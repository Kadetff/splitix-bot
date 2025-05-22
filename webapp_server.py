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
    
    # Создаем основное приложение с ботом
    bot_app = await create_app()
    
    # Импортируем Flask приложение
    from webapp.backend.server import app as flask_app
    
    # Создаем WSGI handler для Flask
    wsgi_handler = WSGIHandler(flask_app)
    
    # Добавляем маршруты для WebApp
    bot_app.router.add_route('*', '/', wsgi_handler)
    bot_app.router.add_route('*', '/test_webapp', wsgi_handler)
    bot_app.router.add_route('*', '/api/{path:.*}', wsgi_handler)
    bot_app.router.add_route('*', '/health', wsgi_handler)
    bot_app.router.add_route('*', '/maintenance/{path:.*}', wsgi_handler)
    bot_app.router.add_route('*', '/{message_id:[0-9]+}', wsgi_handler)
    
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