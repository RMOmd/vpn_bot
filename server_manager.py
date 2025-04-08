#!/usr/bin/env python3

import json
import logging
import os
import shutil
from datetime import datetime, timedelta
import pytz
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Subscription, VPNServer
import uuid
import sys
from pytz import UTC
import asyncio
import aiohttp

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Загрузка конфигурации
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot.db")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def setup_database():
    Base.metadata.create_all(engine)
    return Session()

def cleanup_expired_subscriptions():
    session = Session()
    try:
        now = datetime.now(UTC)
        expired_subs = session.query(Subscription).filter(
            Subscription.end_date < now,
            Subscription.is_active == True
        ).all()
        
        for sub in expired_subs:
            sub.is_active = False
            print(f"Деактивирована подписка {sub.id} для пользователя {sub.user_id}")
        
        session.commit()
        print(f"Обработано {len(expired_subs)} истекших подписок")
        
    except Exception as e:
        print(f"Ошибка при очистке подписок: {e}")
        session.rollback()
    finally:
        session.close()

def check_server_status():
    session = Session()
    try:
        servers = session.query(VPNServer).all()
        for server in servers:
            # Здесь можно добавить проверку доступности сервера
            # Например, пинг или проверку порта
            print(f"Проверка сервера {server.name} ({server.host})")
            
    except Exception as e:
        print(f"Ошибка при проверке серверов: {e}")
    finally:
        session.close()

async def check_server_availability(server: VPNServer) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'http://{server.host}:{server.port}', timeout=5) as response:
                return response.status == 200
    except Exception as e:
        logger.error(f"Error checking server {server.host}: {str(e)}")
        return False

async def check_servers():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        servers = session.query(VPNServer).all()
        for server in servers:
            is_available = await check_server_availability(server)
            old_status = server.is_active
            server.is_active = is_available
            
            if old_status != is_available:
                logger.info(f"Server {server.host} status changed: active={is_available}")
                session.commit()
                
    except Exception as e:
        logger.error(f"Error in check_servers: {str(e)}")
    finally:
        session.close()

def check_subscriptions():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        current_time = datetime.now(UTC)
        expired_subs = session.query(Subscription).filter(
            Subscription.is_active == True,
            Subscription.end_date < current_time
        ).all()
        
        for sub in expired_subs:
            sub.is_active = False
            logger.info(f"Deactivated expired subscription for user {sub.user_id}")
        
        session.commit()
    except Exception as e:
        logger.error(f"Error in check_subscriptions: {str(e)}")
    finally:
        session.close()

async def main():
    logger.info("Starting VPN manager...")
    
    try:
        check_subscriptions()
        await check_servers()
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
    
    logger.info("VPN manager finished")

if __name__ == "__main__":
    asyncio.run(main()) 