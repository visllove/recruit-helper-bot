import logging
import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

from database.orm_query import orm_update_banner_description
from middlewares.db import DataBaseSession
from database.engine import create_db, drop_db, session_maker
from handlers.user_private import user_private_router
from handlers.user_group import user_group_router
from handlers.admin_private import admin_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

ALLOWED_UPDATES = ['message', 'edited_message', 'callback_query']

bot = Bot(token=os.getenv('TOKEN'), parse_mode=ParseMode.HTML)
bot.my_admins_list = []
dp = Dispatcher()

# Подключение роутеров для приватных и групповых чатов. Порядок важен!
dp.include_router(user_private_router)
dp.include_router(user_group_router)
dp.include_router(admin_router)

# Создание таблиц в БД при запуске бота, если они еще не были созданы
async def on_startup(bot) -> None:
    # Если нужно удалить БД, строку ниже необходимо раскомментировать
    # await drop_db()
    await create_db()
    logger.info("Database created successfully.")

    # Обновление описания баннеров
    async with session_maker() as session:
        from common.texts_for_db import description_for_info_pages
        for name, description in description_for_info_pages.items():
            await orm_update_banner_description(session, name, description)
        logger.info("Banner descriptions updated successfully.")
        
# Оповещение о том, что бот не работает
async def on_shutdown(bot) -> None:
    logger.info("Bot is shutting down...")

# Функция для запуска бота
async def main() -> None:
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    # Подключение sessionmaker при запуске бота
    dp.update.middleware(DataBaseSession(session_pool=session_maker))

    await bot.delete_webhook(drop_pending_updates=True)
    # Удаление команд при надобности
    # await bot.delete_my_commands(scope=types.BotCommandScopeAllPrivateChats())
    # await bot.set_my_commands(commands=private, scope=types.BotCommandScopeAllPrivateChats())
    # Использование всех доступных способов обновления (колбеки, отредактированные сообщения, сообщения)
    await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)

if __name__ == "__main__":
    asyncio.run(main())
