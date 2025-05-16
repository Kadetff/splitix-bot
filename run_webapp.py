import os
import logging
import subprocess
import sys
from webapp.server import app
from config.settings import LOG_LEVEL

# Настройка логирования
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

def run_flask_app():
    # Получаем порт из переменной окружения или используем порт по умолчанию
    port = int(os.environ.get('PORT', 8080))
    
    logger.info(f"Запуск веб-сервера на порту {port}")
    
    # Запускаем веб-сервер
    app.run(host='0.0.0.0', port=port)

def main():
    # На Heroku запускаем только веб-сервер, бот уже запущен в отдельном dyno
    # Проверяем, не запущены ли мы на Heroku
    if os.environ.get('DYNO'):
        logger.info("Запуск на Heroku. Запускаем только веб-сервер.")
        run_flask_app()
    else:
        # Локальный запуск - запускаем и бота, и веб-сервер
        logger.info("Локальный запуск. Запускаем бота и веб-сервер.")
        # Запускаем бота как отдельный процесс
        bot_process = subprocess.Popen([sys.executable, 'main.py'], 
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,
                                        universal_newlines=True)
        
        logger.info(f"Telegram бот запущен с PID: {bot_process.pid}")
        
        # Запускаем Flask приложение
        run_flask_app()

if __name__ == "__main__":
    main() 