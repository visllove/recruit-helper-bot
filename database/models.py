from sqlalchemy import DateTime, Float, String, Text, func, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Класс, наследующийся от класса для таблиц, определенного в SQLAlchemy
class Base(DeclarativeBase):
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())  

# Таблица Banner для отображения данных с меню для пользователей по команде /start
class Banner(Base):
    __tablename__ = 'banner'
    banner_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(20), unique=True)
    image: Mapped[str] = mapped_column(String(150), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

class User(Base):
    __tablename__ = 'user'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(unique=True) # Telegram user id
    first_name: Mapped[str] = mapped_column(String(50), nullable=True)
    last_name: Mapped[str] = mapped_column(String(50), nullable=True)
    phone: Mapped[str] = mapped_column(String(15), nullable=True)

    carts: Mapped[list['Cart']] = relationship('Cart', back_populates='user')
    resumes: Mapped[list['Resume']] = relationship('Resume', back_populates='user')

class Cart(Base):
    __tablename__ = 'cart'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.user_id', ondelete='CASCADE'), nullable=False)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey('vacancy.vacancy_id', ondelete='CASCADE'), nullable=False)

    user: Mapped['User'] = relationship('User', back_populates='carts')
    vacancy: Mapped['Vacancy'] = relationship('Vacancy', back_populates='cart')

# Таблица "Вакансии", содержит вакансии, добавленные администратором
class Vacancy(Base):
    __tablename__ = 'vacancy'
    vacancy_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Нельзя удалить категорию, пока есть вакансии, относящиеся к ней
    category_id: Mapped[int] = mapped_column(ForeignKey('category.category_id', ondelete='CASCADE'), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[str] = mapped_column(Text, nullable=False)
    image: Mapped[str] = mapped_column(String, nullable=True)
    
    cart: Mapped[list['Cart']] = relationship('Cart', back_populates='vacancy')
    resumes: Mapped[list['Resume']] = relationship('Resume', back_populates='vacancy')
    category: Mapped['Category'] = relationship('Category', back_populates='vacancies')

# Таблица "Резюме", содержащая резюме пользователей
class Resume(Base):
    __tablename__ = 'resume'
    resume_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.user_id', ondelete='CASCADE'), nullable=False) # id пользователя в Telegram
    vacancy_id: Mapped[int] = mapped_column(ForeignKey('vacancy.vacancy_id', ondelete='CASCADE'), nullable=False)
    file_id: Mapped[str] = mapped_column(nullable=False) # id pdf-файла для отправки текста AI
    date_receipt: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    vacancy: Mapped['Vacancy'] = relationship('Vacancy', back_populates='resumes')
    user: Mapped['User'] = relationship('User', back_populates='resumes')
    resume_text: Mapped['ResumeText'] = relationship('ResumeText', back_populates='resume')

# Таблица "Текст резюме" содержит преобразованный из pdf текст отправленных пользователями резюме
class ResumeText(Base):
    __tablename__ = 'resume_text'
    text_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey('resume.resume_id', ondelete='CASCADE'), nullable=False)
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)

    resume: Mapped['Resume'] = relationship('Resume', back_populates='resume_text')

# Таблица "Категории" с информацией о категориях вакансий
class Category(Base):
    __tablename__ = 'category'

    category_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    
    vacancies: Mapped[list['Vacancy']] = relationship('Vacancy', back_populates='category')

