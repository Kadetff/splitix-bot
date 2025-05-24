import asyncio
import logging
import os
from typing import Any
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from config.settings import TELEGRAM_BOT_TOKEN, LOG_LEVEL, WEBAPP_URL
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
# webapp.message_states = message_states # Временно комментируем для отладки

# Конфигурация для Heroku
# Определяем имя приложения из переменных или используем полное имя
APP_NAME = os.getenv('HEROKU_APP_NAME') or os.getenv('APP_NAME') or 'splitix-bot-69642ff6c071'
PORT = os.getenv('PORT')

# Если есть PORT (означает что мы на Heroku), настраиваем webhook
if PORT:
    WEBHOOK_HOST = f"https://{APP_NAME}.herokuapp.com"
    WEBHOOK_PATH = f"/bot/{TELEGRAM_BOT_TOKEN}"
    WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
else:
    WEBHOOK_HOST = WEBHOOK_PATH = WEBHOOK_URL = None

async def on_startup(bot: Bot) -> None:
    """Хук для настройки webhook при запуске."""
    if WEBHOOK_URL:
        logger.info(f"Настройка webhook: {WEBHOOK_URL}")
        await bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=["message", "callback_query", "inline_query", "chosen_inline_result", "web_app_data"]
        )
        logger.info("Webhook установлен успешно")
    else:
        logger.info("Запуск в режиме polling (локальная разработка)")

async def on_shutdown(bot: Bot) -> None:
    """Хук для удаления webhook при остановке."""
    if WEBHOOK_URL:
        logger.info("Удаление webhook...")
        await bot.delete_webhook()
        logger.info("Webhook удален")

async def create_app() -> web.Application:
    """Создание и настройка веб-приложения."""
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
    # Сначала специфичные обработчики, потом универсальные
    dp.include_router(commands.router)    # Команды должны быть первыми
    dp.include_router(callbacks.router)   # Callback-кнопки
    dp.include_router(photo.router)       # Обработка фотографий
    dp.include_router(inline.router)      # Inline-режим
    dp.include_router(webapp.router)      # WebApp (с fallback) - ПОСЛЕДНИМ!
    
    # Настройка хуков
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Создаем веб-приложение
    app = web.Application()
    
    if WEBHOOK_URL:
        # Webhook режим для Heroku
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
        logger.info("Приложение настроено для webhook режима")
    else:
        # Polling режим для локальной разработки
        async def start_polling():
            await dp.start_polling(bot)
        
        # Запускаем polling в фоновой задаче
        asyncio.create_task(start_polling())
        logger.info("Приложение настроено для polling режима")
    
    return app

async def register_commands(bot: Bot):
    """Регистрирует команды бота для отображения в меню."""
    commands = [
        BotCommand(command="start", description="👋 Начать работу с ботом"),
        BotCommand(command="help", description="❓ Помощь по использованию бота"),
        BotCommand(command="split", description="📇 Разделить чек (в группе)"),
        BotCommand(command="testwebapp", description="🧪 Тестовый WebApp"),
        BotCommand(command="webhook", description="🔍 Статус webhook"),
        BotCommand(command="fixwebhook", description="🔧 Исправить webhook"),
        BotCommand(command="resetwebhook", description="🔥 Полный сброс webhook"),
        BotCommand(command="diagwebhook", description="🔬 Диагностика webhook"),
        BotCommand(command="safewebhook", description="🛡️ Осторожная установка")
    ]
    await bot.set_my_commands(commands)
    logger.info("Команды бота зарегистрированы")

async def main():
    """Главная функция для локального запуска в polling режиме."""
    logger.info(f"Бот запускается с OpenAI GPT Vision и подтверждением выбора...")
    logger.info(f"Уровень логирования: {LOG_LEVEL}")
    
    if WEBHOOK_URL:
        logger.info("Режим webhook - используйте веб-сервер")
        return
    
    # Для локальной разработки - простой polling
    storage = MemoryStorage()
    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=storage)
    
    await register_commands(bot)
    
    @dp.update.outer_middleware()
    async def raw_update_logger(handler, event, data):
        logger.critical(f"!!!! RAW UPDATE RECEIVED BY DISPATCHER !!!! Type: {type(event)}")
        logger.critical(f"Raw event data: {event.model_dump_json(indent=2) if hasattr(event, 'model_dump_json') else str(event)}")
        
        if hasattr(event, 'message') and event.message:
            msg = event.message
            logger.critical(f"!!!! MESSAGE DETAILS !!!! content_type: {msg.content_type}")
            if hasattr(msg, 'web_app_data') and msg.web_app_data:
                logger.critical(f"!!!! WEB_APP_DATA FOUND !!!! data: {msg.web_app_data.data}")
            else:
                logger.critical(f"!!!! NO WEB_APP_DATA in message !!!!")
        
        return await handler(event, data)
    
    dp.include_router(commands.router)
    dp.include_router(callbacks.router)
    dp.include_router(photo.router)
    dp.include_router(inline.router)
    dp.include_router(webapp.router)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 