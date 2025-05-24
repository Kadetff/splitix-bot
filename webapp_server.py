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
    
    # Обертка для логирования запросов
    async def logged_wsgi_handler(request):
        logger.critical(f"!!!! WSGI HANDLER ПОЛУЧИЛ ЗАПРОС: {request.method} {request.path_qs} !!!!")
        logger.critical(f"!!!! MATCH INFO: {request.match_info} !!!!")
        return await wsgi_handler(request)
    
    # Добавляем специфичные маршруты для WebApp
    
    # Тестовая страница WebApp (ВЫСОКИЙ ПРИОРИТЕТ - ПЕРВАЯ!)
    logger.critical("!!!! РЕГИСТРИРУЮ РОУТЫ ДЛЯ /test_webapp !!!!")
    bot_app.router.add_route('GET', '/test_webapp{path_info:/?}', logged_wsgi_handler)
    bot_app.router.add_route('GET', '/test_webapp{path_info:/.*}', logged_wsgi_handler)
    
    # API маршруты
    bot_app.router.add_route('*', '/api/{path_info:.*}', logged_wsgi_handler)
    
    # Утилитарные маршруты
    bot_app.router.add_route('GET', '/health{path_info:.*}', logged_wsgi_handler)
    bot_app.router.add_route('*', '/maintenance/{path_info:.*}', logged_wsgi_handler)
    
    # Маршруты для чеков (числовые ID)
    bot_app.router.add_route('GET', '/{message_id:[0-9]+}{path_info:.*}', logged_wsgi_handler)
    
    # Корневая страница (ТОЛЬКО корень)
    bot_app.router.add_route('GET', '/', logged_wsgi_handler)
    
    logger.critical("!!!! УБРАН УНИВЕРСАЛЬНЫЙ CATCH-ALL РОУТ - ТОЛЬКО КОНКРЕТНЫЕ РОУТЫ !!!!")
    
    logger.critical("!!!! ВСЕ РОУТЫ ЗАРЕГИСТРИРОВАНЫ !!!!")
    
    logger.info("Объединенный сервер (Telegram Bot + WebApp) готов к запуску")
    logger.info(f"Webhook path защищен от перехвата Flask маршрутами")
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