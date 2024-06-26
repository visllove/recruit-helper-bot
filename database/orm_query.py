import logging
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import Banner, ResumeText, User, Cart, Vacancy, Resume, Category

# Настройка логирования
logger = logging.getLogger(__name__)

############### Работа с баннерами (информационными страницами) ###############

async def orm_add_banner_description(session: AsyncSession, data: dict):
    try:
        query = select(Banner)
        result = await session.execute(query)
        if result.first():
            return
        session.add_all([Banner(name=name, description=description) for name, description in data.items()])
        await session.commit()
        logger.info("Banner descriptions added successfully.")
    except Exception as e:
        await session.rollback()
        logger.error(f"Error adding banner descriptions: {e}", exc_info=True)

### Доработать обновление описания баннеров
async def orm_update_banner_description(session: AsyncSession, name: str, description: str):
    query = update(Banner).where(Banner.name == name).values(description=description)
    await session.execute(query)
    await session.commit()


async def orm_change_banner_image(session: AsyncSession, name: str, image: str):
    try:
        query = update(Banner).where(Banner.name == name).values(image=image)
        await session.execute(query)
        await session.commit()
        logger.info(f"Banner image for '{name}' changed successfully.")
    except Exception as e:
        await session.rollback()
        logger.error(f"Error changing banner image: {e}", exc_info=True)


async def orm_get_banner(session: AsyncSession, page: str) -> Banner:
    try:
        query = select(Banner).where(Banner.name == page)
        result = await session.execute(query)
        return result.scalar()
    except Exception as e:
        logger.error(f"Error fetching banner for page '{page}': {e}", exc_info=True)


async def orm_get_info_pages(session: AsyncSession) -> list[Banner]:
    try:
        query = select(Banner)
        result = await session.execute(query)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error fetching info pages: {e}", exc_info=True)

############################ Категории ######################################

async def orm_get_categories(session: AsyncSession) -> list[Category]:
    try:
        query = select(Category)
        result = await session.execute(query)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error fetching categories: {e}", exc_info=True)


async def orm_create_categories(session: AsyncSession, categories: list):
    try:
        query = select(Category)
        result = await session.execute(query)
        if result.first():
            return
        session.add_all([Category(name=name) for name in categories])
        await session.commit()
        logger.info("Categories created successfully.")
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating categories: {e}", exc_info=True)

############################ Админка ######################################

async def orm_add_vacancy(session: AsyncSession, data: dict):
    try:
        obj = Vacancy(
            name=data["name"],
            description=data["description"],
            requirements=data["requirements"],
            image=data["image"],
            category_id=int(data["category"])
        )
        session.add(obj)
        await session.commit()
        logger.info(f"Vacancy '{data['name']}' added successfully.")
    except Exception as e:
        await session.rollback()
        logger.error(f"Error adding vacancy: {e}", exc_info=True)


async def orm_get_vacancies(session: AsyncSession, category_id: int) -> list[Vacancy]:
    try:
        query = select(Vacancy).where(Vacancy.category_id == int(category_id))
        result = await session.execute(query)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error fetching vacancies for category '{category_id}': {e}", exc_info=True)


async def orm_get_vacancy(session: AsyncSession, vacancy_id: int) -> Vacancy:
    try:
        query = select(Vacancy).where(Vacancy.vacancy_id == vacancy_id)
        result = await session.execute(query)
        return result.scalar()
    except Exception as e:
        logger.error(f"Error fetching vacancy '{vacancy_id}': {e}", exc_info=True)


async def orm_update_vacancy(session: AsyncSession, vacancy_id: int, data: dict):
    try:
        query = update(Vacancy).where(Vacancy.vacancy_id == vacancy_id).values(
            name=data["name"],
            description=data["description"],
            requirements=data["requirements"],
            image=data["image"],
            category_id=int(data["category"])
        )
        await session.execute(query)
        await session.commit()
        logger.info(f"Vacancy '{vacancy_id}' updated successfully.")
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating vacancy: {e}", exc_info=True)


async def orm_delete_vacancy(session: AsyncSession, vacancy_id: int):
    try:
        query = delete(Vacancy).where(Vacancy.vacancy_id == vacancy_id)
        await session.execute(query)
        await session.commit()
        logger.info(f"Vacancy '{vacancy_id}' deleted successfully.")
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting vacancy: {e}", exc_info=True)

##################### Добавляем юзера в БД #####################################

async def orm_add_user(
    session: AsyncSession,
    user_id: int,
    first_name: str | None = None,
    last_name: str | None = None,
    phone: str | None = None,
):
    try:
        query = select(User).where(User.user_id == user_id)
        result = await session.execute(query)
        if result.first() is None:
            session.add(User(user_id=user_id, first_name=first_name, last_name=last_name, phone=phone))
            await session.commit()
            logger.info(f"User '{user_id}' added to the database.")
    except Exception as e:
        await session.rollback()
        logger.error(f"Error adding user '{user_id}': {e}", exc_info=True)

######################## Работа с корзинами #######################################

async def orm_add_to_cart(session: AsyncSession, user_id: int, vacancy_id: int) -> Cart:
    try:
        query = select(Cart).where(Cart.user_id == user_id, Cart.vacancy_id == vacancy_id).options(joinedload(Cart.vacancy))
        cart = await session.execute(query)
        cart = cart.scalar()
        if cart:
            await session.commit()
            return cart
        else:
            session.add(Cart(user_id=user_id, vacancy_id=vacancy_id))
            await session.commit()
            logger.info(f"Vacancy '{vacancy_id}' added to cart for user '{user_id}'.")
    except Exception as e:
        await session.rollback()
        logger.error(f"Error adding to cart: {e}", exc_info=True)

# Загрузка связанных корзин с вакансиями
async def orm_get_user_carts(session: AsyncSession, user_id: int) -> list[Cart]:
    try:
        query = select(Cart).filter(Cart.user_id == user_id).options(joinedload(Cart.vacancy))
        result = await session.execute(query)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error fetching carts for user '{user_id}': {e}", exc_info=True)

# Удаление вакансии из корзины
async def orm_delete_from_cart(session: AsyncSession, user_id: int, vacancy_id: int):
    try:
        query = delete(Cart).where(Cart.user_id == user_id, Cart.vacancy_id == vacancy_id)
        await session.execute(query)
        await session.commit()
        logger.info(f"Vacancy '{vacancy_id}' removed from cart for user '{user_id}'.")
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting from cart: {e}", exc_info=True)

# Удаление вакансии из корзины (уменьшение количества вакансий)
async def orm_reduce_vacancy_in_cart(session: AsyncSession, user_id: int, vacancy_id: int) -> bool:
    try:
        query = select(Cart).where(Cart.user_id == user_id, Cart.vacancy_id == vacancy_id)
        cart = await session.execute(query)
        cart = cart.scalar()
        if not cart:
            return False
        else:
            await orm_delete_from_cart(session, user_id, vacancy_id)
            await session.commit()
            logger.info(f"Vacancy '{vacancy_id}' reduced in cart for user '{user_id}'.")
            return True
    except Exception as e:
        await session.rollback()
        logger.error(f"Error reducing vacancy in cart: {e}", exc_info=True)
        return False


######################## Работа с резюме #######################################

async def orm_save_resume(session: AsyncSession, user_id: int, vacancy_id: int, file_id: str, resume_text: str) -> Resume:
    try:
        # Создание новой записи в таблице Resume
        new_resume = Resume(
            user_id=user_id,
            vacancy_id=vacancy_id,
            file_id=file_id
        )
        session.add(new_resume)
        await session.commit()
        await session.refresh(new_resume)
        
        # Создание новой записи в таблице ResumeText
        new_resume_text = ResumeText(
            resume_id=new_resume.resume_id,
            resume_text=resume_text
        )
        session.add(new_resume_text)
        await session.commit()
        
        logger.info(f"Resume for user '{user_id}' and vacancy '{vacancy_id}' saved successfully.")
        return new_resume
    except Exception as e:
        await session.rollback()
        logger.error(f"Error saving resume for user '{user_id}' and vacancy '{vacancy_id}': {e}", exc_info=True)