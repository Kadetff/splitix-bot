import os
import json
import logging
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import traceback

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
            logger.info(f"Загрузка данных из файла: {data_file}")
            
            with open(data_file, 'r', encoding='utf-8') as f:
                try:
                    loaded_data = json.load(f)
                    logger.info(f"Данные успешно загружены из файла, размер: {len(loaded_data)} записей")
                    logger.info(f"Типы ключей в исходных данных: {[type(k).__name__ for k in loaded_data.keys()]}")
                    
                    # Проверяем структуру данных и добавляем метаданные, если их нет
                    clean_data = {}
                    for msg_id, msg_data in loaded_data.items():
                        # Все ключи должны быть строками для единообразия
                        str_msg_id = str(msg_id)
                        logger.debug(f"Обработка записи для message_id: {msg_id} -> {str_msg_id}")
                        
                        # Если есть поле 'created_at', используем его, иначе добавляем текущее время
                        if isinstance(msg_data, dict):
                            if 'metadata' not in msg_data:
                                logger.debug(f"Добавляем метаданные для message_id: {str_msg_id}")
                                msg_data['metadata'] = {
                                    'created_at': time.time(),  # Текущее время в секундах
                                    'last_updated': time.time()
                                }
                            
                            # Проверяем и конвертируем user_selections для гарантии строковых ключей
                            if 'user_selections' in msg_data:
                                logger.debug(f"Обработка user_selections для message_id: {str_msg_id}")
                                
                                # Логируем структуру user_selections до обработки
                                logger.debug(f"user_selections до обработки: {msg_data['user_selections']}")
                                logger.debug(f"Типы ключей user_selections: {[type(k).__name__ for k in msg_data['user_selections'].keys()]}")
                                
                                fixed_user_selections = {}
                                for user_id, selections in msg_data['user_selections'].items():
                                    # Преобразуем user_id в строку
                                    user_id_str = str(user_id)
                                    logger.debug(f"Обработка selections для user_id: {user_id} -> {user_id_str}")
                                    
                                    # Преобразуем ключи выбора товаров в строки, а значения в целые числа
                                    if selections:
                                        # Логируем типы ключей и значений до обработки
                                        logger.debug(f"Типы ключей в selections: {[type(k).__name__ for k in selections.keys()]}")
                                        logger.debug(f"Типы значений в selections: {[type(v).__name__ for v in selections.values()]}")
                                        
                                        fixed_selections = {}
                                        for k, v in selections.items():
                                            str_k = str(k)
                                            try:
                                                int_v = int(v)
                                                fixed_selections[str_k] = int_v
                                            except (ValueError, TypeError) as e:
                                                logger.error(f"Ошибка при преобразовании значения '{v}' типа {type(v).__name__} в int: {e}")
                                                # В случае ошибки используем значение как есть
                                                fixed_selections[str_k] = v
                                        
                                        fixed_user_selections[user_id_str] = fixed_selections
                                        logger.debug(f"Обработанные selections для user_id {user_id_str}: {fixed_selections}")
                                    else:
                                        logger.debug(f"Пустые selections для user_id {user_id_str}")
                                        fixed_user_selections[user_id_str] = {}
                                
                                # Заменяем user_selections на исправленную версию
                                msg_data['user_selections'] = fixed_user_selections
                                logger.debug(f"user_selections после обработки: {fixed_user_selections}")
                                
                            clean_data[str_msg_id] = msg_data
                    
                    receipt_data = clean_data
                    logger.info(f"Загружены данные из {data_file}, количество записей: {len(receipt_data)}")
                    logger.info(f"Ключи receipt_data после загрузки: {list(receipt_data.keys())}")
                    
                    # Логируем состояние user_selections для отладки
                    for msg_id, msg_data in receipt_data.items():
                        if 'user_selections' in msg_data:
                            logger.info(f"user_selections для message_id {msg_id}: {msg_data['user_selections']}")
                    
                    # Очищаем устаревшие данные
                    cleanup_expired_data()
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка при парсинге JSON из файла {data_file}: {e}")
                    receipt_data = {}
        else:
            logger.info(f"Файл данных {data_file} не существует, используем пустое хранилище.")
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных из файла: {e}", exc_info=True)
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
            logger.info(f"Создана директория для данных: {data_dir}")
        
        # Логируем информацию о структуре данных перед сохранением
        logger.info(f"Сохранение данных в файл {data_file}, количество записей: {len(receipt_data)}")
        logger.info(f"Ключи receipt_data: {list(receipt_data.keys())}")
        
        # Проверяем типы ключей
        if any(not isinstance(k, str) for k in receipt_data.keys()):
            logger.warning("Обнаружены не строковые ключи в receipt_data, преобразуем их в строки")
            # Преобразуем все ключи в строки
            receipt_data_fixed = {str(k): v for k, v in receipt_data.items()}
            # Заменяем оригинальные данные
            receipt_data.clear()
            receipt_data.update(receipt_data_fixed)
            logger.info("Ключи receipt_data преобразованы в строки")
        
        # Проверяем типы значений в user_selections
        for msg_id, msg_data in receipt_data.items():
            if 'user_selections' in msg_data:
                user_selections = msg_data['user_selections']
                # Проверяем ключи user_selections
                if any(not isinstance(k, str) for k in user_selections.keys()):
                    logger.warning(f"Обнаружены не строковые ключи в user_selections для message_id {msg_id}")
                    # Преобразуем все ключи в строки
                    user_selections_fixed = {str(k): v for k, v in user_selections.items()}
                    msg_data['user_selections'] = user_selections_fixed
                
                # Проверяем значения в каждом user_selection
                for user_id, selections in list(user_selections.items()):
                    # Проверяем ключи selections
                    if any(not isinstance(k, str) for k in selections.keys()):
                        logger.warning(f"Обнаружены не строковые ключи в selections для user_id {user_id}")
                        # Преобразуем все ключи в строки
                        selections_fixed = {str(k): v for k, v in selections.items()}
                        user_selections[user_id] = selections_fixed
                    
                    # Проверяем значения selections
                    if any(not isinstance(v, int) for v in selections.values()):
                        logger.warning(f"Обнаружены не целочисленные значения в selections для user_id {user_id}")
                        # Преобразуем все значения в числа
                        selections_fixed = {}
                        for k, v in selections.items():
                            try:
                                selections_fixed[k] = int(v)
                            except (ValueError, TypeError):
                                logger.error(f"Не удалось преобразовать значение '{v}' в int, используем 0")
                                selections_fixed[k] = 0
                        user_selections[user_id] = selections_fixed
        
        # Сохраняем данные в файл
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(receipt_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Данные успешно сохранены в файл {data_file}, количество записей: {len(receipt_data)}")
            
            # Проверяем структуру сохраненных данных для отладки
            for msg_id, msg_data in receipt_data.items():
                if 'user_selections' in msg_data:
                    logger.debug(f"Сохранены user_selections для message_id {msg_id}: {msg_data['user_selections']}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в файл: {e}", exc_info=True)

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
    
    # Преобразуем message_id в строку для единообразия
    message_id_str = str(message_id)
    logger.info(f"Преобразованный message_id в строку: {message_id_str}")
    
    # Получаем user_id из query параметров, если есть
    user_id = request.args.get('user_id')
    logger.info(f"Запрос от user_id: {user_id}")
    
    # Детальное логирование структуры хранилища данных
    logger.info(f"Доступные ключи в receipt_data: {list(receipt_data.keys())}")
    
    if message_id_str not in receipt_data:
        logger.warning(f"message_id_str {message_id_str} не найден в receipt_data")
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
    result_data = receipt_data[message_id_str].copy()
    logger.info(f"Найдены данные для message_id_str {message_id_str}, ключи: {list(result_data.keys())}")
    
    # Удаляем служебные метаданные из ответа
    if 'metadata' in result_data:
        del result_data['metadata']
    
    # Фильтруем user_selections, чтобы передавать только данные текущего пользователя
    if 'user_selections' in result_data and user_id:
        # Преобразуем user_id в строку для сравнения
        user_id_str = str(user_id)
        logger.info(f"Преобразованный user_id в строку: {user_id_str}")
        
        # Логируем состояние user_selections для отладки
        logger.info(f"User selections в хранилище: {result_data['user_selections']}")
        logger.info(f"Доступные ключи в user_selections: {list(result_data['user_selections'].keys())}")
        
        # Создаем новый словарь только с данными текущего пользователя
        filtered_selections = {}
        if user_id_str in result_data['user_selections']:
            # Получаем выборы текущего пользователя
            user_selections = result_data['user_selections'][user_id_str]
            logger.info(f"Найдены выборы для пользователя {user_id_str}: {user_selections}")
            
            # Убедимся, что все ключи - строки, а все значения - числа
            normalized_selections = {str(k): int(v) for k, v in user_selections.items()}
            filtered_selections[user_id_str] = normalized_selections
            logger.info(f"Нормализованные выборы: {normalized_selections}")
        else:
            logger.info(f"Выборы для пользователя {user_id_str} не найдены")
        
        result_data['user_selections'] = filtered_selections
    else:
        # Если user_id не указан или нет user_selections, возвращаем пустой словарь
        logger.info(f"Нет user_id или user_selections пуст, возвращаем пустой словарь")
        result_data['user_selections'] = {}
    
    logger.info(f"Отправка данных чека для message_id: {message_id}, user_id: {user_id}")
    logger.info(f"Итоговые данные: {json.dumps(result_data)[:500]}...")
    return jsonify(result_data)

@app.route('/api/receipt/<int:message_id>', methods=['POST'])
def save_receipt_data(message_id):
    """Сохранение данных чека"""
    logger.info(f"Сохранение данных чека для message_id: {message_id}")
    
    # Преобразуем message_id в строку для единообразия
    message_id_str = str(message_id)
    
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
            
        receipt_data[message_id_str] = data
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
    
    # Преобразуем message_id в строку для единообразия
    message_id_str = str(message_id)
    logger.info(f"Преобразованный message_id в строку: {message_id_str}")
    
    try:
        if not request.is_json:
            logger.error(f"Получен не JSON-запрос. Content-Type: {request.content_type}")
            return jsonify({"error": "Expected JSON data"}), 400
            
        data = request.json
        logger.info(f"Получены данные выбора: {json.dumps(data)}")
        
        user_id = data.get('user_id')
        if not user_id:
            logger.error("В запросе отсутствует обязательное поле 'user_id'")
            return jsonify({"error": "Missing required field 'user_id'"}), 400
            
        selected_items = data.get('selected_items')
        if not isinstance(selected_items, dict):
            logger.error(f"Поле 'selected_items' имеет неверный формат: {type(selected_items).__name__}")
            return jsonify({"error": f"Field 'selected_items' should be a dictionary"}), 400
        
        # Преобразуем все ключи selected_items в строки и все значения в числа для единообразия
        selected_items_str_keys = {str(k): int(v) for k, v in selected_items.items()}
        
        # Всегда преобразуем user_id в строку для использования в качестве ключа
        user_id_str = str(user_id)
        
        logger.info(f"Сохранение выбора для пользователя: {user_id_str}, выбранные товары: {selected_items_str_keys}")
        
        if message_id_str not in receipt_data:
            logger.info(f"Создание новой записи для message_id: {message_id_str}")
            receipt_data[message_id_str] = {
                "items": [], 
                "user_selections": {},
                "metadata": {
                    'created_at': time.time(),
                    'last_updated': time.time()
                }
            }
        
        if 'user_selections' not in receipt_data[message_id_str]:
            logger.info(f"Инициализация user_selections для message_id: {message_id_str}")
            receipt_data[message_id_str]['user_selections'] = {}
        
        # Обновляем время последнего обновления
        if 'metadata' not in receipt_data[message_id_str]:
            receipt_data[message_id_str]['metadata'] = {
                'created_at': time.time(),
                'last_updated': time.time()
            }
        else:
            receipt_data[message_id_str]['metadata']['last_updated'] = time.time()
            
        # Используем строковый user_id в качестве ключа
        receipt_data[message_id_str]['user_selections'][user_id_str] = selected_items_str_keys
        logger.info(f"Пользовательский выбор сохранен: {user_id_str} -> {selected_items_str_keys}")
        
        # Сохраняем данные в файл после изменения
        save_receipt_data_to_file()
        
        # Выводим структуру после сохранения
        logger.info(f"Структура user_selections после сохранения: {receipt_data[message_id_str]['user_selections']}")
        
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

# Маршрут для тестирования сохранения выбора пользователя
@app.route('/test_selection_persistence')
def test_selection_persistence():
    """Тестирование сохранения и загрузки выбора пользователя"""
    try:
        test_message_id = "12345"  # Используем строковый ключ
        test_user_id = "67890"
        test_selection = {"0": 1, "1": 2, "2": 3}
        
        # Сохраняем тестовые данные
        if test_message_id not in receipt_data:
            receipt_data[test_message_id] = {
                "items": [
                    {"id": 0, "description": "Тестовый товар 1", "quantity_from_openai": 2, "unit_price_from_openai": 150.00, "total_amount_from_openai": 300.00},
                    {"id": 1, "description": "Тестовый товар 2", "quantity_from_openai": 1, "unit_price_from_openai": 180.00, "total_amount_from_openai": 180.00},
                    {"id": 2, "description": "Тестовый товар 3", "quantity_from_openai": 3, "unit_price_from_openai": 350.00, "total_amount_from_openai": 1050.00}
                ],
                "user_selections": {},
                "metadata": {
                    'created_at': time.time(),
                    'last_updated': time.time()
                }
            }
        
        # Сохраняем тестовый выбор пользователя
        receipt_data[test_message_id]['user_selections'][test_user_id] = test_selection
        logger.info(f"Тестовый выбор сохранен: {test_user_id} -> {test_selection}")
        
        # Сохраняем данные в файл
        save_receipt_data_to_file()
        
        # Проверяем существование файла данных
        file_exists = os.path.exists(data_file)
        file_size = os.path.getsize(data_file) if file_exists else 0
        file_content = None
        if file_exists and file_size > 0:
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    file_content = json.load(f)
            except Exception as e:
                logger.error(f"Ошибка при чтении файла: {e}")
                file_content = f"Ошибка: {str(e)}"
        
        # Очищаем данные в памяти для тестирования загрузки
        before_clear = dict(receipt_data)
        receipt_data.clear()
        logger.info("Данные очищены в памяти для тестирования загрузки из файла")
        
        # Загружаем данные из файла
        load_receipt_data()
        
        # Проверяем загруженные данные
        after_load = dict(receipt_data)
        user_selections_in_loaded_data = receipt_data.get(test_message_id, {}).get('user_selections', {})
        loaded_selection = user_selections_in_loaded_data.get(test_user_id) if user_selections_in_loaded_data else None
        logger.info(f"Загруженный выбор: {loaded_selection}")
        
        # Подготавливаем отчет
        report = {
            "success": loaded_selection == test_selection,
            "message": "Тест пройден успешно" if loaded_selection == test_selection else "Тест не пройден",
            "test_data": {
                "saved": test_selection,
                "loaded": loaded_selection,
                "file_exists": file_exists,
                "file_size": file_size,
                "file_content": file_content,
                "data_before_clear": before_clear,
                "data_after_load": after_load,
                "receipt_data_keys": list(receipt_data.keys()),
                "user_selections_in_loaded_data": user_selections_in_loaded_data
            }
        }
        
        # Если нет выбора пользователя, добавляем более детальную причину
        if not loaded_selection:
            if test_message_id not in receipt_data:
                report["reason"] = f"Message ID {test_message_id} не найден в загруженных данных"
            elif 'user_selections' not in receipt_data.get(test_message_id, {}):
                report["reason"] = f"user_selections не найден в данных для message_id {test_message_id}"
            elif test_user_id not in receipt_data.get(test_message_id, {}).get('user_selections', {}):
                report["reason"] = f"User ID {test_user_id} не найден в user_selections для message_id {test_message_id}"
        
        return jsonify(report)
            
    except Exception as e:
        logger.error(f"Ошибка при тестировании: {e}", exc_info=True)
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route('/test_key_types')
def test_key_types():
    """Эндпоинт для проверки типов ключей в хранилище данных."""
    try:
        result = {
            "receipt_data_keys": {k: type(k).__name__ for k in receipt_data.keys()},
            "user_selections": {}
        }
        
        # Проверяем типы ключей и значений в user_selections
        for msg_id, msg_data in receipt_data.items():
            if 'user_selections' in msg_data:
                # Получаем информацию о типах ключей в user_selections
                user_selections = msg_data['user_selections']
                user_keys_info = {user_id: type(user_id).__name__ for user_id in user_selections.keys()}
                
                # Получаем информацию о типах ключей и значений в selections
                selections_info = {}
                for user_id, selections in user_selections.items():
                    if selections:
                        keys_info = {k: type(k).__name__ for k in selections.keys()}
                        values_info = {k: type(v).__name__ for k, v in selections.items()}
                        selections_info[user_id] = {
                            "keys_types": keys_info,
                            "values_types": values_info,
                            "data": selections
                        }
                
                result["user_selections"][msg_id] = {
                    "user_keys_types": user_keys_info,
                    "selections": selections_info
                }
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Ошибка при проверке типов ключей: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080) 