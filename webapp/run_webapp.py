import os
import logging
import subprocess
import sys
from backend.server import app
from config.settings import LOG_LEVEL

# Настройка логирования
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

def run_flask_app():
    # Получаем порт из переменной окружения или используем порт по умолчанию
    port = int(os.environ.get('PORT', 8080))
    
    # Предупреждаем о потенциальной проблеме с локальным сервером и Telegram
    if os.environ.get('WEBAPP_URL') is None:
        logger.warning("ВНИМАНИЕ: WEBAPP_URL не задан в .env файле, а локальное HTTP подключение не поддерживается Telegram.")
        logger.warning("Для тестирования вебприложения с ботом, настройте WEBAPP_URL с HTTPS доменом.")
    
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
        # Запускаем бота как отдельный процесс с перенаправлением вывода
        bot_process = subprocess.Popen(
            [sys.executable, 'main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1  # Line buffered
        )
        
        # Запускаем отдельный поток для чтения и вывода логов бота
        def read_bot_output():
            for line in bot_process.stdout:
                print(f"[BOT] {line.strip()}")
        
        # Запускаем поток для чтения вывода бота
        import threading
        log_thread = threading.Thread(target=read_bot_output, daemon=True)
        log_thread.start()
        
        logger.info(f"Telegram бот запущен с PID: {bot_process.pid}")
        
        # Запускаем Flask приложение
        run_flask_app()

if __name__ == "__main__":
    main() 