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

# ---------------------------------------------------------------------------
# Prefix‑aware WSGI adapter
# ---------------------------------------------------------------------------

class PrefixedWSGIHandler(WSGIHandler):
    """Adapter that can *either* keep the URL prefix in PATH_INFO (keep_prefix=True)
    or strip it into SCRIPT_NAME (keep_prefix=False).

    keep_prefix=True   → Flask routes already include the prefix (e.g. '/app/<id>')
    keep_prefix=False  → Flask routes declared *without* the prefix (e.g. '/receipt')
    """

    def __init__(self, wsgi_app, prefix: str, *, keep_prefix: bool):
        super().__init__(wsgi_app)
        self._prefix = prefix.rstrip("/")
        self._keep = keep_prefix

    def _get_environ(self, request, body, content_length):
        env = super()._get_environ(request, body, content_length)
        path_info = request.match_info.get("path_info", "")  # '' or '/rest'

        if self._keep:
            # Keep prefix as part of the path; SCRIPT_NAME empty
            env["SCRIPT_NAME"] = ""
            env["PATH_INFO"] = f"{self._prefix}{path_info}" or "/"
        else:
            # Strip prefix into SCRIPT_NAME
            env["SCRIPT_NAME"] = self._prefix
            env["PATH_INFO"] = path_info or "/"
        return env

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

async def init_app() -> web.Application:
    app = await create_app()  # aiogram routes inside

    # ---- direct JSON endpoint ------------------------------------------------
    app.router.add_post("/api/answer_webapp_query", test_answer_webapp_query)

    # ---- import Flask --------------------------------------------------------
    from webapp.backend.server import app as flask_app

    def mount(prefix: str, *, keep: bool):
        h = PrefixedWSGIHandler(flask_app, prefix, keep_prefix=keep)
        app.router.add_route("*", f"{prefix}{{path_info:.*}}", h)

    # 1. Приложение чеков: маршруты вида '/app/<id>' → keep_prefix=True
    mount("/app", keep=True)

    # 2. Health: у вас, похоже, '/health' → keep_prefix=True
    mount("/health", keep=True)

    # 3. API: маршруты без /api в декораторе → keep_prefix=False
    mount("/api", keep=False)

    # 4. Test page и статика — тоже без префикса в декораторах
    mount("/test_webapp", keep=False)
    mount("/static", keep=False)

    return app          # ← ЭТОТ return должен быть!

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

#async def init_app():
#    """Инициализация и запуск объединенного приложения."""
#    
#    logger.info("Инициализация объединенного приложения...")
#    
#    # Создаем основное приложение с ботом
#    bot_app = await create_app()
#    
#    # Добавляем прямой API endpoint в aiohttp
#    logger.info("Добавляю API endpoint /api/answer_webapp_query")
#    bot_app.router.add_post('/api/answer_webapp_query', test_answer_webapp_query)
#    
#    # Импортируем Flask приложение
#    from webapp.backend.server import app as flask_app
#    
#    # Создаем WSGI handler для Flask
#    wsgi_handler = WSGIHandler(flask_app)
#    
#    # Обертка для логирования запросов и исправления путей
#    async def logged_wsgi_handler(request):
#        logger.debug(f"WSGI handler: {request.method} {request.path_qs}")
#        return await wsgi_handler(request)
#    
#    # Специальная обертка для маршрутов с префиксами
#    def prefixed_wsgi_handler(prefix):
#        # Создаем отдельный WSGIHandler с кастомной обработкой
#        class PrefixedWSGIHandler(WSGIHandler):
#            def __init__(self, wsgi_app, prefix):
#                super().__init__(wsgi_app)
#                self.prefix = prefix
#            
#            async def __call__(self, request):
#                # Восстанавливаем полный путь для Flask
#                original_path = request.path
#                path_info = request.match_info.get('path_info', '')
#                full_path = f"{self.prefix}/{path_info}" if path_info else self.prefix
#                
#                logger.debug(f"WSGI handler: {request.method} {original_path} -> {full_path}")
#                
#                # Получаем тело запроса
#                body = await request.read()
#                content_length = len(body)
#                
#                # Создаем environ с правильным путем
#                environ = self._get_environ(request, body, content_length)
#                environ['PATH_INFO'] = full_path
#                environ['REQUEST_URI'] = full_path
#                
#                # Запускаем WSGI приложение
#                return self.run_wsgi_app(environ, request)
#        
#        # Возвращаем экземпляр обработчика
#        return PrefixedWSGIHandler(flask_app, prefix)
#    
#    # Добавляем специфичные маршруты для WebApp
#    
#    # Тестовая страница WebApp
#    logger.info("Регистрирую роуты для /test_webapp")
#    bot_app.router.add_route('GET', '/test_webapp{path_info:/?}', prefixed_wsgi_handler('/test_webapp'))
#    bot_app.router.add_route('GET', '/test_webapp{path_info:/.*}', prefixed_wsgi_handler('/test_webapp'))
#    
#    # Основное приложение для работы с чеками
#    logger.info("Регистрирую роуты для /app/<message_id>")
#    bot_app.router.add_route('GET', '/app/{path_info:.*}', prefixed_wsgi_handler('/app'))
#    
#    # API маршруты - ВЫСОКИЙ ПРИОРИТЕТ
#    bot_app.router.add_route('*', '/api/{path_info:.*}', prefixed_wsgi_handler('/api'))
#    
#    # Утилитарные маршруты
#    bot_app.router.add_route('*', '/health{path_info:.*}', prefixed_wsgi_handler('/health'))
#    
#
#    
#    # Корневая страница и fallback маршруты - САМЫЙ НИЗКИЙ ПРИОРИТЕТ
#    bot_app.router.add_route('GET', '/{path_info:/?}', logged_wsgi_handler)
#    bot_app.router.add_route('GET', '/{path_info:.*}', logged_wsgi_handler)
#    
#    logger.info("Все роуты зарегистрированы")
#    
#    logger.info("Объединенный сервер (Telegram Bot + WebApp) готов к запуску")
#    logger.info(f"Webhook path защищен от перехвата Flask маршрутами")
#    return bot_app
#
#if __name__ == '__main__':
#    port = int(os.environ.get('PORT', 8000))
#    
#    logger.info(f"Запуск объединенного сервера на порту {port}")
#    logger.info("Включает в себя:")
#    logger.info("- Telegram Bot (webhook)")
#    logger.info("- WebApp (Flask)")
#    
#    # Создаем и запускаем приложение
#    web.run_app(
#        init_app(),
#        host='0.0.0.0',
#        port=port
#    ) 

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    logger.info("Starting unified server on port %s", port)
    web.run_app(init_app(), host="0.0.0.0", port=port)