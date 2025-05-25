import os
import json
import logging
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS

# Получаем абсолютный путь к директории webapp
webapp_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_dir = os.path.join(webapp_dir, 'frontend')

app = Flask(__name__, static_folder=os.path.join(frontend_dir, 'static'))
CORS(app)  # Разрешаем CORS для всех маршрутов

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Убрано хранилище данных чеков - используем только тестовое приложение

# Настройки окружения
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ENABLE_TEST_COMMANDS = os.getenv("ENABLE_TEST_COMMANDS", "true").lower() == "true"

def index():
    """Главная страница - отдаем основное приложение"""
    logger.debug("Вызвана функция index() - отдаем основное приложение")
    index_page_path = os.path.join(frontend_dir, 'index.html')
    if os.path.exists(index_page_path):
        return send_file(index_page_path)
    else:
        # Fallback на тестовое приложение
        test_page_path = os.path.join(frontend_dir, 'debug', 'test_webapp.html')
        if os.path.exists(test_page_path):
            return send_file(test_page_path)
        else:
            return "Приложение не найдено", 404

@app.route('/test_webapp')
@app.route('/test_webapp/')
def test_webapp_page():
    """Отдаем тестовый WebApp (только в dev/staging окружениях)"""
    # Проверяем, разрешены ли тестовые команды
    if not ENABLE_TEST_COMMANDS:
        logger.warning(f"Попытка доступа к тестовой странице в {ENVIRONMENT} окружении")
        abort(404)  # Возвращаем 404 в production
    
    logger.debug("Вызвана функция test_webapp_page()")
    test_page_path = os.path.join(frontend_dir, 'debug', 'test_webapp.html')
    
    if os.path.exists(test_page_path):
        logger.debug(f"Отправляю тестовый файл: {test_page_path}")
        return send_file(test_page_path)
    else:
        logger.error(f"Тестовый файл test_webapp.html не найден по пути: {test_page_path}")
        return "Тестовый файл не найден", 404

@app.route('/app/<int:message_id>')
def receipt_app(message_id):
    """Отдаем основное приложение для конкретного чека"""
    logger.debug(f"Запрос к приложению для message_id: {message_id}")
    return index()

@app.route('/')
def test_root_handler():
    """Специальный обработчик для диагностики корневых запросов"""
    logger.debug(f"Flask root handler: {request.url}")
    
    # Если это запрос к test_webapp через корневой handler, перенаправляем
    if 'test_webapp' in request.url:
        logger.debug("Перенаправляем test_webapp запрос")
        return test_webapp_page()
    
    # Если это запрос к health через корневой handler, перенаправляем
    if 'health' in request.url:
        logger.debug("Перенаправляем health запрос")
        return health_check()
    
    # В остальных случаях отдаем обычную главную страницу
    return index()

@app.route('/health')
@app.route('/health/')
def health_check():
    """Проверка работоспособности API"""
    return jsonify({"status": "ok", "message": "API is running"})

@app.route('/api/receipt/<int:message_id>')
def get_receipt_data(message_id):
    """Получение данных чека по message_id"""
    try:
        # Импортируем message_states из handlers.photo
        from handlers.photo import message_states
        
        if message_id not in message_states:
            logger.warning(f"Данные чека не найдены для message_id: {message_id}")
            return jsonify({"error": "Receipt data not found"}), 404
        
        receipt_data = message_states[message_id]
        logger.info(f"Отдаю данные чека для message_id: {message_id}")
        
        return jsonify(receipt_data)
        
    except Exception as e:
        logger.error(f"Ошибка при получении данных чека: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/answer_webapp_query', methods=['POST'])
def answer_webapp_query():
    """API endpoint для answerWebAppQuery (для Inline-кнопок)"""
    try:
        if not request.is_json:
            return jsonify({"error": "Expected JSON data"}), 400
            
        data = request.json
        query_id = data.get('query_id')
        result_data = data.get('data', {})
        title = data.get('title', 'Данные от WebApp')
        description = data.get('description', 'Результат выбора товаров')
        
        if not query_id:
            return jsonify({"error": "query_id is required"}), 400
        
        logger.info(f"Получен запрос answerWebAppQuery: query_id={query_id}")
        logger.info(f"Данные для отправки: {result_data}")
        
        # Импортируем и используем функцию из handlers/webapp.py для вызова answerWebAppQuery
        try:
            # Здесь нужно вызвать Telegram Bot API answerWebAppQuery
            # Но у нас нет прямого доступа к bot объекту из Flask
            # Поэтому мы делаем HTTP запрос к Telegram API
            
            import requests
            import os
            
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not bot_token:
                logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
                return jsonify({"error": "Bot token not configured"}), 500
            
            # Формируем данные для answerWebAppQuery
            telegram_data = {
                "web_app_query_id": query_id,
                "result": {
                    "type": "article",
                    "id": str(int(time.time())),
                    "title": title,
                    "description": description,
                    "input_message_content": {
                        "message_text": f"✅ **Выбор товаров подтвержден**\n\n📱 **Источник**: Inline-клавиатура\n📊 **Выбрано позиций**: {len(result_data.get('selected_items', {}))}\n⏰ **Время**: {datetime.now().strftime('%H:%M:%S')}"
                    }
                }
            }
            
            # Отправляем запрос к Telegram Bot API
            telegram_url = f"https://api.telegram.org/bot{bot_token}/answerWebAppQuery"
            response = requests.post(telegram_url, json=telegram_data, timeout=10)
            
            if response.status_code == 200:
                telegram_result = response.json()
                if telegram_result.get('ok'):
                    logger.info(f"answerWebAppQuery выполнен успешно для query_id: {query_id}")
                    return jsonify({"success": True, "message": "WebApp query answered successfully"})
                else:
                    error_desc = telegram_result.get('description', 'Unknown error')
                    logger.error(f"Telegram API error: {error_desc}")
                    return jsonify({"error": f"Telegram API error: {error_desc}"}), 500
            else:
                logger.error(f"HTTP error from Telegram API: {response.status_code}")
                return jsonify({"error": f"HTTP error: {response.status_code}"}), 500
                
        except requests.RequestException as e:
            logger.error(f"Ошибка при запросе к Telegram API: {e}")
            return jsonify({"error": f"Request error: {str(e)}"}), 500
        except Exception as e:
            logger.error(f"Неожиданная ошибка в answerWebAppQuery: {e}")
            return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
            
    except Exception as e:
        logger.error(f"Ошибка в answer_webapp_query endpoint: {e}")
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode) 