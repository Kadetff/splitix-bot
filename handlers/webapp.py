import json
import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from utils.state import message_state
from utils.calculations import calculate_total_with_charges
from utils.formatters import format_user_summary

logger = logging.getLogger(__name__)
# Устанавливаем уровень логирования для этого модуля на DEBUG
logger.setLevel(logging.DEBUG)
router = Router()

# Будет установлено из main.py
message_states = {}

# Добавляем обработчик для всех сообщений
@router.message()
async def handle_all_messages(message: Message, state: FSMContext):
    """Обработчик для всех сообщений, чтобы отловить данные от WebApp"""
    logger.debug(f"Получено сообщение: {message}")
    
    # Проверяем наличие web_app_data
    if hasattr(message, 'web_app_data') and message.web_app_data:
        logger.info(f"Обнаружены данные WebApp: {message.web_app_data.data}")
        await handle_webapp_data(message, state)
        return
    
    # Проверяем все атрибуты сообщения
    attrs = dir(message)
    logger.debug(f"Атрибуты сообщения: {', '.join([a for a in attrs if not a.startswith('_')])}")
    
    # Расширенное логирование важных атрибутов
    logger.debug(f"Text: {getattr(message, 'text', 'None')}")
    logger.debug(f"ContentType: {getattr(message, 'content_type', 'None')}")
    logger.debug(f"WebAppData: {getattr(message, 'web_app_data', 'None')}")
    
    # Проверяем, есть ли в сообщении JSON-данные
    if hasattr(message, 'text') and message.text:
        try:
            data = json.loads(message.text)
            if isinstance(data, dict) and 'messageId' in data and 'selectedItems' in data:
                logger.info(f"Найдены данные WebApp в тексте сообщения: {message.text}")
                # Создаем временные данные для обработки
                class WebAppData:
                    def __init__(self, data):
                        self.data = json.dumps(data)
                message.web_app_data = WebAppData(data)
                await handle_webapp_data(message, state)
                return
        except json.JSONDecodeError:
            pass
    
    # Если это регулярное сообщение без обработки, просто логируем
    logger.debug("Сообщение не опознано как данные WebApp, пропускаем")

@router.message(F.web_app_data)
async def handle_webapp_data(message: Message, state: FSMContext):
    logger.info('=== Вызван handle_webapp_data ===')
    try:
        logger.info(f"Получены данные от WebApp: {getattr(message.web_app_data, 'data', None)} | message: {message}")
        # Парсим JSON данные
        try:
            data = json.loads(message.web_app_data.data)
            logger.info(f"[handle_webapp_data] Распарсенные данные: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"[handle_webapp_data] Ошибка при парсинге JSON: {e}")
            await message.answer("❌ Ошибка при обработке данных. Пожалуйста, попробуйте еще раз.")
            return
        message_id = data.get('message_id')
        selected_items = data.get('selected_items', [])
        logger.info(f"[handle_webapp_data] message_id: {message_id}, selected_items: {selected_items}")
        if not message_id or not selected_items:
            logger.error(f"[handle_webapp_data] Отсутствуют обязательные поля: message_id={message_id}, selected_items={selected_items}")
            await message.answer("❌ Ошибка: отсутствуют необходимые данные. Пожалуйста, попробуйте еще раз.")
            return
        state_data = await state.get_data()
        logger.info(f"[handle_webapp_data] state_data: {state_data}")
        if not state_data:
            logger.error("[handle_webapp_data] Состояние не найдено")
            await message.answer("❌ Ошибка: сессия истекла. Пожалуйста, начните заново.")
            return
        state_data['selected_items'] = selected_items
        total = sum(item['price'] for item in selected_items)
        state_data['total'] = total
        await state.update_data(**state_data)
        try:
            await message.answer("messageSent")
            logger.info("[handle_webapp_data] Отправлено подтверждение в WebApp")
        except Exception as e:
            logger.error(f"[handle_webapp_data] Ошибка при отправке подтверждения в WebApp: {e}")
        items_text = "\n".join([f"• {item['name']} - {item['price']}₽" for item in selected_items])
        await message.answer(
            f"✅ Ваш выбор сохранен!\n\n"
            f"Выбранные позиции:\n{items_text}\n\n"
            f"Итого: {total}₽",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Посмотреть результаты всех участников", callback_data="show_results")]
            ])
        )
        logger.info(f"[handle_webapp_data] Данные успешно обработаны для пользователя {message.from_user.id}")
    except Exception as e:
        logger.error(f"[handle_webapp_data] Ошибка при обработке данных: {e}")
        await message.answer("❌ Произошла ошибка при обработке данных. Пожалуйста, попробуйте еще раз.") 