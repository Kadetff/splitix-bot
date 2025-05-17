import os
import json
import logging
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

# Получаем абсолютный путь к директории webapp
webapp_dir = os.path.dirname(os.path.abspath(__file__))

# Настраиваем путь к файлу сохранения данных
data_dir = os.path.join(webapp_dir, 'data')
data_file = os.path.join(data_dir, 'receipt_data.json')

app = Flask(__name__)
CORS(app)  # Разрешаем CORS для всех маршрутов

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранилище данных (в реальном приложении должно быть заменено на БД)
receipt_data = {}

# Константы для управления сроком жизни данных
DATA_EXPIRATION_DAYS = 7  # Данные хранятся 7 дней

# Функция для загрузки данных из файла
def load_receipt_data():
    global receipt_data
    try:
        # Проверяем существование директории data
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logger.info(f"Создана директория для данных: {data_dir}")
        
        # Проверяем существование файла с данными
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                
                # Проверяем структуру данных и добавляем метаданные, если их нет
                clean_data = {}
                for msg_id, msg_data in loaded_data.items():
                    # Если есть поле 'created_at', используем его, иначе добавляем текущее время
                    if isinstance(msg_data, dict):
                        if 'metadata' not in msg_data:
                            msg_data['metadata'] = {
                                'created_at': time.time(),  # Текущее время в секундах
                                'last_updated': time.time()
                            }
                        clean_data[msg_id] = msg_data
                
                receipt_data = clean_data
                logger.info(f"Загружены данные из {data_file}, количество записей: {len(receipt_data)}")
                
                # Очищаем устаревшие данные
                cleanup_expired_data()
        else:
            logger.info(f"Файл данных {data_file} не существует, используем пустое хранилище.")
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных из файла: {e}")
        receipt_data = {}

# Функция для очистки устаревших данных
def cleanup_expired_data():
    global receipt_data
    try:
        now = time.time()
        expired_msg_ids = []
        
        # Находим все устаревшие записи
        for msg_id, msg_data in receipt_data.items():
            if 'metadata' in msg_data and 'created_at' in msg_data['metadata']:
                created_at = msg_data['metadata']['created_at']
                age_days = (now - created_at) / (60 * 60 * 24)  # Возраст в днях
                
                if age_days > DATA_EXPIRATION_DAYS:
                    expired_msg_ids.append(msg_id)
        
        # Удаляем устаревшие записи
        for msg_id in expired_msg_ids:
            del receipt_data[msg_id]
            
        if expired_msg_ids:
            logger.info(f"Удалено {len(expired_msg_ids)} устаревших записей")
            # Сохраняем изменения в файл
            save_receipt_data_to_file()
    except Exception as e:
        logger.error(f"Ошибка при очистке устаревших данных: {e}")

# Функция для сохранения данных в файл
def save_receipt_data_to_file():
    try:
        # Проверяем существование директории data
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        # Сохраняем данные в файл
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(receipt_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Данные сохранены в файл {data_file}, количество записей: {len(receipt_data)}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в файл: {e}")

# Загружаем данные при запуске
load_receipt_data()

@app.route('/')
def index():
    """Главная страница"""
    index_path = os.path.join(webapp_dir, 'index.html')
    return send_file(index_path)

@app.route('/health')
def health_check():
    """Проверка работоспособности API"""
    return jsonify({"status": "ok", "message": "API is running"})

@app.route('/<int:message_id>')
def index_with_message_id(message_id):
    """Обработка запроса с message_id в URL"""
    logger.info(f"Запрос страницы с message_id в URL: {message_id}")
    index_path = os.path.join(webapp_dir, 'index.html')
    logger.info(f"Полный путь к index.html: {index_path}")
    
    # Проверяем наличие файла
    if os.path.exists(index_path):
        logger.info(f"Файл index.html найден по пути: {index_path}")
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
    logger.info(f"Запрос данных чека для message_id: {message_id}")
    
    # Получаем user_id из query параметров, если есть
    user_id = request.args.get('user_id')
    logger.info(f"Запрос от user_id: {user_id}")
    
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
    
    # Создаем копию данных, чтобы не изменять оригинал
    result_data = receipt_data[message_id].copy()
    
    # Удаляем служебные метаданные из ответа
    if 'metadata' in result_data:
        del result_data['metadata']
    
    # Фильтруем user_selections, чтобы передавать только данные текущего пользователя
    if 'user_selections' in result_data and user_id:
        # Преобразуем user_id в строку для сравнения
        user_id_str = str(user_id)
        
        # Логируем состояние user_selections для отладки
        logger.info(f"User selections в хранилище: {result_data['user_selections']}")
        
        # Создаем новый словарь только с данными текущего пользователя
        filtered_selections = {}
        if user_id_str in result_data['user_selections']:
            # Получаем выборы текущего пользователя
            user_selections = result_data['user_selections'][user_id_str]
            logger.info(f"Найдены выборы для пользователя {user_id_str}: {user_selections}")
            filtered_selections[user_id_str] = user_selections
        else:
            logger.info(f"Выборы для пользователя {user_id_str} не найдены")
        
        result_data['user_selections'] = filtered_selections
    else:
        # Если user_id не указан или нет user_selections, возвращаем пустой словарь
        logger.info(f"Нет user_id или user_selections пуст, возвращаем пустой словарь")
        result_data['user_selections'] = {}
    
    logger.info(f"Отправка данных чека для message_id: {message_id}, user_id: {user_id}")
    return jsonify(result_data)

@app.route('/api/receipt/<int:message_id>', methods=['POST'])
def save_receipt_data(message_id):
    """Сохранение данных чека"""
    logger.info(f"Сохранение данных чека для message_id: {message_id}")
    
    try:
        if not request.is_json:
            logger.error(f"Получен не JSON-запрос. Content-Type: {request.content_type}")
            return jsonify({"error": "Expected JSON data"}), 400
            
        data = request.json
        logger.info(f"Получены данные: {str(data)[:200]}...")
        
        # Проверяем структуру данных
        if not isinstance(data, dict):
            logger.error(f"Получены данные неверного типа: {type(data).__name__}")
            return jsonify({"error": f"Expected dictionary, got {type(data).__name__}"}), 400
            
        if 'items' not in data:
            logger.error("В данных отсутствует обязательное поле 'items'")
            return jsonify({"error": "Missing required field 'items'"}), 400
        
        # Добавляем метаданные о времени создания и обновления
        if 'metadata' not in data:
            data['metadata'] = {
                'created_at': time.time(),
                'last_updated': time.time()
            }
        else:
            data['metadata']['last_updated'] = time.time()
            
        receipt_data[message_id] = data
        logger.info(f"Данные сохранены для message_id: {message_id}")
        
        # Сохраняем данные в файл после изменения
        save_receipt_data_to_file()
        return jsonify({"success": True, "message": "Data saved successfully"})
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/selection/<int:message_id>', methods=['POST'])
def save_user_selection(message_id):
    """Сохранение выбора пользователя"""
    logger.info(f"Сохранение выбора пользователя для message_id: {message_id}")
    
    try:
        if not request.is_json:
            logger.error(f"Получен не JSON-запрос. Content-Type: {request.content_type}")
            return jsonify({"error": "Expected JSON data"}), 400
            
        data = request.json
        logger.info(f"Получены данные выбора: {str(data)[:200]}...")
        
        user_id = data.get('user_id')
        if not user_id:
            logger.error("В запросе отсутствует обязательное поле 'user_id'")
            return jsonify({"error": "Missing required field 'user_id'"}), 400
            
        selected_items = data.get('selected_items')
        if not isinstance(selected_items, dict):
            logger.error(f"Поле 'selected_items' имеет неверный формат: {type(selected_items).__name__}")
            return jsonify({"error": f"Field 'selected_items' should be a dictionary"}), 400
        
        # Преобразуем все ключи selected_items в строки для единообразия
        selected_items_str_keys = {str(k): v for k, v in selected_items.items()}
        
        # Всегда преобразуем user_id в строку для использования в качестве ключа
        user_id_str = str(user_id)
        
        logger.info(f"Сохранение выбора для пользователя: {user_id_str}, выбранные товары: {selected_items_str_keys}")
        
        if message_id not in receipt_data:
            receipt_data[message_id] = {
                "items": [], 
                "user_selections": {},
                "metadata": {
                    'created_at': time.time(),
                    'last_updated': time.time()
                }
            }
        
        if 'user_selections' not in receipt_data[message_id]:
            receipt_data[message_id]['user_selections'] = {}
        
        # Обновляем время последнего обновления
        if 'metadata' not in receipt_data[message_id]:
            receipt_data[message_id]['metadata'] = {
                'created_at': time.time(),
                'last_updated': time.time()
            }
        else:
            receipt_data[message_id]['metadata']['last_updated'] = time.time()
            
        # Используем строковый user_id в качестве ключа
        receipt_data[message_id]['user_selections'][user_id_str] = selected_items_str_keys
        logger.info(f"Пользовательский выбор сохранен: {user_id_str} -> {selected_items_str_keys}")
        
        # Сохраняем данные в файл после изменения
        save_receipt_data_to_file()
        
        return jsonify({"success": True, "message": "Selection saved successfully"})
    except Exception as e:
        logger.error(f"Ошибка при сохранении выбора: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# Маршрут для очистки устаревших данных
@app.route('/maintenance/cleanup', methods=['POST'])
def trigger_cleanup():
    """Endpoint для запуска очистки устаревших данных"""
    try:
        # Получаем количество записей до очистки
        before_count = len(receipt_data)
        
        # Запускаем очистку
        cleanup_expired_data()
        
        # Получаем количество записей после очистки
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

# Добавляем маршрут для отладки
@app.route('/debug')
def debug():
    return jsonify({
        "receipt_data": receipt_data,
        "webapp_dir": webapp_dir,
        "current_dir": os.getcwd()
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080) 