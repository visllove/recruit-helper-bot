# Recruit Helper Bot

Телеграм-бот для первичного отбора резюме под вакансии с помощью LLM.
Цель — быстро отсечь 70–80% нерелевантных резюме и оставить управляемый шорт-лист.

# Возможности
- Превращает текст вакансии в чек-лист требований (must/optional, теги, min_years/level).

- Сопоставляет резюме с требованиями и возвращает статусы 1 / 0.5 / 0 + короткие цитаты-evidence.

- Итог: overall score, must/optional, matched/missing, highlights.

- Оптимальный пайплайн: локальный парсинг PDF → макс. 2 LLM-вызова на новую пару «вакансия×резюме».

- Кэширование по контенту (строго 64-символьные SHA-ключи) для скорости и экономии.

# Быстрый старт
Требования
- Python 3.11+

- PostgreSQL 13+

- OpenAI API Key

- (Опционально) Tesseract и Poppler (для OCR)

Установка
bash
Copy
Edit
git clone <repo-url>
cd recruit-helper-bot

python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows
.venv\Scripts\activate

pip install -r requirements.txt
Настройка окружения
Создайте файл .env в корне:

env
Copy
Edit
# Telegram
BOT_TOKEN=123456:ABC...

# База
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/atsdb

# OpenAI
OPENAI_API_KEY=sk-...

# Модель и лимиты
LLM_MODEL=gpt-4o
MAX_OUTPUT_TOKENS=1200

# Извлечение текста резюме
ATS_EXTRACT_MODE=local      local | llm
ATS_OCR=0                   1 = включить OCR fallback (tesseract + poppler)

# Версии правил/промптов (для инвалидирования кэша)
PROMPT_VERSION=2025-08-11a
RULES_VERSION=2025-08-11a

# Логи (опц.)
LOG_LEVEL=INFO
База данных
Минимально используется KV-таблица кэша:

`sql
Copy
Edit
CREATE TABLE IF NOT EXISTS llm_cache (
  key          VARCHAR(64) PRIMARY KEY,  -- строго 64-символьный SHA-256 hex
  payload_json TEXT NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT now(),
  updated_at   TIMESTAMPTZ DEFAULT now()
);
`

Рекомендуется управлять схемой через Alembic. При необходимости можно заменить payload_json на JSONB.

Запуск
`bash
python app.py
`
# или
`bash
python -m app
`
`
