from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


class MenuCallBack(CallbackData, prefix="menu"):
    level: int
    menu_name: str
    category: int | None = None
    page: int = 1
    vacancy_id: int | None = None

# Клавиатура для баннера main (стартового баннера)
def get_user_main_btns(*, level: int, sizes: tuple[int] = (2,)):
    keyboard = InlineKeyboardBuilder()
    btns = {
        "Вакансии 📖": "vacancies",
        "Выбранные вакансии 💼": "cart",
        "О компании: ℹ️": "about",
        "Офисы на карте 🗺️": "map",
    }
    for text, menu_name in btns.items():
        keyboard.add(InlineKeyboardButton(
            text=text,
            callback_data=MenuCallBack(level=(level + 1 if menu_name == 'vacancies' else (3 if menu_name == 'cart' else level)), menu_name=menu_name).pack()
        ))

    return keyboard.adjust(*sizes).as_markup()


def get_user_categories_btns(*, level: int, categories: list, sizes: tuple[int] = (2,)):
    keyboard = InlineKeyboardBuilder()

    keyboard.add(InlineKeyboardButton(
        text='Назад',
        callback_data=MenuCallBack(level=level - 1, menu_name='main').pack()
    ))
    keyboard.add(InlineKeyboardButton(
        text='Выбранные вакансии 💼',
        callback_data=MenuCallBack(level=3, menu_name='cart').pack()
    ))
    
    for c in categories:
        keyboard.add(InlineKeyboardButton(
            text=c.name,
            callback_data=MenuCallBack(level=level + 1, menu_name=c.name, category=c.category_id).pack()
        ))
    
    return keyboard.adjust(*sizes).as_markup()


# Клавиатура для баннера с вакансиями
def get_vacancies_btns(
        *,
        level: int,
        category: int,
        page: int,
        pagination_btns: dict,
        vacancy_id: int,
        sizes: tuple[int] = (2, 1)
):
    keyboard = InlineKeyboardBuilder()

    keyboard.add(InlineKeyboardButton(
        text='Назад',
        callback_data=MenuCallBack(level=level - 1, menu_name='categories').pack()
    ))
    keyboard.add(InlineKeyboardButton(
        text='Выбранные вакансии 💼',
        callback_data=MenuCallBack(level=3, menu_name='cart').pack()
    ))
    keyboard.add(InlineKeyboardButton(
        text='Выбрать Вакансию',
        callback_data=MenuCallBack(level=level, menu_name='add_to_cart', vacancy_id=vacancy_id).pack()
    ))
    
    keyboard.adjust(*sizes)

    row = [InlineKeyboardButton(
        text=text,
        callback_data=MenuCallBack(
            level=level,
            menu_name=menu_name,
            category=category,
            page=(page + 1 if menu_name == 'next' else page - 1)
        ).pack()
    ) for text, menu_name in pagination_btns.items()]
            
    return keyboard.row(*row).as_markup()


def get_user_cart(
        *,
        level: int,
        page: int | None,
        pagination_btns: dict | None,
        vacancy_id: int | None,
        sizes: tuple[int] = (3,)
):
    keyboard = InlineKeyboardBuilder()
    if page:
        keyboard.add(InlineKeyboardButton(
            text='Удалить',
            callback_data=MenuCallBack(level=level, menu_name='delete', vacancy_id=vacancy_id, page=page).pack()
        ))
        
        keyboard.adjust(*sizes)

        row = [InlineKeyboardButton(
            text=text,
            callback_data=MenuCallBack(
                level=level,
                menu_name=menu_name,
                page=(page + 1 if menu_name == 'next' else page - 1)
            ).pack()
        ) for text, menu_name in pagination_btns.items()]

        keyboard.row(*row)

        row2 = [
            InlineKeyboardButton(
                text='На главную 📃',
                callback_data=MenuCallBack(level=0, menu_name='main').pack()
            ),
            InlineKeyboardButton(
                text='Отправить резюме',
                callback_data=MenuCallBack(level=0, vacancy_id=vacancy_id, menu_name='send_resume').pack()
            ),
        ]
        return keyboard.row(*row2).as_markup()
    else:
        keyboard.add(InlineKeyboardButton(
            text='На главную 📃',
            callback_data=MenuCallBack(level=0, menu_name='main').pack()
        ))
        
        return keyboard.adjust(*sizes).as_markup()


def get_callback_btns(*, btns: dict[str, str], sizes: tuple[int] = (2,)):

    keyboard = InlineKeyboardBuilder()

    for text, data in btns.items():
        keyboard.add(InlineKeyboardButton(text=text, callback_data=data))

    return keyboard.adjust(*sizes).as_markup()




# def get_url_btns(
#     *,
#     btns: dict[str, str],
#     sizes: tuple[int] = (2,)):

#     keyboard = InlineKeyboardBuilder()

#     for text, url in btns.items():
        
#         keyboard.add(InlineKeyboardButton(text=text, url=url))

#     return keyboard.adjust(*sizes).as_markup()


# #Создать микс из CallBack и URL кнопок
# def get_inlineMix_btns(
#     *,
#     btns: dict[str, str],
#     sizes: tuple[int] = (2,)):

#     keyboard = InlineKeyboardBuilder()

#     for text, value in btns.items():
#         if '://' in value:
#             keyboard.add(InlineKeyboardButton(text=text, url=value))
#         else:
#             keyboard.add(InlineKeyboardButton(text=text, callback_data=value))

#     return keyboard.adjust(*sizes).as_markup()