import os
import logging
import threading
import subprocess
from webapp.server import app
from config.settings import LOG_LEVEL

# Настройка логирования
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

def main():
    # Получаем порт из переменной окружения или используем порт по умолчанию
    port = int(os.environ.get('PORT', 8080))
    
    logger.info(f"Запуск веб-сервера на порту {port}")
    
    # Запускаем веб-сервер
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    main() 