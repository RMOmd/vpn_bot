from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Float, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, scoped_session, joinedload
from datetime import datetime, timedelta, UTC
import os
from dotenv import load_dotenv
from config import DEVELOPER_ID, DATABASE_URL

# Загрузка переменных окружения
load_dotenv()

Base = declarative_base()
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///vpn_bot.db')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Создаем движок базы данных
engine = create_engine(DATABASE_URL)

# Создаем фабрику сессий
Session = sessionmaker(bind=engine)

def get_session():
    """Создает новую сессию базы данных"""
    return Session()

class Country(Base):
    """Модель страны"""
    __tablename__ = 'countries'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    flag = Column(String, nullable=False)  # Эмодзи флага
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(UTC))
    
    # Связь с подписками
    subscriptions = relationship("Subscription", back_populates="country")
    # Связь с серверами
    servers = relationship("VPNServer", back_populates="country")

class User(Base):
    __tablename__ = 'users'
    
    telegram_id = Column(Integer, primary_key=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    created_at = Column(DateTime, default=datetime.now(UTC))
    is_active = Column(Boolean, default=False)
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")

    def get_active_subscription(self):
        """Получить активную подписку пользователя"""
        session = get_session()
        try:
            now = datetime.now(UTC)
            return session.query(Subscription).options(
                joinedload(Subscription.server)
            ).filter(
                Subscription.user_id == self.telegram_id,
                Subscription.is_active == True,
                Subscription.start_date <= now,
                Subscription.end_date >= now
            ).first()
        finally:
            session.close()
    
    def get_days_left(self):
        """Получить количество оставшихся дней подписки"""
        active_sub = self.get_active_subscription()
        if not active_sub:
            return 0
            
        # Убедимся, что обе даты имеют временную зону UTC
        if active_sub.end_date.tzinfo is None:
            end_date = active_sub.end_date.replace(tzinfo=UTC)
        else:
            end_date = active_sub.end_date
            
        days_left = (end_date - datetime.now(UTC)).days
        return max(0, days_left)
    
    def can_use_trial(self):
        """Проверить возможность использования пробного периода"""
        return not self.trial_used and not self.get_active_subscription()
    
    def has_used_trial(self, session=None) -> bool:
        """Проверяет, использовал ли пользователь пробный период
        
        Args:
            session: Существующая сессия SQLAlchemy (опционально)
        """
        if session is None:
            session = get_session()
            should_close = True
        else:
            should_close = False
            
        try:
            trial_sub = session.query(Subscription).filter(
                Subscription.user_id == self.telegram_id,
                Subscription.is_trial == True
            ).first()
            return trial_sub is not None
        finally:
            if should_close:
                session.close()

    def has_active_paid_subscription(self):
        """Проверить наличие активной платной подписки"""
        active_sub = self.get_active_subscription()
        return active_sub and not active_sub.is_trial

class Subscription(Base):
    """Модель подписки"""
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.telegram_id'))
    country_id = Column(Integer, ForeignKey('countries.id'))
    server_id = Column(Integer, ForeignKey('vpn_servers.id'))
    start_date = Column(DateTime, default=datetime.now(UTC))
    end_date = Column(DateTime)
    price = Column(Float)
    is_trial = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    payment_type = Column(String)  # stars, crypto, etc.
    stars_paid = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now(UTC))
    
    # Связи
    user = relationship("User", back_populates="subscriptions")
    country = relationship("Country", back_populates="subscriptions")
    server = relationship("VPNServer", back_populates="subscriptions")

    def is_expired(self):
        """Проверить, истекла ли подписка"""
        return datetime.now(UTC) > self.end_date

class VPNServer(Base):
    """Модель VPN сервера"""
    __tablename__ = 'vpn_servers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    password = Column(String, nullable=False)
    country_id = Column(Integer, ForeignKey('countries.id'), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(UTC))
    
    # Связь с подписками
    subscriptions = relationship("Subscription", back_populates="server")
    # Связь со страной
    country = relationship("Country", back_populates="servers")

def init_db():
    """Инициализация базы данных"""
    # Создаем все таблицы
    Base.metadata.create_all(engine)
    
    # Создаем сессию
    session = get_session()
    
    try:
        # Добавляем администраторов
        for admin_id in ADMIN_IDS:
            existing_admin = session.query(User).filter_by(telegram_id=admin_id).first()
            if not existing_admin:
                admin = User(
                    telegram_id=admin_id,
                    is_active=True
                )
                session.add(admin)
            else:
                # Обновляем статус существующего пользователя
                existing_admin.is_active = True
        
        # Сохраняем изменения
        session.commit()
    finally:
        session.close()

def get_or_create_user(telegram_user, session=None):
    """Получить или создать пользователя
    
    Args:
        telegram_user: Объект пользователя Telegram
        session: Существующая сессия SQLAlchemy (опционально)
    """
    if session is None:
        session = get_session()
        should_close = True
    else:
        should_close = False
        
    try:
        user = session.query(User).filter_by(telegram_id=telegram_user.id).first()
        if not user:
            user = User(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                created_at=datetime.now(UTC)
            )
            session.add(user)
            session.commit()
        else:
            # Обновляем данные существующего пользователя
            user.username = telegram_user.username
            user.first_name = telegram_user.first_name
            user.last_name = telegram_user.last_name
            session.commit()
        return user
    finally:
        if should_close:
            session.close()

def create_trial_subscription(user, session=None):
    """Создать пробную подписку для пользователя
    
    Args:
        user: Объект пользователя
        session: Существующая сессия SQLAlchemy (опционально)
    """
    if session is None:
        session = get_session()
        should_close = True
    else:
        should_close = False
        
    try:
        # Проверяем, не использовал ли пользователь уже пробный период
        existing_trial = session.query(Subscription).filter(
            Subscription.user_id == user.telegram_id,
            Subscription.is_trial == True
        ).first()
        
        if existing_trial:
            return None
            
        subscription = Subscription(
            user_id=user.telegram_id,
            start_date=datetime.now(UTC),
            end_date=datetime.now(UTC) + timedelta(days=7),
            price=0,
            is_trial=True,
            is_active=True,
            payment_type="trial"
        )
        session.add(subscription)
        session.commit()
        return subscription
    finally:
        if should_close:
            session.close()

def delete_user(telegram_id: int, session=None):
    """Удалить пользователя и все его подписки
    
    Args:
        telegram_id: Telegram ID пользователя
        session: Существующая сессия SQLAlchemy (опционально)
    
    Returns:
        bool: True если пользователь был удален, False если пользователь не найден
    """
    if session is None:
        session = get_session()
        should_close = True
    else:
        should_close = False
        
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            # Удаляем все подписки пользователя
            session.query(Subscription).filter_by(user_id=telegram_id).delete()
            # Удаляем самого пользователя
            session.delete(user)
            session.commit()
            return True
        return False
    finally:
        if should_close:
            session.close()

def get_active_subscription(user_id: int, session) -> Subscription:
    """Получение активной подписки пользователя"""
    return session.query(Subscription).filter_by(
        user_id=user_id,
        is_active=True
    ).first()

def deactivate_subscription(subscription: Subscription, session):
    """Деактивация подписки"""
    subscription.is_active = False
    session.commit() 