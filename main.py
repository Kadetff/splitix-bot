import asyncio
import logging
import io
import os
import base64 # Для кодирования изображения
import json   # Для работы с JSON от OpenAI
from typing import Any, cast
from decimal import Decimal, InvalidOperation # Для точной работы с деньгами

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F # Добавили F для фильтров
from aiogram.filters import CommandStart
from aiogram.types import Message, PhotoSize, InlineKeyboardMarkup, InlineKeyboardButton # Добавили инлайн клавиатуры
from aiogram.utils.keyboard import InlineKeyboardBuilder # Удобный построитель клавиатур
from aiogram.fsm.storage.memory import MemoryStorage
from config.settings import TELEGRAM_BOT_TOKEN, LOG_LEVEL
from handlers import photo, callbacks, commands
from utils.keyboards import create_items_keyboard_with_counters
from utils.helpers import parse_possible_price

from openai import AsyncOpenAI # Асинхронный клиент OpenAI

# Загружаем переменные окружения из .env файла
load_dotenv()

# Включим логирование, чтобы видеть ошибки
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# Получаем токен бота из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logger.error("Ошибка: TELEGRAM_BOT_TOKEN не найден в .env файле!")
    exit()

# --- OpenAI API Key --- 
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("Ошибка: OPENAI_API_KEY не найден в .env файле!")
    exit()

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- OpenAI Client Setup --- 
openai_client = None
try:
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    logger.info("Клиент OpenAI инициализирован.")
except Exception as e:
    logger.error(f"Ошибка инициализации клиента OpenAI: {e}")
    exit()

# Словарь для хранения состояния (items и их счетчики) для каждого сообщения с клавиатурой
# Ключ: message_id сообщения бота с клавиатурой
# Значение: {"items": list_of_item_dicts, "user_selections": {user_id: {item_idx: count}}}
message_states: dict[int, dict[str, Any]] = {} # Type hint remains general for simplicity, but structure changes

# Экспорт message_states для использования в обработчиках
from handlers import callbacks, photo
callbacks.message_states = message_states
photo.message_states = message_states

async def main():
    # logging.basicConfig(level=logging.DEBUG) # Можно установить DEBUG для более детальных логов
    logger.info("Бот запускается с OpenAI GPT Vision и подтверждением выбора...")
    
    # Регистрация роутеров из handlers
    dp.include_router(commands.router)
    dp.include_router(photo.router)
    dp.include_router(callbacks.router)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 