from aiogram.filters import Filter
from aiogram import Bot, types


class ChatTypeFilter(Filter):
    def __init__(self, chat_types: list[str]) -> None:

        """
        Инициализация фильтра по типу чата.

        :param chat_types: Список допустимых типов чатов.
        """

        self.chat_types = chat_types

    async def __call__(self, message: types.Message) -> bool:
        """
        Проверяет, что тип чата сообщения находится в списке допустимых типов.

        :param message: Сообщение, отправленное пользователем.
        :return: True, если тип чата допустим, иначе False.
        """
        return message.chat.type in self.chat_types
    
# Фильтр для списка администраторов
class IsAdmin(Filter):
    def __init__(self) -> None:
        """
        Инициализация фильтра для проверки на администратора.
        """
        pass

    async def __call__(self, message: types.Message, bot: Bot) -> bool:
        """
        Проверяет, что отправитель сообщения является администратором.

        :param message: Сообщение, отправленное пользователем.
        :param bot: Экземпляр бота.
        :return: True, если пользователь является администратором, иначе False.
        """
        return message.from_user.id in bot.my_admins_list