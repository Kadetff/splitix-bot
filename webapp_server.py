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

def escape_markdown(text):
    """Экранирует специальные символы для Markdown"""
    if not isinstance(text, str):
        text = str(text)
    
    # Экранируем только критически важные символы Markdown
    # Убираем апострофы, точки и другие символы, которые не ломают разметку
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

async def test_answer_webapp_query(request):
    """Endpoint для обработки Inline WebApp данных через answerWebAppQuery"""
    logger.info("Получен запрос к /api/answer_webapp_query")
    
    try:
        if request.content_type != 'application/json':
            return web.json_response({"error": "Expected JSON data"}, status=400)
            
        data = await request.json()
        query_id = data.get('query_id')
        result_data = data.get('data', {})
        
        logger.info(f"Получены данные: query_id={query_id}, data={result_data}")
        
        if not query_id:
            return web.json_response({"error": "query_id is required"}, status=400)
        
        # Получаем bot token
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            logger.error("TELEGRAM_BOT_TOKEN не найден")
            return web.json_response({"error": "Bot token not configured"}, status=500)
        
        # Извлекаем данные для формирования сообщения
        payload = result_data.get('payload', 'Нет данных')
        button_type = result_data.get('button_type', 'inline')
        
        # Формируем сообщение БЕЗ Markdown для Inline-кнопок (избегаем проблем с парсингом)
        if isinstance(payload, str) and payload.strip() == "Привет":
            message_text = f"🎉 УСПЕХ! Бот получил сообщение от WebApp!\n\n💬 Сообщение: {payload}\n🔵 Тип кнопки: Inline\n⏰ Время: {time.strftime('%H:%M:%S')}"
        else:
            message_text = f"✅ Данные от WebApp получены!\n\n🔵 Тип кнопки: Inline\n"
            
            if isinstance(payload, str):
                message_text += f"💬 Сообщение: {payload}\n"
            elif isinstance(payload, dict):
                if 'message' in payload:
                    message_text += f"💬 Сообщение: {payload['message']}\n"
                if 'items' in payload:
                    # Простой текст без всякой разметки
                    items_str = str(payload['items'])
                    message_text += f"📦 Элементы: {items_str}\n"
                if 'count' in payload:
                    message_text += f"🔢 Количество: {payload['count']}\n"
            
            message_text += f"⏰ Время: {time.strftime('%H:%M:%S')}\n🔧 Источник: test_webapp"
        
        # Формируем данные для answerWebAppQuery
        telegram_data = {
            "web_app_query_id": query_id,
            "result": {
                "type": "article",
                "id": str(int(time.time())),
                "title": "✅ Данные получены",
                "description": f"WebApp: {payload if isinstance(payload, str) else 'JSON данные'}",
                "input_message_content": {
                    "message_text": message_text
                    # Полностью убираем parse_mode
                }
            }
        }
        
        logger.debug(f"Отправляю в Telegram API: {json.dumps(telegram_data, ensure_ascii=False, indent=2)}")
        
        # Отправляем answerWebAppQuery
        telegram_url = f"https://api.telegram.org/bot{bot_token}/answerWebAppQuery"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(telegram_url, json=telegram_data, timeout=10) as response:
                response_text = await response.text()
                logger.debug(f"Telegram API response: status={response.status}, body={response_text}")
                
                if response.status == 200:
                    telegram_result = await response.json()
                    if telegram_result.get('ok'):
                        logger.info("Успешно отправлен answerWebAppQuery")
                        return web.json_response({"success": True, "message": "WebApp query answered successfully"})
                    else:
                        error_desc = telegram_result.get('description', 'Unknown error')
                        logger.error(f"Telegram API error: {error_desc}")
                        return web.json_response({"error": f"Telegram API error: {error_desc}"}, status=500)
                else:
                    logger.error(f"HTTP error from Telegram API: {response.status}")
                    logger.error(f"Response body: {response_text}")
                    return web.json_response({"error": f"HTTP error: {response.status}"}, status=500)
                    
    except Exception as e:
        logger.error(f"Ошибка в test_answer_webapp_query: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def init_app():
    """Инициализация и запуск объединенного приложения."""
    
    logger.info("Инициализация объединенного приложения...")
    
    # Создаем основное приложение с ботом
    bot_app = await create_app()
    
    # Добавляем прямой API endpoint в aiohttp
    logger.info("Добавляю API endpoint /api/answer_webapp_query")
    bot_app.router.add_post('/api/answer_webapp_query', test_answer_webapp_query)
    
    # Импортируем Flask приложение
    from webapp.backend.server import app as flask_app
    
    # Создаем WSGI handler для Flask
    wsgi_handler = WSGIHandler(flask_app)
    
    # Обертка для логирования запросов
    async def logged_wsgi_handler(request):
        logger.debug(f"WSGI handler: {request.method} {request.path_qs}")
        return await wsgi_handler(request)
    
    # Добавляем специфичные маршруты для WebApp
    
    # Тестовая страница WebApp
    logger.info("Регистрирую роуты для /test_webapp")
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
    
    logger.info("Все роуты зарегистрированы")
    
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