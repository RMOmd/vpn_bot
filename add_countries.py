from database import Session, Country

def add_initial_countries():
    countries = [
        ("Россия", "RU", True),
        ("Германия", "DE", True),
        ("Нидерланды", "NL", True),
        ("США", "US", True),
        ("Сингапур", "SG", True)
    ]
    
    session = Session()
    try:
        # Проверяем существующие страны
        existing_countries = session.query(Country).all()
        if existing_countries:
            print("Уже есть страны в базе данных:")
            for country in existing_countries:
                print(f"- {country.name} ({country.code})")
            return
        
        # Добавляем новые страны
        for name, code, is_active in countries:
            country = Country(
                name=name,
                code=code,
                is_active=is_active
            )
            session.add(country)
        
        session.commit()
        print("Страны успешно добавлены:")
        for name, code, _ in countries:
            print(f"- {name} ({code})")
            
    except Exception as e:
        print(f"Ошибка при добавлении стран: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    add_initial_countries() 