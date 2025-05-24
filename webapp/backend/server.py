import os
import json
import logging
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, send_file
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

@app.route('/')
def index():
    """Главная страница"""
    index_path = os.path.join(frontend_dir, 'index.html')
    return send_file(index_path)

@app.route('/test_webapp')
@app.route('/test_webapp/')
def test_webapp_page():
    """Отдаем тестовый WebApp"""
    test_page_path = os.path.join(frontend_dir, 'test_webapp.html')
    if os.path.exists(test_page_path):
        return send_file(test_page_path)
    else:
        logger.error(f"Тестовый файл test_webapp.html не найден по пути: {test_page_path}")
        return "Тестовый файл не найден", 404

@app.route('/health')
def health_check():
    """Проверка работоспособности API"""
    return jsonify({"status": "ok", "message": "API is running"})

@app.route('/<int:message_id>')
def index_with_message_id(message_id):
    """Обработка запроса с message_id в URL"""
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

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8080) 