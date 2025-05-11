import json
import logging
import base64
from decimal import Decimal, InvalidOperation
from openai import AsyncOpenAI
from config.settings import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MAX_TOKENS
from utils.helpers import parse_possible_price

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

def extract_items_from_openai_response(parsed_json_data: dict) -> tuple[list[dict] | None, Decimal | None, Decimal | None, Decimal | None, Decimal | None]:
    if not parsed_json_data or "items" not in parsed_json_data or not isinstance(parsed_json_data["items"], list):
        logger.warning(f"Неожиданный формат JSON от OpenAI или нет ключа 'items': {parsed_json_data}")
        return None, None, None, None, None
    processed_items = []
    for item_data in parsed_json_data["items"]:
        if isinstance(item_data, dict):
            # OpenAI может вернуть unit_price или total_amount как строки, пытаемся их привести к Decimal
            unit_price_dec = parse_possible_price(item_data.get("unit_price"))
            total_amount_dec = parse_possible_price(item_data.get("total_amount"))
            discount_percent_dec = parse_possible_price(item_data.get("discount_percent"))
            discount_amount_dec = parse_possible_price(item_data.get("discount_amount"))
            
            # Пытаемся получить quantity как число
            openai_quantity = 1 # По умолчанию
            raw_quantity = item_data.get("quantity", 1)
            if isinstance(raw_quantity, (int, float)):
                # Если количество дробное (весовой товар), устанавливаем количество 1
                if float(raw_quantity) != int(raw_quantity):
                    openai_quantity = 1
                else:
                    openai_quantity = int(raw_quantity)
            elif isinstance(raw_quantity, str):
                try:
                    openai_quantity_val_str = raw_quantity.lower().replace("шт", "").replace("szt", "").strip()
                    cleaned_quantity_str = "".join(filter(lambda x: x.isdigit() or x == '.', openai_quantity_val_str.split()[0]))
                    if cleaned_quantity_str:
                        parsed_q = float(cleaned_quantity_str)
                        # Если количество дробное (весовой товар), устанавливаем количество 1
                        if parsed_q != int(parsed_q):
                            openai_quantity = 1
                        else:
                            openai_quantity = int(parsed_q)
                except ValueError:
                    pass # openai_quantity останется 1
            
            processed_items.append({
                "description": str(item_data.get("description", "N/A")), # Убедимся, что описание - строка
                "quantity_from_openai": openai_quantity, 
                "unit_price_from_openai": unit_price_dec, # Decimal | None
                "total_amount_from_openai": total_amount_dec, # Decimal | None
                "discount_percent": discount_percent_dec, # Decimal | None
                "discount_amount": discount_amount_dec # Decimal | None
            })
        else:
            logger.warning(f"Найден элемент не-словарь в items: {item_data}")
    
    # Добавляем информацию о плате за обслуживание, если она есть
    service_charge = None
    if "service_charge_percent" in parsed_json_data:
        try:
            service_charge = Decimal(str(parsed_json_data["service_charge_percent"]))
        except (InvalidOperation, TypeError):
            logger.warning(f"Не удалось распарсить service_charge_percent: {parsed_json_data.get('service_charge_percent')}")
    
    # Получаем итоговую сумму чека
    total_check_amount = None
    if "total_check_amount" in parsed_json_data:
        try:
            total_check_amount = Decimal(str(parsed_json_data["total_check_amount"]))
        except (InvalidOperation, TypeError):
            logger.warning(f"Не удалось распарсить total_check_amount: {parsed_json_data.get('total_check_amount')}")
    
    # Получаем общую скидку на чек, если она есть (в процентах или абсолютном выражении)
    total_discount = None
    total_discount_amount = None
    
    if "total_discount_percent" in parsed_json_data:
        try:
            total_discount = Decimal(str(parsed_json_data["total_discount_percent"]))
        except (InvalidOperation, TypeError):
            logger.warning(f"Не удалось распарсить total_discount_percent: {parsed_json_data.get('total_discount_percent')}")
    elif "total_discount_amount" in parsed_json_data:
        try:
            total_discount_amount = Decimal(str(parsed_json_data["total_discount_amount"]))
        except (InvalidOperation, TypeError):
            logger.warning(f"Не удалось распарсить total_discount_amount: {parsed_json_data.get('total_discount_amount')}")
    
    return processed_items, service_charge, total_check_amount, total_discount, total_discount_amount

async def process_receipt_with_openai(image_data: bytes) -> tuple[list[dict] | None, Decimal | None, Decimal | None, Decimal | None, Decimal | None]:
    try:
        # Кодируем изображение в base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        logger.info(f"Изображение закодировано, размер base64: {len(base64_image)} символов")
        
        # Подготавливаем промпт для GPT-4 Vision
        prompt = """Ты - эксперт по анализу чеков. Твоя задача - извлечь из изображения чека информацию о товарах, ценах, количестве, скидках и итоговой сумме.
        ВАЖНО: Ты должен вернуть данные в строго определенном JSON формате. Не добавляй никаких пояснений, только JSON.
        Формат ответа:
        {
            "items": [
                {
                    "description": "Название товара",
                    "quantity": "Количество (число или строка, например '2' или '2 шт')",
                    "unit_price": "Цена за единицу (число)",
                    "total_amount": "Общая сумма за позицию (число)",
                    "discount_percent": "Скидка в процентах (число, опционально)",
                    "discount_amount": "Сумма скидки (число, опционально)"
                }
            ],
            "service_charge_percent": "Процент за обслуживание (число, опционально)",
            "total_check_amount": "Итоговая сумма чека (число)",
            "total_discount_percent": "Общая скидка в процентах (число, опционально)",
            "total_discount_amount": "Общая сумма скидки (число, опционально)"
        }
        
        Правила обработки:
        1. Если в чеке указано количество товара (например, "2 шт" или "2"), используй его
        2. Если количество не указано явно, но есть общая сумма и цена за единицу, вычисли количество
        3. Если товар весовой (указан вес, например "0.5 кг"), укажи количество как есть
        4. Все цены должны быть числами, без валюты
        5. Если есть скидки на отдельные товары, укажи их в соответствующих полях
        6. Если есть общая скидка на чек, укажи её в total_discount_percent или total_discount_amount
        7. Если есть плата за обслуживание, укажи её в service_charge_percent
        
        ВАЖНО: Верни ТОЛЬКО JSON, без дополнительного текста."""
        
        # Отправляем запрос к API
        logger.info(f"Отправляем запрос на анализ изображения в OpenAI, используя модель: {OPENAI_MODEL}")
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=OPENAI_MAX_TOKENS
        )
        
        # Получаем ответ
        response_text = response.choices[0].message.content
        logger.info(f"Получен ответ от OpenAI, длина текста: {len(response_text)} символов")
        
        # Пытаемся распарсить JSON
        try:
            # Удаляем маркеры markdown, если они есть
            if response_text.strip().startswith("```json"):
                # Удаляем открывающие ``` и закрывающие ```
                json_start = response_text.find("{")
                json_end = response_text.rfind("}")
                if json_start != -1 and json_end != -1:
                    response_text = response_text[json_start:json_end+1]
                else:
                    # Если не найдены фигурные скобки, попробуем просто убрать тройные кавычки
                    response_text = response_text.strip().replace("```json", "").replace("```", "").strip()
            
            logger.info(f"Подготовленный текст для парсинга JSON: {response_text[:100]}...")
            parsed_json_data = json.loads(response_text)
            logger.info(f"JSON успешно распарсен, найдено товаров: {len(parsed_json_data.get('items', []))}")
            return extract_items_from_openai_response(parsed_json_data)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка при парсинге JSON от OpenAI: {e}")
            logger.error(f"Полученный текст: {response_text}")
            return None, None, None, None, None
            
    except Exception as e:
        logger.error(f"Ошибка при обработке чека через OpenAI: {e}", exc_info=True)
        return None, None, None, None, None 