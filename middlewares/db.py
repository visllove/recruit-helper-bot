from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker


class DataBaseSession(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        """
        Инициализация middleware с пулом сессий.
        
        :param session_pool: Асинхронный пул сессий SQLAlchemy.
        """
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Вызов middleware, добавляющий сессию в данные события.

        :param handler: Функция-обработчик события.
        :param event: Объект события Telegram.
        :param data: Словарь данных события.
        :return: Результат вызова обработчика.
        """
        try:
            async with self.session_pool() as session:
                data['session'] = session
                return await handler(event, data)
        except Exception as e:
            # Логирование ошибки или обработка исключения
            print(f"Error in DataBaseSession middleware: {e}")
            raise e



# class CounterMiddleware(BaseMiddleware):
#     def __init__(self) -> None:
#         self.counter = 0

#     async def __call__(
#         self,
#         handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
#         event: TelegramObject,
#         data: Dict[str, Any]
#     ) -> Any:
#         self.counter += 1
#         data['counter'] = self.counter
#         return await handler(event, data)