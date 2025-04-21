from database import Session, Country, VPNServer

def add_test_server():
    session = Session()
    try:
        # Получаем первую активную страну
        country = session.query(Country).filter_by(is_active=True).first()
        if not country:
            print("Нет активных стран в базе данных")
            return
            
        # Проверяем, есть ли уже сервер для этой страны
        existing_server = session.query(VPNServer).filter_by(
            country_id=country.id,
            is_active=True
        ).first()
        
        if existing_server:
            print(f"Сервер для страны {country.name} уже существует")
            return
            
        # Создаем тестовый сервер
        server = VPNServer(
            name=f"Тестовый сервер {country.name}",
            host="test.server.com",
            port=443,
            country_id=country.id,
            is_active=True
        )
        session.add(server)
        session.commit()
        print(f"✅ Добавлен тестовый сервер для страны {country.name}")
        
    except Exception as e:
        print(f"Ошибка при добавлении сервера: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    add_test_server() 