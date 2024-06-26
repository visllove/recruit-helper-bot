import fitz  # PyMuPDF
import os
import logging
from aiogram import F, types, Router, Bot
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import orm_add_to_cart, orm_add_user, orm_save_resume
from filters.chat_types import ChatTypeFilter
from handlers.menu_processing import get_menu_content
from kbds.inline import MenuCallBack
from analysis.analysis import resume_analysis



# Настройка логирования
logger = logging.getLogger(__name__)

# Создаем объект типа Фильтр и задаем ограничения на его использование только в личных чатах
user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(['private']))

# FSM для обработки pdf-файлов
class ResumeState(StatesGroup):
    waiting_for_resume = State()


@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    """
    Обрабатывает команду /start и отправляет главное меню пользователю.

    :param message: Объект сообщения от пользователя.
    :param session: Асинхронная сессия для работы с базой данных.
    """
    try:
        media, reply_markup = await get_menu_content(session, level=0, menu_name="main")
        await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)
        logger.info(f"Main menu sent to user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in start_cmd: {e}", exc_info=True)
        await message.answer("Произошла ошибка при загрузке меню. Попробуйте позже.")


async def add_to_cart(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):
    """
    Добавляет вакансию в корзину (список отслеживаемых вакансий) пользователя.

    :param callback: Объект callback-запроса.
    :param callback_data: Данные callback-запроса.
    :param session: Асинхронная сессия для работы с базой данных.
    """
    user = callback.from_user
    try:
        # Добавляем пользователя в БД
        await orm_add_user(
            session,
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=None,
        )
        await orm_add_to_cart(session, user_id=user.id, vacancy_id=callback_data.vacancy_id)
        await callback.answer("Вакансия добавлена в список отслеживаемых.")
        logger.info(f"Vacancy {callback_data.vacancy_id} added to cart for user {user.id}")
    except Exception as e:
        logger.error(f"Error in add_to_cart: {e}", exc_info=True)
        await callback.answer(f"Произошла ошибка при добавлении вакансии в список отслеживаемых: {str(e)}")

# Обработка резюме и сохранение данных в виде текста
@user_private_router.message(StateFilter(ResumeState.waiting_for_resume), F.content_type == "document")
async def handle_resume_file(message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot):
    document = message.document
    if document.mime_type != 'application/pdf':
        await message.reply("Пожалуйста, отправьте резюме в виде PDF-файла.")
        return

    resumes_dir = "resumes"
    if not os.path.exists(resumes_dir):
        os.makedirs(resumes_dir)

    file_info = await bot.get_file(document.file_id)
    file_path = file_info.file_path
    downloaded_file = await bot.download_file(file_path)
    
    local_file_path = os.path.join(resumes_dir, f"{document.file_id}.pdf")
    with open(local_file_path, 'wb') as f:
        f.write(downloaded_file.read())

    try:
        doc = fitz.open(local_file_path)
        text = ""
        for page in doc:
            text += page.get_text()

        user_id = message.from_user.id

        # Получаем vacancy_id из FSM контекста
        data = await state.get_data()
        vacancy_id = data.get('vacancy_id')
        file_id = document.file_id
        
        await orm_save_resume(session, user_id, vacancy_id, file_id, text)
        
        # Анализируем резюме и вакансию
        similarity_score = await resume_analysis(session, vacancy_id, resume_text=text)

        await message.reply("Ваше резюме было успешно получено и отправлено на проверку.")
        await message.answer(f'Ваше резюме соответствует вакансии с такой оценкой: {round(similarity_score, 2)}')

    except Exception as e:
        await message.reply("Произошла ошибка при обработке файла. Попробуйте еще раз.")
        logger.error(f"Error in handle_resume_file: {e}", exc_info=True)
    finally:
        doc.close()  # Закрываем документ, чтобы освободить файл
        os.remove(local_file_path)

    await state.clear()

# Возврат к меню после команды "Отменить"
@user_private_router.message(StateFilter(ResumeState.waiting_for_resume), F.text.lower() == "отменить")
async def cancel_resume(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply("Вы вернулись в главное меню.")

# Обработка некорректного ввода во время ожидания резюме
@user_private_router.message(StateFilter(ResumeState.waiting_for_resume))
async def handle_invalid_input(message: types.Message):
    await message.reply("Пожалуйста, отправьте PDF-файл резюме или введите 'отменить' для отмены.")

# Обработка кнопки "Отправить резюме", которую нажимает пользователь
async def send_resume(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer('Отправьте pdf-файл вашего резюме или введите "отменить", чтобы вернуться к меню')
    await state.set_state(ResumeState.waiting_for_resume)


@user_private_router.callback_query(MenuCallBack.filter())
async def user_menu(callback: types.CallbackQuery, callback_data: MenuCallBack, state: FSMContext, session: AsyncSession):
    """
    Обрабатывает callback-запросы и редактирует контент в сообщении.

    :param callback: Объект callback-запроса.
    :param callback_data: Данные callback-запроса.
    :param session: Асинхронная сессия для работы с базой данных.
    """
    try:
        if callback_data.menu_name == "add_to_cart":
            await add_to_cart(callback, callback_data, session)
            return 
        elif callback_data.menu_name == 'send_resume':
            await state.update_data(vacancy_id=callback_data.vacancy_id)
            await send_resume(callback, state)
            return
        
        # формируем переменные для их последующей передачи в метод edit_media
        media, reply_markup = await get_menu_content(
            session,
            level=callback_data.level,
            menu_name=callback_data.menu_name,
            category=callback_data.category,
            page=callback_data.page,
            vacancy_id=callback_data.vacancy_id,
            user_id=callback.from_user.id,
        )

        await callback.message.edit_media(media=media, reply_markup=reply_markup)
        await callback.answer()
        logger.info(f"Menu {callback_data.menu_name} sent to user {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Error in user_menu: {e}", exc_info=True)
        # await callback.answer("Произошла ошибка при обработке запроса. Попробуйте позже.")













# @user_private_router.message(StateFilter(None), CommandStart())
# async def start_cmd(message: types.Message):
#     await message.answer("Привет, я виртуальный помощник", 
#                          reply_markup=get_keyboard(
#                              'Показать вакансии',
#                              'О компании',
#                              'Карта',
#                              'Отправить резюме',
#                              placeholder='Что вам нужно?',
#                              sizes=(2,2)
#                             ),
#                         )


# @user_private_router.message(or_f(Command('vacancies'), (F.text.lower() == 'показать вакансии')))
# async def vacancies_cmd(message: types.Message, session: AsyncSession):
#     for vacancy in await orm_get_vacancies(session):
#         await message.answer_photo(
#             vacancy.image,
#             caption=f"<strong>{vacancy.name}\
#                 </strong>\n{vacancy.description}\nТребования к кандидату:{vacancy.requirements}",
#         )
#     await message.answer("Список вакансий")


# @user_private_router.message(F.text.lower() == 'о компании')
# @user_private_router.message(Command('about'))
# async def about_cmd(message: types.Message):
#     await message.answer("О нас:")
#     text = as_marked_section(
#         Bold("ООО «Газпром межрегионгаз Санкт-Петербург"),
#         """входит в Группу «Газпром межрегионгаз». 
#         Компания является поставщиком природного газа 
#         в Северо-Западном федеральном округе. 
#         Осуществляет свою деятельность в четырех регионах округа: 
#         Санкт-Петербурге, Ленинградской и Калининградской областях, в Республике Карелия.
#         """,
#     marker='🖋️'
#     )
#     await message.answer(text.as_html())


# @user_private_router.message(F.text.lower() == 'завершить диалог')
# @user_private_router.message(Command('end'))
# async def end_cmd(message: types.Message):
#     await message.answer("До скорых встреч!")

# @user_private_router.message(F.text.lower() == 'карта')
# @user_private_router.message(Command('map'))
# async def map_cmd(message: types.Message):
#     await message.answer("Карта расположений офисов компании:")


# @user_private_router.message(F.text.lower() == 'вакансии')
# async def vacancy_cmd(message: types.Message):
#     await message.answer("Список вакансий:")


# @user_private_router.message(F.contact)
# async def get_contact(message: types.Message):
#     await message.answer(f"Номер получен")
#     await message.answer(str(message.contact))


# @user_private_router.message(F.location)
# async def get_location(message: types.Message):
#     await message.answer(f" Ваше местоположение получено")
#     await message.answer(str(message.location))