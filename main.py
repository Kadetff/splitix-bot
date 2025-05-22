import asyncio
import logging
from typing import Any
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
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
# webapp.message_states = message_states # Временно комментируем для отладки

async def main():
    logger.info(f"Бот запускается с OpenAI GPT Vision и подтверждением выбора...")
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
    # Сначала специфичные обработчики, потом универсальные
    dp.include_router(commands.router)    # Команды должны быть первыми
    dp.include_router(callbacks.router)   # Callback-кнопки
    dp.include_router(photo.router)       # Обработка фотографий
    dp.include_router(inline.router)      # Inline-режим
    dp.include_router(webapp.router)      # WebApp (с fallback) - ПОСЛЕДНИМ!
    
    await dp.start_polling(bot)

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
    asyncio.run(main()) 