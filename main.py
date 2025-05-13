import asyncio
import logging
from typing import Any
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config.settings import TELEGRAM_BOT_TOKEN, LOG_LEVEL
from handlers import photo, callbacks, commands

# Включим логирование, чтобы видеть ошибки
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Словарь для хранения состояния (items и их счетчики) для каждого сообщения с клавиатурой
message_states: dict[int, dict[str, Any]] = {}

# Экспорт message_states для использования в обработчиках
callbacks.message_states = message_states
photo.message_states = message_states

async def main():
    logger.info("Бот запускается с OpenAI GPT Vision и подтверждением выбора...")
    
    # Регистрация роутеров из handlers
    dp.include_router(commands.router)
    dp.include_router(photo.router)
    dp.include_router(callbacks.router)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 