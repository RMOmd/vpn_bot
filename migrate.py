from database import Base, engine, Session, Country, add_country

def migrate():
    """Выполнить миграцию базы данных"""
    # Создаем новые таблицы
    Base.metadata.create_all(engine)
    
    # Добавляем начальные страны
    session = Session()
    try:
        # Проверяем, есть ли уже страны в базе
        if session.query(Country).count() == 0:
            # Добавляем начальные страны
            countries = [
                ("Германия", "DE"),
                ("Латвия", "LV"),
                ("Нидерланды", "NL"),
                ("США", "US")
            ]
            
            for name, code in countries:
                add_country(name, code, session)
            
            print("✅ Начальные страны добавлены")
        else:
            print("ℹ️ Страны уже существуют в базе")
            
    finally:
        session.close()
        
    print("✅ Миграция завершена успешно")

if __name__ == "__main__":
    migrate() 