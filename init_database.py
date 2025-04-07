from database import Base, engine, Session, User, Subscription
from config import ADMIN_IDS

def init_database():
    # Удаляем все таблицы
    Base.metadata.drop_all(engine)
    
    # Создаем таблицы заново
    Base.metadata.create_all(engine)
    
    # Создаем сессию
    session = Session()
    
    # Добавляем администраторов
    for admin_id in ADMIN_IDS:
        admin = User(
            telegram_id=admin_id,
            is_active=True
        )
        session.add(admin)
    
    # Сохраняем изменения
    session.commit()
    session.close()

if __name__ == '__main__':
    init_database()
    print("База данных успешно инициализирована!") 