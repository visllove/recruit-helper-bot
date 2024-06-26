import logging
from string import punctuation
from aiogram import F, Bot, types, Router
from aiogram.filters import Command
from filters.chat_types import ChatTypeFilter
from common.restricted_words import restricted_words

# Настройка логирования
logger = logging.getLogger(__name__)

# Создаем экземпляр класса Router для использования фильтра в групповых чатах
user_group_router = Router()
user_group_router.message.filter(ChatTypeFilter(['group', 'supergroup']))
user_group_router.edited_message.filter(ChatTypeFilter(['group', 'supergroup']))

@user_group_router.message(Command('admin'))
async def get_admins(message: types.Message, bot: Bot):
    """
    Получает список администраторов чата и сохраняет их в bot.my_admins_list.
    Удаляет сообщение, если отправитель является администратором.
    
    :param message: Объект сообщения от пользователя.
    :param bot: Объект бота.
    """
    try:
        chat_id = message.chat.id
        admins_list = await bot.get_chat_administrators(chat_id)
        # Код ниже - это генератор списка
        admins_list = [
            member.user.id
            for member in admins_list
            if member.status in ('creator', 'administrator')
        ]
        bot.my_admins_list = admins_list
        if message.from_user.id in admins_list:
            await message.delete()
        logger.info(f"Admins list updated for chat {chat_id}: {admins_list}")
    except Exception as e:
        logger.error(f"Error in get_admins: {e}", exc_info=True)

def clean_text(text: str) -> str:
    """
    Удаляет пунктуацию из текста.

    :param text: Входной текст.
    :return: Текст без пунктуации.
    """
    return text.translate(str.maketrans('', '', punctuation))

@user_group_router.edited_message()
@user_group_router.message()
async def cleaner(message: types.Message):
    """
    Проверяет сообщение на наличие запрещенных слов и удаляет его, если таковые найдены.
    
    :param message: Объект сообщения от пользователя.
    """
    try:
        if restricted_words.intersection(clean_text(message.text.lower()).split()):
            await message.answer(f"{message.from_user.first_name}, не ругайтесь!")
            await message.delete()
            logger.info(f"Message from {message.from_user.id} deleted for using restricted words.")
            # Если захотите забанить пользователя
            # await message.chat.ban(message.from_user.id)
    except Exception as e:
        logger.error(f"Error in cleaner: {e}", exc_info=True)
