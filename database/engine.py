import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
from database.models import Base
from common.texts_for_db import categories, description_for_info_pages
from database.orm_query import orm_add_banner_description, orm_create_categories

# Подключение логгера из основного файла
logger = logging.getLogger(__name__)

# Извлечение URL базы данных из переменной окружения
db_url = os.getenv('DB_URL')
if not db_url:
    raise ValueError("переменная окружения DB_URL не установлена")

# Создание асинхронного движка БД
engine = create_async_engine(db_url, echo=True)

# Создание фабрики сессий
session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def create_db():
    """
    Создание всех таблиц в базе данных и загрузка начальных данных.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("База данных успешно создана.")
        
        async with session_maker() as session:
            try:
                await orm_create_categories(session, categories)
                await orm_add_banner_description(session, description_for_info_pages)
                await session.commit()
                logger.info("Начальные данные успешно добавлены в базу данных.")
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка при добавлении начальных данных: {e}", exc_info=True)
                raise

async def drop_db():
    """
    Удаление всех таблиц из базы данных.
    """
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("База данных успешно удалена.")
        except Exception as e:
            logger.error(f"Ошибка при удалении базы данных: {e}", exc_info=True)
            raise
