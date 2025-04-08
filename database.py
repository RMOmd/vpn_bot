from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Float, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta, UTC
import os
from dotenv import load_dotenv
from config import DEVELOPER_ID

# Загрузка переменных окружения
load_dotenv()

Base = declarative_base()
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///vpn_bot.db')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=False)
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")

    def get_active_subscription(self):
        """Получить активную подписку пользователя"""
        now = datetime.now(UTC)
        return self.subscriptions.filter(
            Subscription.is_active == True,
            Subscription.start_date <= now,
            Subscription.end_date >= now
        ).first()
    
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
            session = Session()
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
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id'))
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)
    price = Column(Float)
    is_trial = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    payment_type = Column(String)
    stars_paid = Column(Integer, default=0)
    
    user = relationship("User", back_populates="subscriptions")

    def is_expired(self):
        """Проверить, истекла ли подписка"""
        return datetime.now(UTC) > self.end_date

def init_db():
    """Инициализация базы данных"""
    Base.metadata.create_all(engine)
    
    # Создаем сессию
    session = Session()
    
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
    session.close()

def get_or_create_user(telegram_user, session=None):
    """Получить или создать пользователя
    
    Args:
        telegram_user: Объект пользователя Telegram
        session: Существующая сессия SQLAlchemy (опционально)
    """
    if session is None:
        session = Session()
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
        session = Session()
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