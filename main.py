import asyncio
import logging
import io
import os
import base64 # Для кодирования изображения
import json   # Для работы с JSON от OpenAI
from typing import Any, cast
from decimal import Decimal, InvalidOperation # Для точной работы с деньгами

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F # Добавили F для фильтров
from aiogram.filters import CommandStart
from aiogram.types import Message, PhotoSize, InlineKeyboardMarkup, InlineKeyboardButton # Добавили инлайн клавиатуры
from aiogram.utils.keyboard import InlineKeyboardBuilder # Удобный построитель клавиатур
from aiogram.fsm.storage.memory import MemoryStorage
from config.settings import TELEGRAM_BOT_TOKEN, LOG_LEVEL
from handlers import photo, callbacks, commands

from openai import AsyncOpenAI # Асинхронный клиент OpenAI

# Загружаем переменные окружения из .env файла
load_dotenv()

# Включим логирование, чтобы видеть ошибки
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# Получаем токен бота из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logger.error("Ошибка: TELEGRAM_BOT_TOKEN не найден в .env файле!")
    exit()

# --- OpenAI API Key --- 
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("Ошибка: OPENAI_API_KEY не найден в .env файле!")
    exit()

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- OpenAI Client Setup --- 
openai_client = None
try:
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    logger.info("Клиент OpenAI инициализирован.")
except Exception as e:
    logger.error(f"Ошибка инициализации клиента OpenAI: {e}")
    exit()

# Словарь для хранения состояния (items и их счетчики) для каждого сообщения с клавиатурой
# Ключ: message_id сообщения бота с клавиатурой
# Значение: {"items": list_of_item_dicts, "user_selections": {user_id: {item_idx: count}}}
message_states: dict[int, dict[str, Any]] = {} # Type hint remains general for simplicity, but structure changes

# Экспорт message_states для использования в обработчиках
from handlers import callbacks, photo
callbacks.message_states = message_states
photo.message_states = message_states

def create_openai_prompt(base64_image_data: str) -> list:
    """Создает промпт для OpenAI Vision API."""
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Проанализируй это изображение чека. Извлеки все товарные позиции, информацию о плате за обслуживание (service charge), "
                        "скидках (discounts) и итоговую сумму чека (total_check_amount). "
                        "Если в чеке есть несколько одинаковых позиций (с одинаковым наименованием и ценой), объедини их в одну позицию, "
                        "суммировав количество. Например, если в чеке есть три строки 'Пицца Маргарита 1 шт. 500р', "
                        "объедини их в одну позицию 'Пицца Маргарита' с количеством 3 и ценой 500р за единицу. "
                        "Для каждой позиции предоставь описание (description), общее количество в чеке (quantity, если есть, иначе 1), "
                        "цену за единицу (unit_price, если есть), общую сумму по позиции в чеке (total_amount) и скидку на эту позицию "
                        "(discount_percent в процентах или discount_amount в абсолютном выражении, если есть). "
                        "Если в чеке есть плата за обслуживание (service charge) или сервисный сбор, укажи её в процентах в поле service_charge_percent. "
                        "Если платы за обслуживание нет, просто не включай это поле в результат. "
                        "Если в чеке есть общая скидка на весь чек (например, скидка за день рождения или счастливые часы), "
                        "укажи её в поле total_discount_percent (если скидка в процентах) или total_discount_amount (если скидка в абсолютном выражении). "
                        "Важно: НДС/VAT - это налог, а не скидка, поэтому не включай его в поля discount_percent или discount_amount. "
                        "Все числовые значения (quantity, unit_price, total_amount, service_charge_percent, total_check_amount, "
                        "discount_percent, discount_amount, total_discount_percent, total_discount_amount) "
                        "должны быть числами (int или float), а не строками, если это возможно. Запятые в числах должны быть заменены на точки." 
                        "Верни результат в виде JSON-объекта со списком items, опциональными полями service_charge_percent, "
                        "total_discount_percent/total_discount_amount и обязательным полем total_check_amount. "
                        "Каждый элемент списка items должен быть объектом со следующими ключами: "
                        "'description' (строка), 'quantity' (число), 'unit_price' (число, опционально), 'total_amount' (число), "
                        "'discount_percent' (число, опционально), 'discount_amount' (число, опционально)."
                        "Если не можешь определить какое-то числовое значение, используй null или пропусти ключ. "
                        "Пример JSON: {\"items\": [{\"description\": \"Пицца Маргарита\", \"quantity\": 3, \"unit_price\": 500.00, \"total_amount\": 1500.00, \"discount_percent\": 20}, {\"description\": \"Молоко 3.2%\", \"quantity\": 1, \"unit_price\": 75.00, \"total_amount\": 75.00}], \"service_charge_percent\": 10, \"total_discount_amount\": 370.00, \"total_check_amount\": 1472.63}. "
                        "Убедись, что весь твой ответ является валидным JSON объектом, начинающимся с { и заканчивающимся }."
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image_data}",
                        "detail": "auto"
                    }
                }
            ]
        }
    ]

def parse_possible_price(price_value: Any) -> Decimal | None:
    """Пытается распарсить значение цены в Decimal, обрабатывая строки с запятыми/точками."""
    if price_value is None: return None
    if isinstance(price_value, (int, float)): 
        return Decimal(str(price_value))
    if isinstance(price_value, str):
        try:
            # Убираем пробелы, заменяем запятые, если это разделитель тысяч - убираем (сложно без контекста)
            # Для простоты предполагаем, что запятая - это десятичный разделитель, если нет точки
            # Или если есть точка, то запятые - это разделители тысяч (удаляем)
            cleaned_str = price_value.strip()
            if '.' in cleaned_str and ',' in cleaned_str:
                 cleaned_str = cleaned_str.replace(',', '') # Удаляем запятые-тысячные
            elif ',' in cleaned_str:
                 cleaned_str = cleaned_str.replace(',', '.') # Заменяем запятую-десятичную на точку
            return Decimal(cleaned_str)
        except InvalidOperation:
            return None
    return None

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

def create_items_keyboard_with_counters(items: list[dict], user_specific_counts: dict[int, int], view_mode: str = "default") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, item in enumerate(items):
        description = item.get("description", "N/A")
        current_selection_count = user_specific_counts.get(idx, 0) 
        openai_quantity = item.get("quantity_from_openai", 1)
        unit_price_openai = item.get("unit_price_from_openai")
        total_amount_openai = item.get("total_amount_from_openai")
        
        # Определяем, является ли товар весовым
        is_weight_item = False
        if openai_quantity == 1 and total_amount_openai is not None and unit_price_openai is not None:
            # Проверяем, есть ли расхождение между total_amount и unit_price
            # с учетом возможного округления (разница не более 0.01)
            price_diff = abs(total_amount_openai - unit_price_openai)
            is_weight_item = price_diff > Decimal("0.01")
        
        # Логика отображения цены
        price_display = None
        if is_weight_item and total_amount_openai is not None:
            # Для весовых товаров показываем total_amount напрямую
            price_display = total_amount_openai
        elif unit_price_openai is not None:
            # Для обычных товаров показываем цену за единицу
            price_display = unit_price_openai
        elif total_amount_openai is not None and openai_quantity > 0:
            try:
                # Для обычных товаров с количеством > 1 показываем цену за единицу
                price_display = total_amount_openai / Decimal(str(openai_quantity))
            except (InvalidOperation, ZeroDivisionError):
                pass
            
        price_str = f" - {price_display:.2f}" if price_display is not None else ""
        
        # Иконка галочки, если количество выбрано полностью
        checkmark_icon = "✅ " if current_selection_count == openai_quantity and openai_quantity > 0 else ""
        
        button_text = f"{checkmark_icon}[{current_selection_count}/{openai_quantity}] {description[:30]}{price_str}"
        builder.row(InlineKeyboardButton(text=button_text, callback_data=f"increment_item:{idx}")) 
    
    if view_mode == "default":
        builder.row(InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="confirm_selection"))
        builder.row(InlineKeyboardButton(text="📊 Мой текущий выбор", callback_data="show_my_summary"))
        builder.row(InlineKeyboardButton(text="📈 Общий итог по чеку", callback_data="show_total_summary"))
    elif view_mode == "total_summary_display":
        builder.row(InlineKeyboardButton(text="⬅️ Назад к моему выбору", callback_data="back_to_selection"))
    elif view_mode == "my_summary_display":
        builder.row(InlineKeyboardButton(text="⬅️ Назад к выбору", callback_data="back_to_selection"))

    return builder.as_markup()

@dp.message(CommandStart())
async def send_welcome(message: Message):
    """Отправляет приветственное сообщение при команде /start."""
    await message.reply(
        "Привет! Отправь мне фотографию чека, и я попробую распознать его с помощью OpenAI."
    )

@dp.callback_query(F.data.startswith("increment_item:"))
async def handle_item_increment(callback_query: types.CallbackQuery):
    try:
        user_id = callback_query.from_user.id
        _, item_idx_str = callback_query.data.split(":")
        item_idx = int(item_idx_str)

        message = callback_query.message
        if not message:
            await callback_query.answer("Не удалось обновить: исходное сообщение не найдено.")
            return

        current_message_id = message.message_id
        if current_message_id not in message_states or "items" not in message_states[current_message_id]:
            logger.warning(f"Состояние (или items) для message_id {current_message_id} не найдено в message_states.")
            await callback_query.answer("Состояние для этого списка не найдено. Возможно, он устарел.", show_alert=True)
            return

        state_data_for_message = message_states[current_message_id]
        items = state_data_for_message["items"]
        
        # Получаем или инициализируем словарь выборов для текущего пользователя
        user_selections_for_message = state_data_for_message.setdefault("user_selections", {})
        current_user_counts = user_selections_for_message.setdefault(user_id, {})

        if item_idx < 0 or item_idx >= len(items):
            logger.error(f"Неверный item_idx {item_idx} для message_id {current_message_id}, user_id {user_id}")
            await callback_query.answer("Ошибка: неверный индекс позиции.")
            return
        
        item_info = items[item_idx]
        openai_quantity = item_info.get("quantity_from_openai", 1)
        current_item_count_for_user = current_user_counts.get(item_idx, 0)

        if current_item_count_for_user < openai_quantity:
            current_user_counts[item_idx] = current_item_count_for_user + 1
            # message_states уже обновлен через current_user_counts -> user_selections_for_message -> state_data_for_message
            
            new_keyboard = create_items_keyboard_with_counters(items, current_user_counts)
            try:
                await message.edit_reply_markup(reply_markup=new_keyboard)
                await callback_query.answer(f"Ваш счетчик для '{item_info.get("description", "N/A")[:20]}...' увеличен до {current_user_counts[item_idx]}")
            except Exception as e:
                logger.error(f"Ошибка при обновлении клавиатуры для message_id {current_message_id}: {e}")
                await callback_query.answer("Не удалось обновить отображение счетчика.")
        else:
            await callback_query.answer(f"Достигнуто максимальное количество ({openai_quantity}) для '{item_info.get("description", "N/A")[:20]}...' для вас.", show_alert=False)

    except Exception as e:
        logger.error(f"Ошибка в handle_item_increment (user_id: {callback_query.from_user.id if callback_query else 'N/A'}): {e}", exc_info=True)
        await callback_query.answer("Произошла ошибка при обработке вашего выбора.")

@dp.callback_query(F.data == "confirm_selection")
async def handle_confirm_selection(callback_query: types.CallbackQuery):
    user = callback_query.from_user
    message = cast(Message, callback_query.message)
    current_message_id = message.message_id

    try:
        if current_message_id not in message_states or "items" not in message_states[current_message_id]:
            await callback_query.answer("Не удалось найти данные для подтверждения. Пожалуйста, отправьте фото чека заново.", show_alert=True)
            return

        state_data_for_message = message_states[current_message_id]
        items = state_data_for_message["items"]
        user_selections_map = state_data_for_message.get("user_selections", {})
        service_charge_percent = state_data_for_message.get("service_charge_percent")
        total_discount_percent = state_data_for_message.get("total_discount_percent")
        total_discount_amount = state_data_for_message.get("total_discount_amount")
        
        logger.info(f"Обработка подтверждения для user {user.id}, message_id {current_message_id}")
        logger.info(f"Данные состояния: items={len(items)}, service_charge={service_charge_percent}, "
                   f"total_discount_percent={total_discount_percent}, total_discount_amount={total_discount_amount}")
        
        current_user_counts = user_selections_map.get(user.id, {})
        logger.info(f"Выбор пользователя: {current_user_counts}")
        
        user_mention = f"@{user.username}" if user.username else f"{user.first_name}"
        summary_text = f"<b>{user_mention}, ваш выбор:</b>\n\n"
        total_sum = Decimal("0.00")
        has_selected_items = False

        # Сначала посчитаем общую сумму всех позиций в чеке
        total_check_sum = Decimal("0.00")
        for item in items:
            if item.get("total_amount_from_openai") is not None:
                total_check_sum += item["total_amount_from_openai"]
        
        logger.info(f"Общая сумма чека: {total_check_sum}")

        for idx, item_data in enumerate(items):
            selected_count = current_user_counts.get(idx, 0)
            if selected_count > 0:
                has_selected_items = True
                description = item_data.get("description", "N/A")
                
                # Определяем, является ли товар весовым
                is_weight_item = False
                openai_quantity = item_data.get("quantity_from_openai", 1)
                total_amount_openai = item_data.get("total_amount_from_openai")
                unit_price_openai = item_data.get("unit_price_from_openai")
                
                if openai_quantity == 1 and total_amount_openai is not None and unit_price_openai is not None:
                    # Проверяем, есть ли расхождение между total_amount и unit_price
                    # с учетом возможного округления (разница не более 0.01)
                    price_diff = abs(total_amount_openai - unit_price_openai)
                    is_weight_item = price_diff > Decimal("0.01")
                
                current_item_total_price = None
                if is_weight_item:
                    # Для весовых товаров берем total_amount напрямую
                    current_item_total_price = total_amount_openai
                else:
                    # Для обычных товаров считаем как обычно
                    if unit_price_openai is not None:
                        current_item_total_price = unit_price_openai * Decimal(selected_count)
                    else:
                        if total_amount_openai is not None and openai_quantity > 0:
                            try:
                                unit_price = total_amount_openai / Decimal(str(openai_quantity))
                                current_item_total_price = unit_price * Decimal(selected_count)
                            except (InvalidOperation, ZeroDivisionError) as e:
                                logger.error(f"Ошибка при расчете цены за единицу для {description}: {e}")
                                current_item_total_price = total_amount_openai
                
                current_item_total_price_str = "(цена неизвестна)"
                if current_item_total_price is not None:
                    try:
                        # Применяем скидку на позицию, если она есть
                        if item_data.get("discount_percent") is not None:
                            discount_amount = (current_item_total_price * item_data["discount_percent"] / Decimal("100")).quantize(Decimal("0.01"))
                            current_item_total_price -= discount_amount
                            current_item_total_price_str = f"{current_item_total_price:.2f} (скидка {item_data['discount_percent']}%)"
                        elif item_data.get("discount_amount") is not None:
                            # Распределяем скидку пропорционально количеству
                            if openai_quantity > 0:
                                item_discount = (item_data["discount_amount"] * Decimal(selected_count) / Decimal(str(openai_quantity))).quantize(Decimal("0.01"))
                                current_item_total_price -= item_discount
                                current_item_total_price_str = f"{current_item_total_price:.2f} (скидка {item_discount:.2f})"
                            else:
                                current_item_total_price_str = f"{current_item_total_price:.2f}"
                        else:
                            current_item_total_price_str = f"{current_item_total_price:.2f}"
                        
                        total_sum += current_item_total_price
                    except (InvalidOperation, ZeroDivisionError) as e:
                        logger.error(f"Ошибка при расчете стоимости для {description}: {e}")
                        current_item_total_price_str = "(ошибка расчета)"
                
                summary_text += f"- {description}: {selected_count} шт. = {current_item_total_price_str}\n"

        if not has_selected_items:
            summary_text = f"{user_mention}, вы ничего не выбрали."
        else:
            summary_text += f"\n<b>Сумма за позиции: {total_sum:.2f}</b>"
            
            # Добавляем информацию о плате за обслуживание, если она есть
            if service_charge_percent is not None:
                try:
                    service_charge_amount = (total_sum * service_charge_percent / Decimal("100")).quantize(Decimal("0.01"))
                    summary_text += f"\n<b>Плата за обслуживание ({service_charge_percent}%): {service_charge_amount:.2f}</b>"
                    total_sum += service_charge_amount
                except (InvalidOperation, ZeroDivisionError) as e:
                    logger.error(f"Ошибка при расчете платы за обслуживание: {e}")
            
            # Добавляем информацию об общей скидке, если она есть
            if total_discount_percent is not None:
                try:
                    discount_amount = (total_sum * total_discount_percent / Decimal("100")).quantize(Decimal("0.01"))
                    summary_text += f"\n<b>Скидка ({total_discount_percent}%): -{discount_amount:.2f}</b>"
                    total_sum -= discount_amount
                except (InvalidOperation, ZeroDivisionError) as e:
                    logger.error(f"Ошибка при расчете процентной скидки: {e}")
            elif total_discount_amount is not None:
                try:
                    # Распределяем общую скидку пропорционально сумме выбранных позиций
                    if total_check_sum > 0:
                        user_discount = (total_discount_amount * total_sum / total_check_sum).quantize(Decimal("0.01"))
                        summary_text += f"\n<b>Скидка: -{user_discount:.2f}</b>"
                        total_sum -= user_discount
                except (InvalidOperation, ZeroDivisionError) as e:
                    logger.error(f"Ошибка при расчете абсолютной скидки: {e}")
            
            summary_text += f"\n<b>Итоговая сумма: {total_sum:.2f}</b>"

        # Отправляем новое сообщение с итогом для пользователя
        try:
            await bot.send_message(
                chat_id=message.chat.id, 
                text=summary_text,
                parse_mode="HTML"
            )
            await callback_query.answer("Ваш выбор подтвержден и отправлен в чат!")
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения с подтверждением для user {user.id} в чат {message.chat.id}: {e}")
            await callback_query.answer("Ошибка при отправке вашего выбора в чат.", show_alert=True)
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обработке подтверждения для user {user.id}: {e}", exc_info=True)
        await callback_query.answer("Произошла ошибка при обработке вашего выбора.", show_alert=True)

@dp.callback_query(F.data == "show_my_summary")
async def handle_show_my_summary(callback_query: types.CallbackQuery):
    user = callback_query.from_user
    message = cast(Message, callback_query.message)
    current_message_id = message.message_id

    if current_message_id not in message_states or "items" not in message_states[current_message_id]:
        await callback_query.answer("Не удалось найти данные для отображения. Пожалуйста, отправьте фото чека заново.", show_alert=True)
        return

    state_data_for_message = message_states[current_message_id]
    items = state_data_for_message["items"]
    user_selections_map = state_data_for_message.get("user_selections", {})
    current_user_counts = user_selections_map.get(user.id, {})

    user_mention = f"@{user.username}" if user.username else f"{user.first_name}"
    summary_text_content = f"**{user_mention}, ваш текущий выбор:**\\n\\n"

    # Генерируем клавиатуру с персональными счетчиками пользователя
    keyboard_my_summary = create_items_keyboard_with_counters(items, current_user_counts, view_mode="my_summary_display")

    try:
        await message.edit_text(text=summary_text_content, reply_markup=keyboard_my_summary)
        await callback_query.answer("Отображен ваш текущий выбор.")
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения для показа текущего выбора user {user.id} в чате {message.chat.id}: {e}")
        await callback_query.answer("Ошибка при отображении вашего текущего выбора.", show_alert=True)

@dp.callback_query(F.data == "show_total_summary")
async def handle_show_total_summary(callback_query: types.CallbackQuery):
    user = callback_query.from_user # Нужен для логгирования и возможного будущего использования
    message = cast(Message, callback_query.message)
    current_message_id = message.message_id

    if current_message_id not in message_states or "items" not in message_states[current_message_id]:
        await callback_query.answer("Не удалось найти данные для отображения. Пожалуйста, отправьте фото чека заново.", show_alert=True)
        return

    state_data_for_message = message_states[current_message_id]
    items = state_data_for_message["items"]
    user_selections_map = state_data_for_message.get("user_selections", {})

    summary_text_content = "**Общий итог по чеку (выбрано всеми / количество в чеке):**\\n\\n"
    # Рассчитываем агрегированные счетчики
    aggregated_counts = {idx: 0 for idx in range(len(items))}
    for _user_id, user_counts in user_selections_map.items():
        for item_idx, count in user_counts.items():
            if 0 <= item_idx < len(items):
                 aggregated_counts[item_idx] = aggregated_counts.get(item_idx,0) + count
    
    # Добавляем детализацию по позициям в текстовое сообщение, если нужно, или можно оставить только заголовок
    # Например, можно добавить общую сумму под клавиатурой или в тексте.
    # grand_total_sum_all_users = Decimal("0.00") 
    # (логика подсчета общей суммы, если она нужна в тексте над этой клавиатурой)

    # Генерируем клавиатуру в режиме отображения общего итога
    keyboard_total_summary = create_items_keyboard_with_counters(items, aggregated_counts, view_mode="total_summary_display")

    try:
        await message.edit_text(text=summary_text_content, reply_markup=keyboard_total_summary)
        await callback_query.answer("Отображен общий итог по чеку.")
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения для показа общего итога в чате {message.chat.id} (user: {user.id}): {e}")
        await callback_query.answer("Ошибка при отображении общего итога.", show_alert=True)

@dp.callback_query(F.data == "back_to_selection")
async def handle_back_to_selection(callback_query: types.CallbackQuery):
    user = callback_query.from_user
    message = cast(Message, callback_query.message)
    current_message_id = message.message_id

    if current_message_id not in message_states or "items" not in message_states[current_message_id]:
        await callback_query.answer("Не удалось найти данные для возврата к выбору. Пожалуйста, отправьте фото чека заново.", show_alert=True)
        # Потенциально можно отредактировать сообщение, сказав, что оно устарело, и убрать клавиатуру
        # await message.edit_text("Данные по этому чеку устарели.", reply_markup=None)
        return

    state_data_for_message = message_states[current_message_id]
    items = state_data_for_message["items"]
    user_selections_map = state_data_for_message.get("user_selections", {})
    current_user_counts = user_selections_map.get(user.id, {}) # Получаем выбор конкретного пользователя для восстановления клавиатуры

    # Восстанавливаем исходный текст и клавиатуру выбора
    original_prompt_text = "Распознанные позиции. Выберите количество или подтвердите:\\n"
    selection_keyboard = create_items_keyboard_with_counters(items, current_user_counts)

    try:
        await message.edit_text(text=original_prompt_text, reply_markup=selection_keyboard)
        await callback_query.answer("Возврат к выбору позиций.")
    except Exception as e:
        logger.error(f"Ошибка при возврате к выбору позиций для message_id {current_message_id}: {e}")
        await callback_query.answer("Ошибка при возврате к выбору.", show_alert=True)

async def main():
    # logging.basicConfig(level=logging.DEBUG) # Можно установить DEBUG для более детальных логов
    logger.info("Бот запускается с OpenAI GPT Vision и подтверждением выбора...")
    
    # Регистрация роутеров из handlers
    dp.include_router(commands.router)
    dp.include_router(photo.router)
    dp.include_router(callbacks.router)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 