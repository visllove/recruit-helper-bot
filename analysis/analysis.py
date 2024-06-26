import os
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sentence_transformers import SentenceTransformer, util
import logging
from database.models import Vacancy

logger = logging.getLogger(__name__)

cache_dir = os.getenv('HF_HOME')

models = [
            'paraphrase-multilingual-mpnet-base-v2',
	]

# Функция для извлечения текста вакансии из базы данных
async def get_vacancy_text(session: AsyncSession, vacancy_id: int) -> str:
    result = await session.execute(select(Vacancy).where(Vacancy.vacancy_id == vacancy_id))
    vacancy = result.scalar_one()
    return f"{vacancy.name}. {vacancy.description}. {vacancy.requirements}"

# Функция для анализа резюме и вакансии
async def resume_analysis(session: AsyncSession, vacancy_id: int, resume_text: str):
      
    for m in models:
        try:
            model = SentenceTransformer(m, cache_folder=cache_dir)
        except Exception as e:
            logger.error(f"Ошибка при загрузке модели {m}: {str(e)}")
            continue

        # Извлечение текста вакансии из базы данных
        vacancy_text = await get_vacancy_text(session, vacancy_id)

        # Получение векторных представлений
        resume_vec = model.encode(resume_text, convert_to_tensor=True)
        vacancy_vec = model.encode(vacancy_text, convert_to_tensor=True)

        # Расчет косинусного сходства
        similarity = util.pytorch_cos_sim(resume_vec, vacancy_vec).item() * 100
        logger.info(f"Совместимость по модели {m}: {similarity:.2f}%")
        
        return similarity
