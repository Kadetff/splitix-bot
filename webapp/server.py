import os
import json
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Получаем абсолютный путь к директории webapp
webapp_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app)  # Разрешаем CORS для всех маршрутов

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранилище данных (в реальном приложении должно быть заменено на БД)
receipt_data = {}

@app.route('/')
def index():
    logger.info(f"Запрос главной страницы, webapp_dir: {webapp_dir}")
    return send_from_directory(webapp_dir, 'index.html')

@app.route('/health')
def health_check():
    """Простой эндпоинт для проверки доступности API"""
    logger.info("Запрос проверки состояния API")
    return jsonify({"status": "ok", "message": "API is running"})

@app.route('/<int:message_id>')
def index_with_message_id(message_id):
    """Обработка запроса с message_id в URL"""
    logger.info(f"Запрос страницы с message_id в URL: {message_id}")
    return send_from_directory(webapp_dir, 'index.html')

@app.route('/api/receipt/<int:message_id>', methods=['GET'])
def get_receipt_data(message_id):
    """Получение данных чека по ID сообщения"""
    logger.info(f"Запрос данных чека для message_id: {message_id}")
    
    if message_id not in receipt_data:
        # Для тестирования возвращаем тестовые данные только если включен режим отладки
        if app.debug:
            logger.info(f"Receipt not found, returning test data for message_id: {message_id} (debug mode)")
            test_data = {
                "items": [
                    {"id": 0, "description": "Тестовый товар 1", "quantity_from_openai": 2, "unit_price_from_openai": 150.00, "total_amount_from_openai": 300.00},
                    {"id": 1, "description": "Тестовый товар 2", "quantity_from_openai": 1, "unit_price_from_openai": 180.00, "total_amount_from_openai": 180.00},
                    {"id": 2, "description": "Тестовый товар 3", "quantity_from_openai": 3, "unit_price_from_openai": 350.00, "total_amount_from_openai": 1050.00}
                ],
                "user_selections": {},
                "service_charge_percent": 10.0,
                "total_check_amount": 1530.00,
                "total_discount_percent": 5.0,
                "total_discount_amount": 76.50,
                "actual_discount_percent": 5.0
            }
            return jsonify(test_data)
        else:
            logger.warning(f"Receipt data not found for message_id: {message_id}")
            return jsonify({"error": "Receipt not found"}), 404
    
    logger.info(f"Returning receipt data for message_id: {message_id}")
    return jsonify(receipt_data[message_id])

@app.route('/api/receipt/<int:message_id>', methods=['POST'])
def save_receipt_data(message_id):
    """Сохранение данных чека"""
    logger.info(f"Сохранение данных чека для message_id: {message_id}")
    
    try:
        data = request.json
        receipt_data[message_id] = data
        return jsonify({"success": True, "message": "Data saved successfully"})
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/selection/<int:message_id>', methods=['POST'])
def save_user_selection(message_id):
    """Сохранение выбора пользователя"""
    logger.info(f"Сохранение выбора пользователя для message_id: {message_id}")
    
    try:
        data = request.json
        user_id = data.get('user_id')
        selected_items = data.get('selected_items')
        
        if message_id not in receipt_data:
            receipt_data[message_id] = {"items": [], "user_selections": {}}
        
        if 'user_selections' not in receipt_data[message_id]:
            receipt_data[message_id]['user_selections'] = {}
        
        receipt_data[message_id]['user_selections'][user_id] = selected_items
        
        return jsonify({"success": True, "message": "Selection saved successfully"})
    except Exception as e:
        logger.error(f"Ошибка при сохранении выбора: {e}")
        return jsonify({"error": str(e)}), 500

# Добавляем маршрут для отладки
@app.route('/debug')
def debug():
    return jsonify({
        "receipt_data": receipt_data,
        "webapp_dir": webapp_dir,
        "current_dir": os.getcwd()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Запуск сервера на порту {port}, webapp_dir: {webapp_dir}")
    app.run(host='0.0.0.0', port=port, debug=True) 