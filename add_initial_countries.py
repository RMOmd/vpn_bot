from database import Session, Country

def add_initial_countries():
    countries = [
        ("Россия", "🇷🇺", True),
        ("Германия", "🇩🇪", True),
        ("Нидерланды", "🇳🇱", True),
        ("США", "🇺🇸", True),
        ("Сингапур", "🇸🇬", True)
    ]
    
    session = Session()
    try:
        # Проверяем существующие страны
        existing_countries = session.query(Country).all()
        if existing_countries:
            print("Уже есть страны в базе данных:")
            for country in existing_countries:
                print(f"- {country.name} ({country.flag})")
            return
        
        # Добавляем новые страны
        for name, flag, is_active in countries:
            country = Country(
                name=name,
                flag=flag,
                is_active=is_active
            )
            session.add(country)
        
        session.commit()
        print("Страны успешно добавлены:")
        for name, flag, _ in countries:
            print(f"- {name} {flag}")
            
    except Exception as e:
        print(f"Ошибка при добавлении стран: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    add_initial_countries() 