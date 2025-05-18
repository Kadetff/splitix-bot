import json
import time
import logging
from typing import Dict, Any, Optional
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

def convert_to_string_keys(data: Dict) -> Dict:
    """Преобразует все ключи словаря в строки."""
    return {str(k): v for k, v in data.items()}

def convert_selections_to_int(selections: Dict) -> Dict:
    """Преобразует значения в selections в целые числа."""
    fixed_selections = {}
    for k, v in selections.items():
        str_k = str(k)
        try:
            int_v = int(v)
            fixed_selections[str_k] = int_v
        except (ValueError, TypeError) as e:
            logger.error(f"Ошибка при преобразовании значения '{v}' в int: {e}")
            fixed_selections[str_k] = v
    return fixed_selections

def add_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Добавляет метаданные к данным."""
    if 'metadata' not in data:
        data['metadata'] = {
            'created_at': time.time(),
            'last_updated': time.time()
        }
    return data

def validate_and_fix_user_selections(data: Dict[str, Any]) -> Dict[str, Any]:
    """Проверяет и исправляет структуру user_selections."""
    if 'user_selections' in data:
        fixed_user_selections = {}
        for user_id, selections in data['user_selections'].items():
            user_id_str = str(user_id)
            if selections:
                fixed_selections = convert_selections_to_int(selections)
                fixed_user_selections[user_id_str] = fixed_selections
            else:
                fixed_user_selections[user_id_str] = {}
        data['user_selections'] = fixed_user_selections
    return data

def is_data_expired(created_at: float, expiration_days: int = 7) -> bool:
    """Проверяет, истек ли срок хранения данных."""
    now = time.time()
    age_days = (now - created_at) / (60 * 60 * 24)
    return age_days > expiration_days

def load_json_data(file_path: str) -> Dict:
    """Загружает и валидирует данные из JSON файла."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Преобразуем все ключи в строки
            data = convert_to_string_keys(data)
            # Добавляем метаданные и валидируем user_selections
            for msg_id, msg_data in data.items():
                data[msg_id] = validate_and_fix_user_selections(add_metadata(msg_data))
            return data
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при парсинге JSON: {e}")
        return {}
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных: {e}")
        return {}

def save_json_data(data: Dict, file_path: str) -> bool:
    """Сохраняет данные в JSON файл с валидацией."""
    try:
        # Валидируем и фиксим данные перед сохранением
        fixed_data = convert_to_string_keys(data)
        for msg_id, msg_data in fixed_data.items():
            fixed_data[msg_id] = validate_and_fix_user_selections(msg_data)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(fixed_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}")
        return False

def parse_possible_price(price_value: any) -> Decimal | None:
    """Упрощенная версия парсинга цены."""
    if price_value is None:
        return None
    if isinstance(price_value, (int, float)):
        return Decimal(str(price_value))
    if isinstance(price_value, str):
        try:
            cleaned_str = price_value.strip().replace(',', '.')
            return Decimal(cleaned_str)
        except InvalidOperation:
            return None
    return None 