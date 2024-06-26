import logging
from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import (
    orm_add_vacancy,
    orm_change_banner_image,
    orm_delete_vacancy,
    orm_get_categories,
    orm_get_info_pages,
    orm_get_vacancies,
    orm_get_vacancy,
    orm_update_banner_description,
    orm_update_vacancy,
)
from filters.chat_types import ChatTypeFilter, IsAdmin
from kbds.inline import get_callback_btns
from kbds.reply import get_keyboard

# Настройка логирования
logger = logging.getLogger(__name__)

# Подключаем роутер для администратора и соответствующий фильтр для приватных чатов
admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())

# Создаем клавиатуру с кнопками
ADMIN_KB = get_keyboard(
    "Добавить вакансию",
    "Выбрать вакансию",
    "Удалить вакансию",
    "Добавить/Изменить баннер",
    "Список вакансий",
    placeholder="Выберите нужную команду",
    sizes=(2, 2, 1),
)

# Команда для активации команд администратора
@admin_router.message(Command("admin"))
async def admin_features(message: types.Message):
    """
    Отправляет администратору клавиатуру с командами.
    """
    await message.answer("Выберите команду", reply_markup=ADMIN_KB)
    logger.info(f"Admin features menu sent to {message.from_user.id}")

@admin_router.message(F.text == "Показать список вакансий")
async def vac_list(message: types.Message):
    """
    Обработчик команды для отображения списка вакансий.
    """
    await message.answer("Список вакансий:")
    logger.info(f"Vacancy list requested by {message.from_user.id}")

@admin_router.message(F.text == "Изменить вакансию")
async def edit_vac(message: types.Message):
    """
    Обработчик команды для изменения вакансии.
    """
    await message.answer("Выберите вакансию для изменения")
    logger.info(f"Vacancy edit requested by {message.from_user.id}")

@admin_router.message(F.text == "Удалить вакансию")
async def delete_vac(message: types.Message):
    """
    Обработчик команды для удаления вакансии.
    """
    await message.answer("Выберите вакансию для удаления")
    logger.info(f"Vacancy delete requested by {message.from_user.id}")

@admin_router.message(F.text == "Список вакансий")
async def admin_features(message: types.Message, session: AsyncSession):
    """
    Отправляет список категорий вакансий для выбора.
    """
    try:
        categories = await orm_get_categories(session)
        btns = {category.name: f'category_{category.category_id}' for category in categories}
        await message.answer("Выберите категорию", reply_markup=get_callback_btns(btns=btns))
        logger.info(f"Categories list sent to {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in admin_features: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении категорий.")

@admin_router.callback_query(F.data.startswith('category_'))
async def get_vacancies(callback: types.CallbackQuery, session: AsyncSession):
    """
    Отправляет список вакансий для выбранной категории.
    """
    try:
        category_id = callback.data.split("_")[-1]
        for vacancy in await orm_get_vacancies(session, int(category_id)):
            await callback.message.answer_photo(
                vacancy.image,
                caption=f"<strong>{vacancy.name}</strong>\n{vacancy.description}\nТребования к кандидату: {vacancy.requirements}",
                reply_markup=get_callback_btns(
                    btns={
                        "Удалить": f"delete_{vacancy.vacancy_id}",
                        "Изменить": f"change_{vacancy.vacancy_id}",
                    }
                ),
            )
        await callback.answer()
        await callback.message.answer("Актуальные вакансии ⏫")
        logger.info(f"Vacancies for category {category_id} sent to {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Error in get_vacancies: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при получении вакансий.")

@admin_router.callback_query(F.data.startswith("delete_"))
async def delete_vacancy_callback(callback: types.CallbackQuery, session: AsyncSession):
    """
    Удаляет вакансию по запросу.
    """
    try:
        vacancy_id = callback.data.split("_")[-1]
        await orm_delete_vacancy(session, int(vacancy_id))
        await callback.answer("Вакансия удалена")
        await callback.message.answer("Вакансия удалена!")
        logger.info(f"Vacancy {vacancy_id} deleted by {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Error in delete_vacancy_callback: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при удалении вакансии.")


################# Микро-FSM для загрузки/изменения баннеров ############################

class AddBanner(StatesGroup):
    image = State()
    description = State()


@admin_router.message(StateFilter(None), F.text == 'Добавить/Изменить баннер')
async def add_image2(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Переход в состояние добавления изображения для баннера.
    """
    try:
        pages_names = [page.name for page in await orm_get_info_pages(session)]
        await message.answer(f"Отправьте фото баннера.\nВ описании укажите для какой страницы:\n{', '.join(pages_names)}")
        await state.set_state(AddBanner.image)
        logger.info(f"Request to add/change banner initiated by {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in add_image2: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении списка страниц.")


@admin_router.message(AddBanner.image, F.photo)
async def add_banner(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Обрабатывает добавление или изменение изображения баннера.
    """
    try:
        image_id = message.photo[-1].file_id
        if not message.caption:
            await message.answer("Пожалуйста, прикрепите описание состояния (например, main) к изображению")
            return
        for_page = message.caption.strip()
        pages_names = [page.name for page in await orm_get_info_pages(session)]
        if for_page not in pages_names:
            await message.answer(f"Введите нормальное название страницы, например:\n{', '.join(pages_names)}")
            return
        
        # Сохраняем данные в состоянии
        await state.update_data(for_page=for_page, image_id=image_id)


        await orm_change_banner_image(session, for_page, image_id)
        await message.answer('''Баннер добавлен/изменен. Теперь введите описание баннера 
                             или отправьте "оставить", чтобы оставить текущее описание.''')
        await state.set_state(AddBanner.description)

        logger.info(f"Banner image for page {for_page} added/changed by {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in add_banner: {e}", exc_info=True)
        await message.answer("Произошла ошибка при добавлении баннера.")


@admin_router.message(AddBanner.image)
async def add_banner2(message: types.Message, state: FSMContext):
    """
    Обработчик некорректного ввода для состояния добавления баннера.
    """
    await message.answer("Отправьте фото баннера или отмена")
    logger.warning(f"Incorrect input for banner by {message.from_user.id}")


@admin_router.message(AddBanner.description, F.text)
async def add_banner_description(message: types.Message, state: FSMContext, session: AsyncSession):
    """
    Обрабатывает добавление или изменение описания баннера.
    """
    try:
        # Извлекаем данные из состояния
        data = await state.get_data()
        for_page = data.get('for_page')
        description = message.text.strip()

        if description.lower() == 'оставить':
            await message.answer("Описание оставлено без изменений")
        else:
            await orm_update_banner_description(session, for_page, description)
            await message.answer("Описание для баннера обновлено.")

        await state.clear()
        
        logger.info(f"Banner description for page {for_page} updated by {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in add_banner_description: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обновлении описания баннера.")

@admin_router.message(AddBanner.description)
async def add_banner_description2(message: types.Message, state: FSMContext):
    """
    Обработчик некорректного ввода для состояния добавления описания баннера.
    """
    await message.answer("Отправьте описание баннера или команду 'оставить' для сохранения текущего описания.")
    logger.warning(f"Incorrect input for banner description by {message.from_user.id}")

#########################################################################################


######################### FSM для добавления/изменения вакансий администратором ###################


# Машина состояний (FSM)
class AddVacancy(StatesGroup):
    name = State()
    description = State()
    requirements = State()
    image = State()
    category = State()
    vacancy_check = State()

    vacancy_for_change = None

    texts = {
        'AddVacancy:name': 'Введите название заново:',
        'AddVacancy:description': 'Введите описание заново:',
        'AddVacancy:requirements': 'Введите требования к кандидатам заново:',
        'AddVacancy:image': 'Отправьте изображение для вакансии',
        'AddVacancy:vacancy_check': 'Подтвердите добавление вакансии вводом сообщения "Да"'
    }

# Callback-запрос для изменения вакансии, активирующийся по нажатию на inline-кнопку
@admin_router.callback_query(StateFilter(None), F.data.startswith("change_"))
async def change_vacancy_callback(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        vacancy_id = callback.data.split("_")[-1]
        vacancy_for_change = await orm_get_vacancy(session, int(vacancy_id))
        AddVacancy.vacancy_for_change = vacancy_for_change
        await callback.answer()
        await callback.message.answer("Введите название вакансии", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(AddVacancy.name)
        logger.info(f"Change vacancy process started by {callback.from_user.id} for vacancy {vacancy_id}")
    except Exception as e:
        logger.error(f"Error in change_vacancy_callback: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при начале изменения вакансии.")

# Добавление вакансии, точка входа в FSM
@admin_router.message(StateFilter(None), F.text == "Добавить вакансию")
async def add_vacancy(message: types.Message, state: FSMContext):
    await message.answer("Введите название вакансии", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AddVacancy.name)
    logger.info(f"Add vacancy process started by {message.from_user.id}")

# Хендлер отмены и сброса состояния
@admin_router.message(StateFilter('*'), Command("отмена"))
@admin_router.message(StateFilter('*'), F.text.casefold() == "отмена")
async def cancel_handler(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("Действия отменены", reply_markup=ADMIN_KB)
    logger.info(f"FSM state cleared by {message.from_user.id}")

# Вернуться на шаг назад (к прошлому состоянию)
@admin_router.message(StateFilter('*'), Command("назад"))
@admin_router.message(StateFilter('*'), F.text.casefold() == "назад")
async def back_step_handler(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state == AddVacancy.name:
        await message.answer('Вы уже вернулись к выбору названия вакансии')
        return
    previous = None
    for step in AddVacancy.__all_states__:
        if step.state == current_state:
            await state.set_state(previous)
            await message.answer(f"Вы вернулись к прошлому шагу \n {AddVacancy.texts[previous.state]}")
            logger.info(f"User {message.from_user.id} returned to previous step {previous.state}")
            return
        previous = step

# Ловим данные для состояние name и меняем состояние на description
@admin_router.message(AddVacancy.name, F.text)
async def add_name(message: types.Message, state: FSMContext):
    if message.text == "." and AddVacancy.vacancy_for_change:
        await state.update_data(name=AddVacancy.vacancy_for_change.name)
    else:
        if len(message.text) >= 100:
            await message.answer("Название вакансии не должно превышать 100 символов. \nВведите другое название")
            return
        await state.update_data(name=message.text)
    await message.answer("Введите описание вакансии")
    await state.set_state(AddVacancy.description)

@admin_router.message(AddVacancy.name)
async def add_name2(message: types.Message, state: FSMContext):
    await message.answer("Недопустимый ввод. Введите название вакансии заново")

# Ловим данные для состояние description и далее переходим к requirements
@admin_router.message(AddVacancy.description, F.text)
async def add_description(message: types.Message, state: FSMContext):
    if message.text == "." and AddVacancy.vacancy_for_change:
        await state.update_data(description=AddVacancy.vacancy_for_change.description)
    else:
        await state.update_data(description=message.text)
    await message.answer("Введите требования к кандидатам")
    await state.set_state(AddVacancy.requirements)

@admin_router.message(AddVacancy.description)
async def add_description2(message: types.Message, state: FSMContext):
    await message.answer("Недопустимый ввод. Введите описание вакансии заново")

# Ловим данные для состояние requirements и далее меняем состояние на image
@admin_router.message(AddVacancy.requirements, F.text)
async def add_requirements(message: types.Message, state: FSMContext):
    if message.text == "." and AddVacancy.vacancy_for_change:
        await state.update_data(requirements=AddVacancy.vacancy_for_change.requirements)
    else:
        await state.update_data(requirements=message.text)
    await message.answer("Отправьте изображение для вакансии")
    await state.set_state(AddVacancy.image)

@admin_router.message(AddVacancy.requirements)
async def add_requirements(message: types.Message, state: FSMContext):
    await message.answer("Недопустимый ввод. Отправьте требования повторно")

# Ловим данные для состояние image и переходим к выбору категории вакансий
@admin_router.message(AddVacancy.image, or_f(F.photo, F.text == '.'))
async def add_image(message: types.Message, state: FSMContext, session: AsyncSession):
    if message.text and message.text == "." and AddVacancy.vacancy_for_change:
        await state.update_data(image=AddVacancy.vacancy_for_change.image)
    elif message.photo:
        await state.update_data(image=message.photo[-1].file_id)
        await message.answer("Изображение добавлено")
    else:
        await message.answer("Отправьте изображение как фото, не как файл")
        return
    categories = await orm_get_categories(session)
    btns = {category.name: str(category.category_id) for category in categories}
    await message.answer("Выберите категорию для вакансии", reply_markup=get_callback_btns(btns=btns))
    await state.set_state(AddVacancy.category)

@admin_router.message(AddVacancy.image)
async def add_image2(message: types.Message, state: FSMContext):
    await message.answer("Недопустимые данные. Попробуйте отправить изображение как фото")

# Ловим callback-запрос выбора категории
@admin_router.callback_query(AddVacancy.category)
async def category_choice(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        if int(callback.data) in [category.category_id for category in await orm_get_categories(session)]:
            await callback.answer()
            await state.update_data(category=callback.data)
            await callback.message.answer("Подтвердите добавление вакансии вводом сообщения 'Да'")
            await state.set_state(AddVacancy.vacancy_check)
        else:
            await callback.message.answer('Выберите категорию из кнопок выше')
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in category_choice: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при выборе категории.")

@admin_router.message(AddVacancy.category)
async def category_choice2(message: types.Message, state: FSMContext):
    await message.answer("'Выберите категорию из кнопок выше'")


# Ловим данные для состояния vacancy_check, сохраняем все в БД и затем выходим из FSM
@admin_router.message(AddVacancy.vacancy_check, F.text.lower() == 'да')
async def add_vacancy_check(message: types.Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()

    # Только для теста, потом убрать!!!
    await message.answer(str(data))

    try:
        if AddVacancy.vacancy_for_change:
            await orm_update_vacancy(session, AddVacancy.vacancy_for_change.vacancy_id, data)
            await message.answer("Вакансия успешно изменена", reply_markup=get_keyboard("OK"))
            logger.info(f"Vacancy {AddVacancy.vacancy_for_change.vacancy_id} updated by {message.from_user.id}")
        else:
            await orm_add_vacancy(session, data)
            await message.answer("Отлично, вакансия добавлена!", reply_markup=get_keyboard("OK"))
            logger.info(f"New vacancy added by {message.from_user.id}")

        await state.clear()
        AddVacancy.vacancy_for_change = None

    except Exception as e:
        logger.error(f"Error in add_vacancy_check: {e}", exc_info=True)
        await message.answer(
            f"Ошибка: \n{str(e)}\nВозникла ошибка, проконсультируйтесь с разработчиком бота",
            reply_markup=get_keyboard("OK"),
        )
        await state.clear()

@admin_router.message(AddVacancy.vacancy_check)
async def add_vacancy_check2(message: types.Message, state: FSMContext):
    await message.answer("Недопустимые данные. Если хотите выйти, напишите 'отмена'")
    logger.warning(f"Incorrect input for vacancy check by {message.from_user.id}")
