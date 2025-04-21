from database import Base, engine
from add_initial_countries import add_initial_countries

def init_database():
    # Создаем все таблицы
    Base.metadata.create_all(engine)
    print("✅ Таблицы созданы")
    
    # Добавляем начальные данные
    add_initial_countries()
    print("✅ Начальные данные добавлены")

if __name__ == "__main__":
    init_database() 