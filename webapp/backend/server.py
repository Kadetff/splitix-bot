import os
import json
import logging
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, send_file, abort
from flask_cors import CORS
from utils.data_utils import (
    load_json_data,
    save_json_data,
    is_data_expired,
    add_metadata,
    validate_and_fix_user_selections,
    convert_decimals
)
from models.receipt import Receipt, ReceiptItem
from typing import Dict, Any

# Получаем абсолютный путь к директории webapp
webapp_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_dir = os.path.join(webapp_dir, 'frontend')
backend_dir = os.path.dirname(os.path.abspath(__file__))

# Настраиваем путь к файлу сохранения данных
data_dir = os.path.join(backend_dir, 'data')
data_file = os.path.join(data_dir, 'receipt_data.json')

app = Flask(__name__, static_folder=os.path.join(frontend_dir, 'static'))
CORS(app)  # Разрешаем CORS для всех маршрутов

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранилище данных (в реальном приложении должно быть заменено на БД)
receipt_data = {}

# Константы для управления сроком жизни данных
DATA_EXPIRATION_DAYS = 7  # Данные хранятся 7 дней

def load_receipt_data():
    """Загрузка данных из файла"""
    global receipt_data
    try:
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logger.info(f"Создана директория для данных: {data_dir}")
        
        receipt_data = load_json_data(data_file)
        logger.info(f"Загружены данные из {data_file}, количество записей: {len(receipt_data)}")
        
        cleanup_expired_data()
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных из файла: {e}")
        receipt_data = {}

def cleanup_expired_data():
    """Очистка устаревших данных"""
    global receipt_data
    try:
        expired_msg_ids = []
        
        for msg_id, msg_data in receipt_data.items():
            if 'metadata' in msg_data and 'created_at' in msg_data['metadata']:
                if is_data_expired(msg_data['metadata']['created_at'], DATA_EXPIRATION_DAYS):
                    expired_msg_ids.append(msg_id)
        
        for msg_id in expired_msg_ids:
            del receipt_data[msg_id]
            
        if expired_msg_ids:
            logger.info(f"Удалено {len(expired_msg_ids)} устаревших записей")
            save_receipt_data_to_file()
    except Exception as e:
        logger.error(f"Ошибка при очистке устаревших данных: {e}")

def save_receipt_data_to_file():
    """Сохранение данных в файл"""
    try:
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logger.info(f"Создана директория для данных: {data_dir}")
        
        if save_json_data(receipt_data, data_file):
            logger.info(f"Данные успешно сохранены в файл {data_file}")
        else:
            logger.error("Не удалось сохранить данные в файл")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в файл: {e}")

# Загружаем данные при запуске
load_receipt_data()

# Настройки окружения
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ENABLE_TEST_COMMANDS = os.getenv("ENABLE_TEST_COMMANDS", "true").lower() == "true"

def index():
    """Главная страница"""
    logger.debug("Вызвана функция index()")
    index_path = os.path.join(frontend_dir, 'index.html')
    return send_file(index_path)

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

@app.route('/<int:message_id>')
@app.route('/<int:message_id>/')
def index_with_message_id(message_id):
    """Обработка запроса с message_id в URL"""
    logger.debug(f"Обработка запроса с message_id: {message_id}")
    index_path = os.path.join(frontend_dir, 'index.html')
    
    if os.path.exists(index_path):
        try:
            return send_file(index_path)
        except Exception as e:
            logger.error(f"Ошибка при отправке файла: {e}")
            return f"Ошибка при отправке файла: {e}", 500
    else:
        logger.error(f"Файл index.html не найден по пути: {index_path}")
        return "Файл не найден", 404

@app.route('/api/receipt/<int:message_id>', methods=['GET'])
def get_receipt_data(message_id):
    """Получение данных чека по ID сообщения"""
    message_id_str = str(message_id)
    user_id = request.args.get('user_id')
    
    if message_id_str not in receipt_data:
        logger.warning(f"Receipt data not found for message_id: {message_id}")
        return jsonify({"error": "Receipt not found"}), 404
    
    try:
        # Создаем объект Receipt из данных
        receipt = Receipt(**receipt_data[message_id_str])
        result_data = convert_decimals(receipt.model_dump())
        
        if 'metadata' in result_data:
            del result_data['metadata']
        
        if 'user_selections' in result_data and user_id:
            user_id_str = str(user_id)
            filtered_selections = {}
            if user_id_str in result_data['user_selections']:
                user_selections = result_data['user_selections'][user_id_str]
                normalized_selections = {str(k): int(v) for k, v in user_selections.items()}
                filtered_selections[user_id_str] = normalized_selections
            result_data['user_selections'] = filtered_selections
        else:
            result_data['user_selections'] = {}
        
        return jsonify(result_data)
    except Exception as e:
        logger.error(f"Ошибка при обработке данных чека: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/receipt/<int:message_id>', methods=['POST'])
def save_receipt_data(message_id):
    """Сохранение данных чека"""
    message_id_str = str(message_id)
    
    try:
        if not request.is_json:
            return jsonify({"error": "Expected JSON data"}), 400
            
        data = request.json
        
        if not isinstance(data, dict):
            return jsonify({"error": f"Expected dictionary, got {type(data).__name__}"}), 400
            
        if 'items' not in data:
            return jsonify({"error": "Missing required field 'items'"}), 400
        
        # Валидируем данные через модель Receipt
        receipt = Receipt(**data)
        receipt_data[message_id_str] = convert_decimals(receipt.model_dump())
        
        save_receipt_data_to_file()
        return jsonify({"success": True, "message": "Data saved successfully"})
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/selection/<int:message_id>', methods=['POST'])
def save_user_selection(message_id):
    """Сохранение выбора пользователя"""
    message_id_str = str(message_id)
    
    try:
        if not request.is_json:
            return jsonify({"error": "Expected JSON data"}), 400
            
        data = request.json
        user_id = data.get('user_id')
        selected_items = data.get('selected_items')
        
        if not user_id:
            return jsonify({"error": "Missing required field 'user_id'"}), 400
            
        if not isinstance(selected_items, dict):
            return jsonify({"error": f"Field 'selected_items' should be a dictionary"}), 400
        
        selected_items_str_keys = {str(k): int(v) for k, v in selected_items.items()}
        user_id_str = str(user_id)
        
        if message_id_str not in receipt_data:
            receipt_data[message_id_str] = {
                "items": [], 
                "user_selections": {},
                "metadata": {
                    'created_at': time.time(),
                    'last_updated': time.time()
                }
            }
        
        if 'user_selections' not in receipt_data[message_id_str]:
            receipt_data[message_id_str]['user_selections'] = {}
        
        receipt_data[message_id_str] = add_metadata(receipt_data[message_id_str])
        receipt_data[message_id_str]['user_selections'][user_id_str] = selected_items_str_keys
        
        save_receipt_data_to_file()
        return jsonify({"success": True, "message": "Selection saved successfully"})
    except Exception as e:
        logger.error(f"Ошибка при сохранении выбора: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/maintenance/cleanup', methods=['POST'])
@app.route('/maintenance/cleanup/', methods=['POST'])
def trigger_cleanup():
    """Endpoint для запуска очистки устаревших данных"""
    try:
        before_count = len(receipt_data)
        cleanup_expired_data()
        after_count = len(receipt_data)
        
        return jsonify({
            "success": True,
            "message": f"Очистка выполнена успешно",
            "records_before": before_count,
            "records_after": after_count,
            "records_removed": before_count - after_count
        })
    except Exception as e:
        logger.error(f"Ошибка при запуске очистки: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/maintenance/create_test_data', methods=['POST'])
@app.route('/maintenance/create_test_data/', methods=['POST'])
def create_test_data():
    """Endpoint для создания тестовых данных (только в dev окружении)"""
    if ENVIRONMENT == "production":
        return jsonify({"error": "Test data creation not allowed in production"}), 403
    
    try:
        # Создаем тестовые данные для message_id=1223
        test_data = {
            "items": [
                {
                    "id": 0,
                    "description": "Кофе латте",
                    "quantity_from_openai": 2,
                    "unit_price_from_openai": 150.00,
                    "total_amount_from_openai": 300.00
                },
                {
                    "id": 1,
                    "description": "Круассан с миндалем",
                    "quantity_from_openai": 1,
                    "unit_price_from_openai": 180.00,
                    "total_amount_from_openai": 180.00
                },
                {
                    "id": 2,
                    "description": "Салат Цезарь",
                    "quantity_from_openai": 3,
                    "unit_price_from_openai": 350.00,
                    "total_amount_from_openai": 1050.00
                }
            ],
            "user_selections": {},
            "service_charge_percent": 10.0,
            "total_check_amount": 1530.00,
            "total_discount_percent": 5.0,
            "total_discount_amount": 76.50,
            "actual_discount_percent": 5.0,
            "metadata": {
                "created_at": time.time(),
                "last_updated": time.time()
            }
        }
        
        receipt_data["1223"] = test_data
        save_receipt_data_to_file()
        
        return jsonify({
            "success": True,
            "message": "Тестовые данные созданы для message_id=1223",
            "data": test_data
        })
    except Exception as e:
        logger.error(f"Ошибка при создании тестовых данных: {e}")
        return jsonify({"error": str(e)}), 500

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