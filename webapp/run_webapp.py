import os
import logging
from backend.server import app
from config.settings import LOG_LEVEL

# Настройка логирования
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Запуск веб-сервера на порту {port}")
    app.run(host='0.0.0.0', port=port) 