import os
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logger = logging.getLogger(__name__)

# Telegram Bot settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле!")

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY не найден в .env файле!")

# OpenAI model settings
OPENAI_MODEL = "gpt-4.1-mini"
OPENAI_MAX_TOKENS = 1500
USE_OPENAI_GPT_VISION = True  # Использовать ли GPT Vision для анализа чеков

# WebApp settings
WEBAPP_URL = os.getenv("WEBAPP_URL")

if not WEBAPP_URL:
    logger.warning("WEBAPP_URL не указан в .env файле. WebApp функциональность будет недоступна.")
    WEBAPP_URL = None
else:
    # Очищаем URL от кавычек, если они есть
    WEBAPP_URL = WEBAPP_URL.strip('"\'')
    logger.info(f"Загружен WEBAPP_URL: {WEBAPP_URL}")

# Logging settings
LOG_LEVEL = "DEBUG" 