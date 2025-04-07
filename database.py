from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Float
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
    
    telegram_id = Column(Integer, primary_key=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    is_active = Column(Boolean, default=False)
    trial_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    subscriptions = relationship("Subscription", backref="user", lazy="dynamic")

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
    
    def has_active_paid_subscription(self):
        """Проверить наличие активной платной подписки"""
        active_sub = self.get_active_subscription()
        return active_sub and not active_sub.is_trial

class Subscription(Base):
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.telegram_id'))
    start_date = Column(DateTime, default=lambda: datetime.now(UTC))
    end_date = Column(DateTime)
    price = Column(Float, default=0)
    is_trial = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    payment_type = Column(String)  # trial, money, stars
    stars_paid = Column(Integer, default=0)  # Количество потраченных звезд

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

def get_or_create_user(telegram_id, username, first_name, last_name, fingerprint):
    session = Session()
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            fingerprint=fingerprint
        )
        session.add(user)
        session.commit()
    
    session.close()
    return user

def create_trial_subscription(user_id, telegram_id):
    session = Session()
    user = session.query(User).filter_by(id=user_id).first()
    
    # Специальная проверка для разработчика
    if telegram_id == DEVELOPER_ID:
        end_date = datetime.now(UTC) + timedelta(days=7)
        subscription = Subscription(
            user_id=user.id,
            end_date=end_date,
            subscription_type='trial',
            price=0,
            payment_method='trial'
        )
        session.add(subscription)
        session.commit()
        session.close()
        return True
    
    if user and not user.trial_used:
        end_date = datetime.now(UTC) + timedelta(days=7)
        user.trial_used = True
        user.trial_end_date = end_date
        
        subscription = Subscription(
            user_id=user.id,
            end_date=end_date,
            subscription_type='trial',
            price=0,
            payment_method='trial'
        )
        
        session.add(subscription)
        session.commit()
        session.close()
        return True
    
    session.close()
    return False 