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

from openai import AsyncOpenAI # Асинхронный клиент OpenAI

# Загружаем переменные окружения из .env файла
load_dotenv()

# Включим логирование, чтобы видеть ошибки
logging.basicConfig(level=logging.INFO)
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
dp = Dispatcher()

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

def create_openai_prompt(base64_image_data: str) -> list:
    """Создает промпт для OpenAI Vision API."""
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Проанализируй это изображение чека. Извлеки все товарные позиции. "
                        "Для каждой позиции предоставь описание (description), количество в чеке (quantity, если есть, иначе 1), "
                        "цену за единицу (unit_price, если есть) и общую сумму по позиции в чеке (total_amount)."
                        "Все числовые значения (quantity, unit_price, total_amount) должны быть числами (int или float), а не строками, если это возможно. Запятые в числах должны быть заменены на точки." 
                        "Верни результат в виде JSON-объекта со списком items. "
                        "Каждый элемент списка должен быть объектом со следующими ключами: "
                        "'description' (строка), 'quantity' (число), 'unit_price' (число, опционально), 'total_amount' (число)."
                        "Если не можешь определить какое-то числовое значение, используй null или пропусти ключ. "
                        "Пример JSON: {\"items\": [{\"description\": \"Хлеб Бородинский\", \"quantity\": 1, \"total_amount\": 50.99}, {\"description\": \"Молоко 3.2%\", \"quantity\": 1, \"unit_price\": 75.00, \"total_amount\": 75.00}]}. "
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

def extract_items_from_openai_response(parsed_json_data: dict) -> list[dict] | None:
    if not parsed_json_data or "items" not in parsed_json_data or not isinstance(parsed_json_data["items"], list):
        logger.warning(f"Неожиданный формат JSON от OpenAI или нет ключа 'items': {parsed_json_data}")
        return None
    processed_items = []
    for item_data in parsed_json_data["items"]:
        if isinstance(item_data, dict):
            # OpenAI может вернуть unit_price или total_amount как строки, пытаемся их привести к Decimal
            unit_price_dec = parse_possible_price(item_data.get("unit_price"))
            total_amount_dec = parse_possible_price(item_data.get("total_amount"))
            
            # Пытаемся получить quantity как число
            openai_quantity = 1 # По умолчанию
            raw_quantity = item_data.get("quantity", 1)
            if isinstance(raw_quantity, (int, float)):
                openai_quantity = int(raw_quantity)
            elif isinstance(raw_quantity, str):
                try:
                    openai_quantity_val_str = raw_quantity.lower().replace("шт", "").replace("szt", "").strip()
                    cleaned_quantity_str = "".join(filter(lambda x: x.isdigit() or x == '.', openai_quantity_val_str.split()[0]))
                    if cleaned_quantity_str:
                        parsed_q = float(cleaned_quantity_str) if '.' in cleaned_quantity_str else int(cleaned_quantity_str)
                        openai_quantity = int(parsed_q) if parsed_q > 0 else 1
                except ValueError:
                    pass # openai_quantity останется 1
            
            processed_items.append({
                "description": str(item_data.get("description", "N/A")), # Убедимся, что описание - строка
                "quantity_from_openai": openai_quantity, 
                "unit_price_from_openai": unit_price_dec, # Decimal | None
                "total_amount_from_openai": total_amount_dec # Decimal | None
            })
        else:
            logger.warning(f"Найден элемент не-словарь в items: {item_data}")
    return processed_items

def create_items_keyboard_with_counters(items: list[dict], user_specific_counts: dict[int, int], view_mode: str = "default") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, item in enumerate(items):
        description = item.get("description", "N/A")
        # В режиме total_summary_display, user_specific_counts будут агрегированными счетчиками
        current_selection_count = user_specific_counts.get(idx, 0) 
        openai_quantity = item.get("quantity_from_openai", 1) # Это всегда общее количество из чека
        
        # Логика отображения цены за единицу
        unit_price_display = None
        unit_price_openai = item.get("unit_price_from_openai")
        total_amount_openai = item.get("total_amount_from_openai")
        
        if unit_price_openai is not None:
            unit_price_display = unit_price_openai
        elif total_amount_openai is not None and openai_quantity > 0:
            try:
                unit_price_display = total_amount_openai / Decimal(str(openai_quantity))
            except (InvalidOperation, ZeroDivisionError): # Добавим ZeroDivisionError на всякий случай
                pass # unit_price_display останется None
            
        price_str = f" - {unit_price_display:.2f}" if unit_price_display is not None else ""
        
        # Иконка галочки, если количество выбрано полностью
        checkmark_icon = "✅ " if current_selection_count == openai_quantity and openai_quantity > 0 else ""
        
        button_text = f"{checkmark_icon}[{current_selection_count}/{openai_quantity}] {description[:30]}{price_str}"
        # В режиме отображения общего итога кнопки товаров не должны быть интерактивными для инкремента,
        # но для простоты оставим callback_data, хотя он не будет иметь эффекта в этом контексте,
        # или можно сделать их без callback_data вообще, если не хотим случайных нажатий.
        # Пока оставим как есть, т.к. основная цель - отображение.
        builder.row(InlineKeyboardButton(text=button_text, callback_data=f"increment_item:{idx}")) 
    
    if view_mode == "default":
        builder.row(InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="confirm_selection"))
        builder.row(InlineKeyboardButton(text="📊 Мой текущий выбор", callback_data="show_my_summary"))
        builder.row(InlineKeyboardButton(text="📈 Общий итог по чеку", callback_data="show_total_summary"))
    elif view_mode == "total_summary_display":
        builder.row(InlineKeyboardButton(text="⬅️ Назад к моему выбору", callback_data="back_to_selection"))
        # Можно добавить и другие кнопки, если нужно, например, "Подтвердить общий выбор" (если такая логика появится)

    return builder.as_markup()

@dp.message(CommandStart())
async def send_welcome(message: Message):
    """Отправляет приветственное сообщение при команде /start."""
    await message.reply(
        "Привет! Отправь мне фотографию чека, и я попробую распознать его с помощью OpenAI."
    )

@dp.message(F.photo)
async def handle_photo(message: Message):
    user = message.from_user
    photo: PhotoSize = message.photo[-1]
    processing_msg = None # Инициализируем processing_msg

    try:
        # Отправляем начальное сообщение "Фото получил..."
        processing_msg = await message.reply("Фото получил! Отправляю в OpenAI для анализа...")

        if not openai_client: # Проверка клиента OpenAI должна быть после попытки отправить сообщение
            logger.error("Клиент OpenAI не инициализирован!")
            if processing_msg: # Если удалось отправить начальное сообщение, редактируем его
                await processing_msg.edit_text("Ошибка: Клиент OpenAI не настроен. Обратитесь к администратору.")
            else: # Если даже начальное сообщение не отправилось
                await message.answer("Ошибка: Клиент OpenAI не настроен. Обратитесь к администратору.")
            return
        
        photo_bytes_io = io.BytesIO()
        await bot.download(file=photo.file_id, destination=photo_bytes_io)
        photo_bytes = photo_bytes_io.getvalue()
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')

        prompt_messages = create_openai_prompt(base64_image)
        
        logger.info("Отправка запроса в OpenAI Vision API...")
        completion = await openai_client.chat.completions.create(
            model="gpt-4.1-mini", # Убедитесь, что это правильное имя модели
            messages=prompt_messages, # type: ignore
            max_completion_tokens=1500 
        )

        ai_response_choice = completion.choices[0]
        ai_response_content = ai_response_choice.message.content
        finish_reason = ai_response_choice.finish_reason

        logger.info(f"Получен ответ от OpenAI. Content: '{ai_response_content}', Finish Reason: '{finish_reason}'")

        if not ai_response_content:
            await processing_msg.edit_text(f"OpenAI вернул пустой ответ. Причина завершения: {finish_reason}")
            return

        parsed_json = None
        try:
            if ai_response_content.strip().startswith("```json"):
                json_str = ai_response_content.strip()[7:-3].strip()
            elif ai_response_content.strip().startswith("{"):
                json_str = ai_response_content.strip()
            else:
                raise ValueError("Ответ OpenAI не является ожидаемым JSON.")
            parsed_json = json.loads(json_str)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Ошибка обработки ответа OpenAI: {e}. Ответ: {ai_response_content}")
            await processing_msg.edit_text(f"Ошибка обработки ответа от AI. Ответ AI:\n{ai_response_content[:1000]}")
            return

        items = extract_items_from_openai_response(parsed_json)

        if items:
            initial_user_counts = {} # Для первого отображения клавиатуры, ни у кого нет выбранных элементов
            keyboard = create_items_keyboard_with_counters(items, initial_user_counts)
            response_msg_text = "Распознанные позиции. Выберите количество или подтвердите:\n"
            
            sent_message_with_keyboard = await processing_msg.edit_text(response_msg_text, reply_markup=keyboard)
            
            # Сохраняем items и пустой словарь для user_selections
            message_states[sent_message_with_keyboard.message_id] = {
                "items": items, 
                "user_selections": {} # user_id -> {item_idx: count}
            }
            logger.info(f"Состояние для message_id {sent_message_with_keyboard.message_id} сохранено: {len(items)} позиций. Ожидание выбора пользователей.")
        else:
            await processing_msg.edit_text("AI не смог извлечь товарные позиции из чека в ожидаемом формате.")

    except Exception as e:
        logger.error(f"Ошибка при обработке фото через OpenAI: {e}", exc_info=True)
        error_message_text = f"Произошла очень серьезная ошибка при обработке фото: {str(e)[:1000]}"
        if processing_msg: # Теперь processing_msg будет определена (может быть None)
            try:
                await processing_msg.edit_text(error_message_text)
            except Exception as e2: # Если редактирование не удалось (например, сообщение удалено)
                logger.error(f"Не удалось отредактировать сообщение об ошибке: {e2}")
                await message.answer(error_message_text) # Отправляем новое сообщение
        else: # Если processing_msg так и не было создано (ошибка до его присвоения)
            await message.answer(error_message_text)

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

    if current_message_id not in message_states or "items" not in message_states[current_message_id]:
        await callback_query.answer("Не удалось найти данные для подтверждения. Пожалуйста, отправьте фото чека заново.", show_alert=True)
        # Не редактируем исходное сообщение, если оно все еще может быть использовано другими
        # await message.edit_text("Данные для этого выбора устарели.", reply_markup=None) 
        return

    state_data_for_message = message_states[current_message_id]
    items = state_data_for_message["items"]
    user_selections_map = state_data_for_message.get("user_selections", {})
    
    current_user_counts = user_selections_map.get(user.id, {}) # Получаем выбор конкретного пользователя
    
    user_mention = f"@{user.username}" if user.username else f"{user.first_name}"
    summary_text = f"<b>{user_mention}, ваш выбор:</b>\n\n"
    total_sum = Decimal("0.00")
    has_selected_items = False

    for idx, item_data in enumerate(items):
        selected_count = current_user_counts.get(idx, 0)
        if selected_count > 0:
            has_selected_items = True
            description = item_data.get("description", "N/A")
            
            item_price_for_one = None
            unit_price_openai = item_data.get("unit_price_from_openai")
            if unit_price_openai is not None:
                item_price_for_one = unit_price_openai
            else:
                total_amount_openai = item_data.get("total_amount_from_openai")
                quantity_openai = item_data.get("quantity_from_openai", 1)
                if total_amount_openai is not None and quantity_openai > 0:
                    item_price_for_one = total_amount_openai / Decimal(str(quantity_openai))
            
            current_item_total_price_str = "(цена неизвестна)"
            if item_price_for_one is not None:
                current_item_total_price = item_price_for_one * Decimal(selected_count)
                total_sum += current_item_total_price
                current_item_total_price_str = f"{current_item_total_price:.2f}"
            
            summary_text += f"- {description}: {selected_count} шт. = {current_item_total_price_str}\n"

    if not has_selected_items:
        summary_text = f"{user_mention}, вы ничего не выбрали."
    else:
        summary_text += f"\n<b>Итоговая сумма: {total_sum:.2f}</b>"

    # Отправляем новое сообщение с итогом для пользователя
    try:
        await bot.send_message(
            chat_id=message.chat.id, 
            text=summary_text,
            parse_mode="HTML",
            # reply_to_message_id=message.message_id # Можно раскомментировать, чтобы ответ был привязан к сообщению с чеком
        )
        await callback_query.answer("Ваш выбор подтвержден и отправлен в чат!")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения с подтверждением для user {user.id} в чат {message.chat.id}: {e}")
        await callback_query.answer("Ошибка при отправке вашего выбора в чат.", show_alert=True)

    # Не удаляем состояние общего сообщения и не удаляем клавиатуру с исходного сообщения,
    # чтобы другие пользователи могли продолжить.
    # Также не очищаем выбор конкретного пользователя из message_states, 
    # чтобы он мог "переподтвердить" с другими значениями, если захочет.
    # logger.info(f"Пользователь {user.id} подтвердил выбор для message_id {current_message_id}.")

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
    total_sum = Decimal("0.00")
    has_selected_items = False

    for idx, item_data in enumerate(items):
        selected_count = current_user_counts.get(idx, 0)
        if selected_count > 0:
            has_selected_items = True
            description = item_data.get("description", "N/A")
            item_price_for_one = None
            unit_price_openai = item_data.get("unit_price_from_openai")
            if unit_price_openai is not None:
                item_price_for_one = unit_price_openai
            else:
                total_amount_openai = item_data.get("total_amount_from_openai")
                quantity_openai = item_data.get("quantity_from_openai", 1)
                if total_amount_openai is not None and quantity_openai > 0:
                    item_price_for_one = total_amount_openai / Decimal(str(quantity_openai))
            
            current_item_total_price_str = "(цена неизвестна)"
            if item_price_for_one is not None:
                current_item_total_price = item_price_for_one * Decimal(selected_count)
                total_sum += current_item_total_price
                current_item_total_price_str = f"{current_item_total_price:.2f}"
            
            summary_text_content += f"- {description}: {selected_count} шт. = {current_item_total_price_str}\\n"

    if not has_selected_items:
        summary_text_content = f"{user_mention}, вы пока ничего не выбрали."
    else:
        summary_text_content += f"\\n**Итоговая сумма вашего текущего выбора: {total_sum:.2f}**"

    back_keyboard_builder = InlineKeyboardBuilder()
    back_keyboard_builder.row(InlineKeyboardButton(text="⬅️ Назад к выбору", callback_data="back_to_selection"))

    try:
        await message.edit_text(text=summary_text_content, reply_markup=back_keyboard_builder.as_markup())
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

async def main() -> None:
    # logging.basicConfig(level=logging.DEBUG) # Можно установить DEBUG для более детальных логов
    logger.info("Бот запускается с OpenAI GPT Vision и подтверждением выбора...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 