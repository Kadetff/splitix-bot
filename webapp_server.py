#!/usr/bin/env python3
"""
Объединенный сервер для Telegram Bot и WebApp на Heroku.
Запускает webhook для бота и Flask для WebApp на одном порту.
"""
import asyncio
import logging
import os
import json
import aiohttp
import time
from aiohttp import web
from aiohttp_wsgi import WSGIHandler
from main import create_app

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_answer_webapp_query(request):
    """Тестовый endpoint для answerWebAppQuery в aiohttp"""
    logger.critical(f"!!!! ТЕСТОВЫЙ ENDPOINT /api/answer_webapp_query ПОЛУЧИЛ ЗАПРОС !!!!")
    
    try:
        if request.content_type != 'application/json':
            return web.json_response({"error": "Expected JSON data"}, status=400)
            
        data = await request.json()
        query_id = data.get('query_id')
        result_data = data.get('data', {})
        title = data.get('title', 'Данные от WebApp')
        description = data.get('description', 'Результат выбора товаров')
        
        logger.critical(f"!!!! ПОЛУЧЕНЫ ДАННЫЕ: query_id={query_id}, data={result_data} !!!!")
        
        if not query_id:
            return web.json_response({"error": "query_id is required"}, status=400)
        
        # Здесь должен быть вызов к Telegram Bot API
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            logger.error("TELEGRAM_BOT_TOKEN не найден")
            return web.json_response({"error": "Bot token not configured"}, status=500)
        
        # Формируем данные для answerWebAppQuery
        telegram_data = {
            "web_app_query_id": query_id,
            "result": {
                "type": "article",
                "id": str(int(time.time())),  # Простой timestamp как ID
                "title": title,
                "description": description,
                "input_message_content": {
                    "message_text": f"✅ **Данные от WebApp получены (aiohttp)!**\n\n📱 **Источник**: Inline-кнопка\n📊 **Выбрано**: {len(result_data.get('selected_items', {})) if 'selected_items' in result_data else 'N/A'}\n⏰ **Время**: {description}"
                }
            }
        }
        
        # Отправляем запрос к Telegram Bot API
        telegram_url = f"https://api.telegram.org/bot{bot_token}/answerWebAppQuery"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(telegram_url, json=telegram_data, timeout=10) as response:
                if response.status == 200:
                    telegram_result = await response.json()
                    if telegram_result.get('ok'):
                        logger.critical(f"!!!! УСПЕХ answerWebAppQuery через aiohttp: {query_id} !!!!")
                        return web.json_response({"success": True, "message": "WebApp query answered successfully"})
                    else:
                        error_desc = telegram_result.get('description', 'Unknown error')
                        logger.error(f"Telegram API error: {error_desc}")
                        return web.json_response({"error": f"Telegram API error: {error_desc}"}, status=500)
                else:
                    logger.error(f"HTTP error from Telegram API: {response.status}")
                    return web.json_response({"error": f"HTTP error: {response.status}"}, status=500)
                    
    except Exception as e:
        logger.error(f"Ошибка в test_answer_webapp_query: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def init_app():
    """Инициализация и запуск объединенного приложения."""
    
    logger.info("Инициализация объединенного приложения...")
    
    # Создаем основное приложение с ботом
    bot_app = await create_app()
    
    # ДОБАВЛЯЕМ ПРЯМОЙ API ENDPOINT В AIOHTTP (ВЫСШИЙ ПРИОРИТЕТ)
    logger.critical("!!!! ДОБАВЛЯЮ ПРЯМОЙ API ENDPOINT /api/answer_webapp_query В AIOHTTP !!!!")
    bot_app.router.add_post('/api/answer_webapp_query', test_answer_webapp_query)
    
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
    
    # API маршруты (остальные API кроме answer_webapp_query)
    bot_app.router.add_route('*', '/api/receipt/{path_info:.*}', logged_wsgi_handler)
    bot_app.router.add_route('*', '/api/selection/{path_info:.*}', logged_wsgi_handler)
    
    # Утилитарные маршруты
    bot_app.router.add_route('GET', '/health{path_info:.*}', logged_wsgi_handler)
    bot_app.router.add_route('*', '/maintenance/{path_info:.*}', logged_wsgi_handler)
    
    # Маршруты для чеков (числовые ID)
    bot_app.router.add_route('GET', '/{message_id:[0-9]+}{path_info:.*}', logged_wsgi_handler)
    
    # Корневая страница (ТОЛЬКО корень)
    bot_app.router.add_route('GET', '/{path_info:/?}', logged_wsgi_handler)
    
    logger.critical("!!!! ПРЯМОЙ API ENDPOINT ДОБАВЛЕН С ВЫСШИМ ПРИОРИТЕТОМ !!!!")
    
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