import asyncio
import logging
import sys
from typing import Any
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from config.settings import TELEGRAM_BOT_TOKEN, LOG_LEVEL
from handlers import photo, callbacks, commands, webapp

# Настраиваем логирование
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Словарь для хранения состояния (items и их счетчики) для каждого сообщения с клавиатурой
message_states: dict[int, dict[str, Any]] = {}

# Экспорт message_states для использования в обработчиках
callbacks.message_states = message_states
photo.message_states = message_states
webapp.message_states = message_states

async def main():
    logger.info("Бот запускается с OpenAI GPT Vision и подтверждением выбора...")
    logger.info(f"Уровень логирования: {LOG_LEVEL}")
    
    # Регистрация роутеров из handlers
    dp.include_router(commands.router)
    dp.include_router(photo.router)
    dp.include_router(callbacks.router)
    dp.include_router(webapp.router)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 