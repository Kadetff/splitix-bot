import os
import logging
import threading
import asyncio
from webapp.server import app
from config.settings import LOG_LEVEL
from main import main as run_bot

# Настройка логирования
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

def run_flask_app():
    # Получаем порт из переменной окружения или используем порт по умолчанию
    port = int(os.environ.get('PORT', 8080))
    
    logger.info(f"Запуск веб-сервера на порту {port}")
    
    # Запускаем веб-сервер
    app.run(host='0.0.0.0', port=port)

def run_telegram_bot():
    logger.info("Запуск Telegram бота в отдельном потоке")
    asyncio.run(run_bot())

def main():
    # Создаем и запускаем поток для Telegram бота
    bot_thread = threading.Thread(target=run_telegram_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Запускаем Flask приложение в основном потоке
    run_flask_app()

if __name__ == "__main__":
    main() 