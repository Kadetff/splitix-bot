import asyncio
import logging
import os
from typing import Any
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from config.settings import TELEGRAM_BOT_TOKEN, LOG_LEVEL
from handlers import photo, callbacks, commands, webapp, inline

# Настраиваем логирование
logging.basicConfig(
    level=logging.DEBUG if LOG_LEVEL == "DEBUG" else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Словарь для хранения состояния (items и их счетчики) для каждого сообщения с клавиатурой
message_states: dict[int, dict[str, Any]] = {}

# Экспорт message_states для использования в обработчиках
callbacks.message_states = message_states
photo.message_states = message_states

# Конфигурация webhook
HEROKU_APP_NAME = os.getenv('HEROKU_APP_NAME', 'splitix-bot-69642ff6c071')
WEBHOOK_HOST = f"https://{HEROKU_APP_NAME}.herokuapp.com"
WEBHOOK_PATH = f"/bot/{TELEGRAM_BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

async def on_startup(bot: Bot) -> None:
    """Настройка webhook при запуске."""
    logger.info(f"Настройка webhook: {WEBHOOK_URL}")
    await bot.set_webhook(
        url=WEBHOOK_URL,
        allowed_updates=["message", "callback_query", "inline_query", "chosen_inline_result"]
    )
    logger.info("Webhook установлен успешно")

async def on_shutdown(bot: Bot) -> None:
    """Удаление webhook при остановке."""
    logger.info("Удаление webhook...")
    await bot.delete_webhook()
    logger.info("Webhook удален")

async def create_bot_app():
    """Создание приложения бота."""
    logger.info(f"Бот запускается в webhook режиме...")
    logger.info(f"Уровень логирования: {LOG_LEVEL}")
    
    # Инициализируем бота и диспетчер
    storage = MemoryStorage()
    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=storage)
    
    # Регистрируем команды бота
    await register_commands(bot)
    
    # Низкоуровневый обработчик ВСЕХ входящих обновлений для отладки
    @dp.update.outer_middleware()
    async def raw_update_logger(handler, event, data):
        logger.critical(f"!!!! RAW UPDATE RECEIVED BY DISPATCHER !!!! Type: {type(event)}")
        logger.critical(f"Raw event data: {event.model_dump_json(indent=2) if hasattr(event, 'model_dump_json') else str(event)}")
        
        # Специальная проверка для сообщений
        if hasattr(event, 'message') and event.message:
            msg = event.message
            logger.critical(f"!!!! MESSAGE DETAILS !!!! content_type: {msg.content_type}")
            if hasattr(msg, 'web_app_data') and msg.web_app_data:
                logger.critical(f"!!!! WEB_APP_DATA FOUND !!!! data: {msg.web_app_data.data}")
            else:
                logger.critical(f"!!!! NO WEB_APP_DATA in message !!!!")
        
        return await handler(event, data)
    
    # Регистрируем обработчики (ВАЖНО: порядок имеет значение!)
    dp.include_router(commands.router)    # Команды должны быть первыми
    dp.include_router(callbacks.router)   # Callback-кнопки
    dp.include_router(photo.router)       # Обработка фотографий
    dp.include_router(inline.router)      # Inline-режим
    dp.include_router(webapp.router)      # WebApp (с fallback) - ПОСЛЕДНИМ!
    
    # Настройка хуков
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Создаем веб-приложение для webhook
    app = web.Application()
    
    # Настройка webhook handler
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    
    logger.info("Bot webhook сервер готов")
    return app

async def register_commands(bot: Bot):
    """Регистрирует команды бота для отображения в меню."""
    commands = [
        BotCommand(command="start", description="👋 Начать работу с ботом"),
        BotCommand(command="help", description="❓ Помощь по использованию бота"),
        BotCommand(command="split", description="📇 Разделить чек (в группе)"),
        BotCommand(command="testwebapp", description="🧪 Тестовый WebApp")
    ]
    await bot.set_my_commands(commands)
    logger.info("Команды бота зарегистрированы")

if __name__ == "__main__":
    # Определяем порт для запуска
    port = int(os.environ.get('PORT', 8080))
    
    logger.info(f"Запуск бота в webhook режиме на порту {port}")
    
    # Создаем и запускаем приложение
    web.run_app(
        create_bot_app(),
        host='0.0.0.0',
        port=port
    ) 