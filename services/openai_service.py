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
    logger.info("Начало извлечения данных из ответа OpenAI.")
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
    total_discount_percent = None
    total_discount_amount = None
    
    if "total_discount_percent" in parsed_json_data:
        try:
            total_discount_percent = Decimal(str(parsed_json_data["total_discount_percent"]))
        except (InvalidOperation, TypeError):
            logger.warning(f"Не удалось распарсить total_discount_percent: {parsed_json_data.get('total_discount_percent')}")
    
    if "total_discount_amount" in parsed_json_data:
        try:
            total_discount_amount = Decimal(str(parsed_json_data["total_discount_amount"]))
        except (InvalidOperation, TypeError):
            logger.warning(f"Не удалось распарсить total_discount_amount: {parsed_json_data.get('total_discount_amount')}")
    
    logger.info(f"Извлечено {len(processed_items)} товаров из ответа OpenAI.")
    logger.info(f"service_charge: {service_charge}; total_check_amount: {total_check_amount}; total_discount_amount: {total_discount_amount}; total_discount_percent: {total_discount_percent}")
    return processed_items, service_charge, total_check_amount, total_discount_percent, total_discount_amount

async def process_receipt_with_openai(image_data: bytes) -> tuple[list[dict] | None, Decimal | None, Decimal | None, Decimal | None, Decimal | None]:
    try:
        # Кодируем изображение в base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        logger.info(f"Изображение закодировано, размер base64: {len(base64_image)} символов")
        
        # Подготавливаем промпт для GPT-4 Vision
        prompt = """
        Ты — эксперт по анализу кассовых чеков. Проанализируй изображение чека и извлеки из него информацию о товарных позициях, скидках, плате за обслуживание и итоговой сумме. 
        Верни ТОЛЬКО валидный JSON-объект без пояснений. Структура:
        {
        "items": [
            {
            "description": "строка",
            "quantity": число,
            "unit_price": число (опц.),
            "total_amount": число,
            "discount_percent": число (опц.),
            "discount_amount": число (опц.)
            }
        ],
        "service_charge_percent": число (опц.),
        "total_discount_percent": число (опц.),
        "total_discount_amount": число (опц.),
        "total_check_amount": число
        }
        Правила:
        1. Объединяй одинаковые позиции с совпадающим названием и ценой.
        2. quantity — всегда число. «2 шт» → 2, «0.5 кг» → 0.5.
        3. Если quantity не указано, но есть unit_price и total_amount — вычисли quantity.
        4. Если unit_price не указана — опусти поле.
        5. discount_percent / discount_amount — только если явно указано или вычисляемо.
        6. Общая скидка — в total_discount_percent или total_discount_amount.
        7. service_charge_percent — если есть сервисный сбор.
        8. VAT / НДС — не считать скидкой.
        9. Все числа — тип float или int, только точка как разделитель.
        10. Если не можешь определить значение — используй null или не включай поле.
        11. Если нельзя с уверенностью определить, к какому товару относится скидка, не указывай её в item.discount_amount, а отнеси в общую total_discount_amount.
        ВАЖНО: Верни ТОЛЬКО JSON, без текста до или после.
        """
        
        # Отправляем запрос к API
        logger.info(f"Отправляем запрос на анализ изображения в OpenAI, используя модель: {OPENAI_MODEL}")
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0,
            top_p=1,
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
        logger.info(f"Полный ответ OpenAI:\n{response_text}")
        
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