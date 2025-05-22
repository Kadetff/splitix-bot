#!/usr/bin/env python3
"""
Объединенный сервер для Telegram Bot и WebApp на Heroku.
Запускает webhook для бота и Flask для WebApp на одном порту.
"""
import asyncio
import logging
import os
from aiohttp import web
from aiohttp_wsgi import WSGIHandler
from main import create_app

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def init_app():
    """Инициализация и запуск объединенного приложения."""
    
    logger.info("Инициализация объединенного приложения...")
    
    # Создаем основное приложение с ботом
    bot_app = await create_app()
    
    # Импортируем Flask приложение
    from webapp.backend.server import app as flask_app
    
    # Создаем WSGI handler для Flask
    wsgi_handler = WSGIHandler(flask_app)
    
    # Добавляем специфичные маршруты для WebApp (чтобы не перехватить webhook)
    # Корневая страница
    bot_app.router.add_route('GET', '/', wsgi_handler)
    bot_app.router.add_route('GET', '/{path_info}', wsgi_handler)
    
    # Тестовая страница WebApp  
    bot_app.router.add_route('GET', '/test_webapp{path_info:.*}', wsgi_handler)
    
    # API маршруты
    bot_app.router.add_route('*', '/api/{path_info:.*}', wsgi_handler)
    
    # Маршруты для чеков (числовые ID)
    bot_app.router.add_route('GET', '/{message_id:[0-9]+}{path_info:.*}', wsgi_handler)
    
    # Утилитарные маршруты
    bot_app.router.add_route('GET', '/health{path_info:.*}', wsgi_handler)
    bot_app.router.add_route('*', '/maintenance/{path_info:.*}', wsgi_handler)
    
    logger.info("Объединенный сервер (Telegram Bot + WebApp) готов к запуску")
    return bot_app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    
    logger.info(f"Запуск объединенного сервера на порту {port}")
    logger.info("Включает в себя:")
    logger.info("- Telegram Bot (webhook)")
    logger.info("- WebApp (Flask)")
    
    # Создаем и запускаем приложение
    web.run_app(
        init_app(),
        host='0.0.0.0',
        port=port
    ) 