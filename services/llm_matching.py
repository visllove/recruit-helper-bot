# services/llm_matching.py
import os
import json
import hashlib
from typing import Any, Dict, List, Tuple, Optional

from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from database.models import Vacancy, LLMCache

# ===================== конфигурация =====================
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "1200"))

# как извлекать текст резюме: "local" (по умолчанию) или "llm"
ATS_EXTRACT_MODE = os.getenv("ATS_EXTRACT_MODE", "local").strip().lower()  # local | llm
# включить OCR (tesseract) как промежуточный шаг, если PDF без текста
ATS_OCR = os.getenv("ATS_OCR", "0").strip().lower() in {"1", "true", "yes"}

# версии правил/промптов — меняем при правках, чтобы инвалидировать кэш
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "2025-08-11a")
RULES_VERSION  = os.getenv("RULES_VERSION",  "2025-08-11a")

client = AsyncOpenAI(timeout=60.0, max_retries=2)

# ===================== utils & cache =====================
def _sha256_hex(*parts: bytes) -> str:
    """Вернуть ровно 64-символьный hex SHA-256 по набору байтовых кусков."""
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.hexdigest()

def _cache_key_requirements(vacancy_text: str) -> str:
    """ ключ для кэша требований вакансии """
    key = _sha256_hex(
        b"reqs",
        LLM_MODEL.encode("utf-8"),
        PROMPT_VERSION.encode("utf-8"),
        vacancy_text.encode("utf-8", "ignore"),
    )
    return key  # всегда 64 символа

def _cache_key_final_from_text(vacancy_text: str, resume_text_sha: str) -> str:
    """ ключ финального результата (когда есть локально извлечённый текст) """
    key = _sha256_hex(
        b"final",
        LLM_MODEL.encode("utf-8"),
        ATS_EXTRACT_MODE.encode("utf-8"),
        PROMPT_VERSION.encode("utf-8"),
        RULES_VERSION.encode("utf-8"),
        vacancy_text.encode("utf-8", "ignore"),
        resume_text_sha.encode("utf-8"),
    )
    return key

def _cache_key_final_from_bytes(vacancy_text: str, resume_bytes: bytes) -> str:
    """ ключ финального результата (fallback, когда работаем по PDF-байтам) """
    key = _sha256_hex(
        b"final",
        LLM_MODEL.encode("utf-8"),
        ATS_EXTRACT_MODE.encode("utf-8"),
        PROMPT_VERSION.encode("utf-8"),
        RULES_VERSION.encode("utf-8"),
        vacancy_text.encode("utf-8", "ignore"),
        resume_bytes,
    )
    return key

def _cache_key_file_id(resume_bytes: bytes) -> str:
    """ ключ для кэша openai file_id по байтам PDF """
    key = _sha256_hex(b"fileid", resume_bytes)
    return key

async def _cache_get(session: AsyncSession, key: str) -> Optional[Dict[str, Any]]:
    q = await session.execute(select(LLMCache).where(LLMCache.key == key))
    row = q.scalar_one_or_none()
    return json.loads(row.payload_json) if row else None

async def _cache_set(session: AsyncSession, key: str, payload: Dict[str, Any]) -> None:
    payload_str = json.dumps(payload, ensure_ascii=False)
    stmt = insert(LLMCache).values(key=key, payload_json=payload_str)
    # idempotent upsert
    stmt = stmt.on_conflict_do_update(
        index_elements=[LLMCache.key],
        set_={"payload_json": payload_str}
    )
    try:
        await session.execute(stmt)
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise

async def _get_vacancy_text(session: AsyncSession, vacancy_id: int) -> str:
    v: Optional[Vacancy] = await session.get(Vacancy, vacancy_id)
    if not v:
        return ""
    parts = [v.name or "", v.description or "", getattr(v, "requirements", "") or ""]
    text = "\n".join(p.strip() for p in parts if p and p.strip())
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())

# ===================== локальный парсинг PDF =====================
def _extract_text_pymupdf(pdf_bytes: bytes) -> Optional[str]:
    """Быстрый извлекатель текста для цифровых PDF (без OCR)."""
    try:
        import fitz  # PyMuPDF
    except Exception:
        return None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None
    pieces: List[str] = []
    try:
        for page in doc:
            txt = page.get_text("text")
            if txt and txt.strip():
                pieces.append(txt.strip())
    finally:
        doc.close()
    full = "\n\n".join(pieces).strip()
    return full if full else None

def _extract_text_ocr_tesseract(pdf_bytes: bytes) -> Optional[str]:
    """OCR как резерв (требует tesseract и poppler для pdf2image)."""
    if not ATS_OCR:
        return None
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except Exception:
        return None
    try:
        images = convert_from_bytes(pdf_bytes)
    except Exception:
        return None
    texts: List[str] = []
    for img in images:
        try:
            txt = pytesseract.image_to_string(img)
        except Exception:
            txt = ""
        if txt and txt.strip():
            texts.append(txt.strip())
    full = "\n\n".join(texts).strip()
    return full if full else None

# ===================== Pydantic-схемы =====================

class Requirement(BaseModel):
    text: str
    tags: List[str] = Field(default_factory=list)
    must: bool
    min_years: Optional[float] = None
    level: Optional[str] = None
    weight: Optional[float] = None

class VacancyRequirements(BaseModel):
    requirements: List[Requirement]

class ScoredRequirement(BaseModel):
    req_index: int
    # 1.0 выполнено, 0.5 частично, 0 нет
    status: float                 
    years: Optional[float] = None
    evidence: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

class RequirementScores(BaseModel):
    per_requirement: List[ScoredRequirement]

# ===================== LLM вызовы =====================
async def parse_vacancy_requirements(vacancy_text: str) -> List[Dict[str, Any]]:
    """Достаём чек-лист требований из текста вакансии."""
    resp = await client.responses.parse(
        model=LLM_MODEL,
        instructions=(
            "Extract a concise checklist of job requirements.\n"
            "- Split composite items into atomic requirements (e.g., 'replication, migrations, backups' -> three lines).\n"
            "- Set must=true for mandatory items; otherwise false.\n"
            "- Infer min_years/level if explicitly present.\n"
            "- Keep tags short (e.g., 'postgresql','replication','backup').\n"
            "- Only include weight if explicitly implied; otherwise leave it null."
        ),
        input=f"Vacancy text:\n{vacancy_text}",
        text_format=VacancyRequirements,
        temperature=0,
        top_p=1,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    data: VacancyRequirements = resp.output_parsed
    reqs: List[Dict[str, Any]] = []
    for r in data.requirements:
        weight = r.weight if r.weight is not None else (2.0 if r.must else 1.0)
        reqs.append({
            "text": r.text,
            "tags": r.tags or [],
            "must": r.must,
            "min_years": r.min_years,
            "level": r.level,
            "weight": weight,
        })
    return reqs

async def score_requirements_from_file(file_id: str, requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Скоринг по PDF через OpenAI (file input)."""
    resp = await client.responses.parse(
        model=LLM_MODEL,
        instructions=(
            "You are an ATS evaluator.\n"
            "- For each requirement return status in {1, 0.5, 0}.\n"
            "- Include 1–2 verbatim quotes from the resume as evidence; avoid hallucinations.\n"
            "- If years of experience can be inferred, include it in 'years'.\n"
            "- Reject non-relevant quotes; do not duplicate evidence strings."
        ),
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text",
                 "text": "Requirements JSON:\n" + json.dumps({"requirements": requirements}, ensure_ascii=False)},
                {"type": "input_file", "file_id": file_id},
            ],
        }],
        text_format=RequirementScores,
        temperature=0,
        top_p=1,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    parsed: RequirementScores = resp.output_parsed
    return [s.model_dump() for s in parsed.per_requirement]

async def score_requirements_from_text(resume_text: str, requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Скоринг по локально извлечённому тексту резюме (предпочтительный путь)."""
    resp = await client.responses.parse(
        model=LLM_MODEL,
        instructions=(
            "You are an ATS evaluator.\n"
            "- For each requirement return status in {1, 0.5, 0}.\n"
            "- Evidence must be verbatim quotes from the provided resume TEXT; avoid hallucinations.\n"
            "- If years of experience can be inferred, include it in 'years'.\n"
            "- No duplicate evidence strings. If no relevant quote exists, set status=0."
        ),
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text",
                 "text": "Requirements JSON:\n" + json.dumps({"requirements": requirements}, ensure_ascii=False)},
                {"type": "input_text",
                 "text": "RESUME TEXT (verbatim):\n" + resume_text},
            ],
        }],
        text_format=RequirementScores,
        temperature=0,
        top_p=1,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    parsed: RequirementScores = resp.output_parsed
    return [s.model_dump() for s in parsed.per_requirement]

# ===================== агрегация =====================
def assemble_final(
    requirements: List[Dict[str, Any]],
    per_req: List[Dict[str, Any]],
) -> Tuple[float, Dict[str, float], List[str], List[str], List[str]]:
    idx_map = {s["req_index"]: s for s in per_req if 0 <= s["req_index"] < len(requirements)}
    total_w = sum(r["weight"] for r in requirements) or 1.0
    base = 0.0
    must_w = sum(r["weight"] for r in requirements if r["must"]) or 1.0
    opt_w  = sum(r["weight"] for r in requirements if not r["must"]) or 1.0
    must_sum = 0.0
    opt_sum  = 0.0

    matched: List[str] = []
    missing: List[str] = []
    highlights: List[str] = []

    for i, r in enumerate(requirements):
        s = idx_map.get(i, {"status": 0.0, "years": None, "evidence": []})
        w = r["weight"]
        st = float(s.get("status", 0.0))
        base += w * st
        if r["must"]:
            must_sum += w * st
        else:
            opt_sum  += w * st

        if st >= 0.95:
            matched.append(r["text"])
        if st < 0.5:
            missing.append(r["text"])

        for q in (s.get("evidence") or []):
            if q and len(highlights) < 3:
                q = q.strip()
                highlights.append(q[:350] + ("…" if len(q) > 350 else ""))

    base_ratio = base / total_w

    # бонус +2 за каждый пункт за must с min_years, если выполнено (лимит +10)
    bonus = 0.0
    for i, r in enumerate(requirements):
        if r.get("min_years") is not None and r["must"]:
            yrs = (idx_map.get(i) or {}).get("years")
            if isinstance(yrs, (int, float)) and yrs >= r["min_years"]:
                bonus += 2.0
    bonus = min(bonus, 10.0)

    score_overall = round(min(100.0, 100.0 * base_ratio + bonus), 1)
    subscores = {
        "must_have": round(100.0 * (must_sum / must_w), 1) if any(r["must"] for r in requirements) else 0.0,
        "optional":  round(100.0 * (opt_sum  / opt_w ), 1) if any(not r["must"] for r in requirements) else 0.0
    }
    return score_overall, subscores, matched, missing, highlights



# ===================== публичный API =====================

async def score_resume_api(session: AsyncSession, vacancy_id: int, resume_bytes: bytes) -> Dict[str, Any]:
    """
    Основной сценарий:
      1) Берём текст вакансии из БД.
      2) Кэшируем/достаём чек-лист требований по вакансии.
      3) Извлекаем текст резюме локально (PyMuPDF; опц. OCR, но нужно включить соответствующий флаг). Если не получилось — готовим fallback.
      4) Формируем корректный финальный ключ и сначала проверяем кэш.
      5) Если кэша нет — выполняем скоринг (по тексту или по PDF) и сохраняем результат.
    """
    vacancy_text = await _get_vacancy_text(session, vacancy_id)
    if not vacancy_text:
        return {"error": "vacancy_not_found"}

    # ---------- 1. кэш требований вакансии ----------
    reqs_key = _cache_key_requirements(vacancy_text)
    reqs_cached = await _cache_get(session, reqs_key)
    if reqs_cached and "requirements" in reqs_cached:
        reqs = reqs_cached["requirements"]
    else:
        reqs = await parse_vacancy_requirements(vacancy_text)
        if not reqs:
            return {"error": "requirements_parse_failed"}
        await _cache_set(session, reqs_key, {
            "kind": "requirements",
            "requirements": reqs,
            "prompt_version": PROMPT_VERSION,
            "model": LLM_MODEL
        })

    # ---------- 2. извлекаем текст резюме / готовим fallback ----------
    use_llm_file = (ATS_EXTRACT_MODE != "local")
    resume_text: Optional[str] = None
    if ATS_EXTRACT_MODE == "local":
        resume_text = _extract_text_pymupdf(resume_bytes)
        if not resume_text:
            ocr_text = _extract_text_ocr_tesseract(resume_bytes)
            if ocr_text and ocr_text.strip():
                resume_text = ocr_text
        if not resume_text:
            use_llm_file = True

    # ---------- 3. формируем корректный финальный ключ и проверяем кэш ----------
    if resume_text and not use_llm_file:
        resume_text_sha = hashlib.sha256(resume_text.encode("utf-8")).hexdigest()
        final_key = _cache_key_final_from_text(vacancy_text, resume_text_sha)
    else:
        final_key = _cache_key_final_from_bytes(vacancy_text, resume_bytes)

    cached_final = await _cache_get(session, final_key)
    if cached_final:
        return cached_final

    # ---------- 4. если нужен fallback — берём или создаём file_id (кэш) ----------
    file_id: Optional[str] = None
    if use_llm_file:
        file_key = _cache_key_file_id(resume_bytes)
        cached_file = await _cache_get(session, file_key)
        if cached_file and "openai_file_id" in cached_file:
            file_id = cached_file["openai_file_id"]
        else:
            uploaded = await client.files.create(file=("resume.pdf", resume_bytes), purpose="user_data")
            file_id = uploaded.id
            await _cache_set(session, file_key, {"kind": "file_id", "openai_file_id": file_id})

    # ---------- 5. скоринг ----------
    if resume_text and not use_llm_file:
        per_req = await score_requirements_from_text(resume_text, reqs)
        mode_used = "local_text"
    else:
        if not file_id:
            return {"error": "resume_input_unavailable"}
        per_req = await score_requirements_from_file(file_id, reqs)
        mode_used = "llm_file"

    # ---------- 6. агрегация и кэш ----------
    score, subs, matched, missing, highlights = assemble_final(reqs, per_req)
    result: Dict[str, Any] = {
        "kind": "final_score",
        "score_overall": score,
        "subscores": subs,
        "skills": {"matched": matched, "missing": missing},
        "highlights": highlights,
        "explanations": (
            "Оценка по чек-листу требований (must/optional) с цитатами из резюме. "
            f"Input mode: {mode_used}; prompt={PROMPT_VERSION}; rules={RULES_VERSION}."
        ),
        "model_info": {"llm_model": LLM_MODEL},
        "meta": {
            "prompt_version": PROMPT_VERSION,
            "rules_version": RULES_VERSION,
            "input_mode": mode_used,
        },
    }
    await _cache_set(session, final_key, result)
    return result
