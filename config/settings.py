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

# WebApp settings
WEBAPP_URL = os.getenv("WEBAPP_URL")
if not WEBAPP_URL:
    # Если WEBAPP_URL не задан, но есть PORT и HEROKU_APP_NAME, формируем URL для Heroku
    HEROKU_APP_NAME = os.getenv("HEROKU_APP_NAME")
    if HEROKU_APP_NAME:
        WEBAPP_URL = f"https://{HEROKU_APP_NAME}.herokuapp.com"
        logger.info(f"WEBAPP_URL автоматически сформирован для Heroku: {WEBAPP_URL}")
    else:
        # Для локальной разработки
        PORT = os.getenv("PORT", "8080")
        WEBAPP_URL = f"http://localhost:{PORT}"
        logger.warning(f"WEBAPP_URL не найден, используем локальный URL: {WEBAPP_URL}")
else:
    # Очищаем URL от кавычек, если они есть
    WEBAPP_URL = WEBAPP_URL.strip('"\'')
    logger.info(f"Загружен WEBAPP_URL: {WEBAPP_URL}")

# Logging settings
LOG_LEVEL = "DEBUG" 