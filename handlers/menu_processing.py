import logging
from aiogram.types import InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import (
    orm_add_to_cart,
    orm_delete_from_cart,
    orm_get_banner,
    orm_get_categories,
    orm_get_user_carts,
    orm_get_vacancies,
    orm_reduce_vacancy_in_cart
)
from kbds.inline import get_user_cart, get_user_main_btns, get_vacancies_btns, get_user_categories_btns
from utils.paginator import Paginator

logger = logging.getLogger(__name__)

# Изображение и описание по умолчанию (в случае какой-либо ошибки)
DEFAULT_IMAGE_ID = "/images/not_found.jpg"
DEFAULT_CAPTION = "Произошла ошибка, нужный баннер не найден"

async def main_menu(session, level, menu_name):
    """
    Получает баннер для главного меню и возвращает его с кнопками главного меню.
    
    :param session: Асинхронная сессия для работы с базой данных.
    :param level: Уровень меню.
    :param menu_name: Название меню.
    :return: Изображение и кнопки главного меню.
    """
    try:
        banner = await orm_get_banner(session, menu_name)
        image = InputMediaPhoto(media=banner.image, caption=banner.description)
        kbds = get_user_main_btns(level=level)
        return image, kbds
    except Exception as e:
        logger.error(f"Error in main_menu: {e}", exc_info=True)
        return InputMediaPhoto(media=DEFAULT_IMAGE_ID, caption=DEFAULT_CAPTION), get_user_main_btns(level=level)

async def categories(session, level, menu_name):
    """
    Получает баннер для категорий и возвращает его с кнопками категорий.
    
    :param session: Асинхронная сессия для работы с базой данных.
    :param level: Уровень меню.
    :param menu_name: Название меню.
    :return: Изображение и кнопки категорий.
    """
    try:
        banner = await orm_get_banner(session, menu_name)
        image = InputMediaPhoto(media=banner.image, caption=banner.description)
        categories = await orm_get_categories(session)
        kbds = get_user_categories_btns(level=level, categories=categories)
        return image, kbds
    except Exception as e:
        logger.error(f"Error in categories: {e}", exc_info=True)
        return InputMediaPhoto(media=DEFAULT_IMAGE_ID, caption=DEFAULT_CAPTION), get_user_main_btns(level=level)

def pages(paginator: Paginator):
    """
    Проверяет наличие предыдущих и следующих страниц для добавления кнопок пагинации.
    
    :param paginator: Объект пагинатора.
    :return: Словарь с кнопками пагинации.
    """
    btns = dict()
    if paginator.has_previous():
        btns["◀ Предыдущая"] = "previous"
    if paginator.has_next():
        btns["Следующая ▶"] = "next"
    return btns

async def vacancies(session, level, category, page):
    """
    Получает список вакансий, создает пагинатор, возвращает изображение вакансии и кнопки навигации.
    
    :param session: Асинхронная сессия для работы с базой данных.
    :param level: Уровень меню.
    :param category: Категория вакансий.
    :param page: Страница пагинации.
    :return: Изображение вакансии и кнопки навигации.
    """
    try:
        vacancies = await orm_get_vacancies(session, category_id=category)
        paginator = Paginator(vacancies, page=page)
        vacancy = paginator.get_page()[0]
        image = InputMediaPhoto(
            media=vacancy.image,
            caption=f"<strong>{vacancy.name}</strong>\n{vacancy.description}\nТребования к кандидату: {vacancy.requirements}\n<strong>Вакансия {paginator.page} из {paginator.pages}</strong>",
        )
        pagination_btns = pages(paginator)
        kbds = get_vacancies_btns(
            level=level,
            category=category,
            page=page,
            pagination_btns=pagination_btns,
            vacancy_id=vacancy.vacancy_id,
        )
        return image, kbds
    except Exception as e:
        logger.error(f"Error in vacancies: {e}", exc_info=True)
        return InputMediaPhoto(media=DEFAULT_IMAGE_ID, caption=DEFAULT_CAPTION), get_user_main_btns(level=level)

async def carts(session, level, menu_name, page, user_id, vacancy_id):
    """
    Обрабатывает добавление, удаление и изменение вакансий в корзине.
    Получает список корзин пользователя и возвращает изображение и кнопки навигации.
    
    :param session: Асинхронная сессия для работы с базой данных.
    :param level: Уровень меню.
    :param menu_name: Название меню.
    :param page: Страница пагинации.
    :param user_id: Идентификатор пользователя.
    :param vacancy_id: Идентификатор вакансии.
    :return: Изображение и кнопки навигации.
    """
    try:
        if menu_name == 'delete':
            await orm_delete_from_cart(session, user_id, vacancy_id)
            if page > 1:
                page -= 1
        elif menu_name == 'decrement':
            is_cart = await orm_reduce_vacancy_in_cart(session, user_id, vacancy_id)
            if page > 1 and not is_cart:
                page -= 1
        elif menu_name == 'increment':
            await orm_add_to_cart(session, user_id, vacancy_id)
        
        carts = await orm_get_user_carts(session, user_id)
        if not carts:
            banner = await orm_get_banner(session, 'cart')
            image = InputMediaPhoto(media=banner.image, caption=f"<strong>{banner.description}</strong>")
            kbds = get_user_cart(
                level=level,
                page=None,
                pagination_btns=None,
                vacancy_id=None,
            )
        else:
            paginator = Paginator(carts, page=page)
            cart = paginator.get_page()[0]
            image = InputMediaPhoto(
                media=cart.vacancy.image,
                caption=f"<strong>{cart.vacancy.name}</strong>\n{cart.vacancy.description}\nВакансия {paginator.page} из {paginator.pages} выбранных.",
            )
            pagination_btns = pages(paginator)
            kbds = get_user_cart(
                level=level,
                page=page,
                pagination_btns=pagination_btns,
                vacancy_id=cart.vacancy.vacancy_id,
            )
        return image, kbds
    except Exception as e:
        logger.error(f"Error in carts: {e}", exc_info=True)
        return InputMediaPhoto(media=DEFAULT_IMAGE_ID, caption=DEFAULT_CAPTION), get_user_main_btns(level=level)

async def get_menu_content(
        session: AsyncSession,
        level: int,
        menu_name: str,
        category: int | None = None,
        page: int | None = None,
        vacancy_id: int | None = None,
        user_id: int | None = None,
):
    """
    Определяет, какую функцию вызвать в зависимости от уровня меню и возвращает соответствующее содержимое.
    
    :param session: Асинхронная сессия для работы с базой данных.
    :param level: Уровень меню.
    :param menu_name: Название меню.
    :param category: Категория вакансий (по умолчанию None).
    :param page: Страница пагинации (по умолчанию None).
    :param vacancy_id: Идентификатор вакансии (по умолчанию None).
    :param user_id: Идентификатор пользователя (по умолчанию None).
    :return: Соответствующее содержимое меню.
    """
    try:
        if level == 0:
            return await main_menu(session, level, menu_name)
        elif level == 1:
            return await categories(session, level, menu_name)
        elif level == 2:
            return await vacancies(session, level, category, page)
        elif level == 3:
            return await carts(session, level, menu_name, page, user_id, vacancy_id)
    except Exception as e:
        logger.error(f"Error in get_menu_content: {e}", exc_info=True)
        return InputMediaPhoto(media=DEFAULT_IMAGE_ID, caption=DEFAULT_CAPTION), get_user_main_btns(level=level)
