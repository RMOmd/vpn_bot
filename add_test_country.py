from database import Session, Country

def add_test_country():
    session = Session()
    try:
        # Проверяем, есть ли уже страны в базе данных
        existing_countries = session.query(Country).all()
        print(f"Текущее количество стран в базе: {len(existing_countries)}")
        
        # Создаем тестовую страну
        country = Country(
            name="Россия",
            flag="🇷🇺",
            is_active=True
        )
        
        session.add(country)
        session.commit()
        print(f"✅ Добавлена тестовая страна: {country.name} {country.flag}")
        
    except Exception as e:
        print(f"❌ Ошибка при добавлении страны: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    add_test_country() 