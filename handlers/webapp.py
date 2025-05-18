import json
import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton
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
    """Обработчик данных, полученных от веб-приложения"""
    try:
        logger.debug(f"Начало обработки данных WebApp. Сообщение: {message}")
        
        # Получаем данные
        webapp_data = None
        if hasattr(message, 'web_app_data') and message.web_app_data:
            webapp_data = message.web_app_data.data
            logger.debug(f"Получены данные из web_app_data: {webapp_data}")
        elif hasattr(message, 'text') and message.text:
            try:
                data = json.loads(message.text)
                if isinstance(data, dict) and 'messageId' in data and 'selectedItems' in data:
                    webapp_data = message.text
                    logger.debug(f"Получены данные из text: {webapp_data}")
            except json.JSONDecodeError:
                pass
        
        if not webapp_data:
            logger.error("Не удалось получить данные из сообщения")
            await message.answer("❌ Не удалось получить данные из мини-приложения. Пожалуйста, попробуйте снова.")
            return
        
        # Парсим JSON-данные
        try:
            data = json.loads(webapp_data)
            logger.debug(f"Распарсенные данные: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка при парсинге JSON: {e}")
            await message.answer("❌ Ошибка при обработке данных. Пожалуйста, попробуйте снова.")
            return
            
        message_id = data.get('messageId')
        selected_items = data.get('selectedItems', {})
        
        if not message_id:
            logger.error("Отсутствует messageId в данных")
            await message.answer("❌ Не удалось обработать выбор: отсутствует идентификатор сообщения.")
            return
        
        logger.debug(f"Обработка данных для message_id: {message_id}, selected_items: {selected_items}")
        
        # Получаем состояние
        state_data = message_state.get_state(int(message_id))
        if not state_data:
            logger.error(f"Не найдено состояние для message_id: {message_id}")
            await message.answer("❌ Не удалось обработать выбор из веб-приложения. Попробуйте еще раз.")
            return
        
        user_id = message.from_user.id
        logger.debug(f"Обработка выбора для user_id: {user_id}")
        
        # Обновляем выбор пользователя
        if 'user_selections' not in state_data:
            state_data['user_selections'] = {}
        # Преобразуем ключи и значения к строкам и int
        state_data['user_selections'][user_id] = {str(idx): int(count) for idx, count in selected_items.items()}
        
        # Расчёт и форматирование итогов
        user_counts = state_data['user_selections'][user_id]
        total_sum, summary = calculate_total_with_charges(
            items=state_data.get("items", []),
            user_counts=user_counts,
            service_charge_percent=state_data.get("service_charge_percent"),
            actual_discount_percent=state_data.get("actual_discount_percent"),
            total_discount_amount=state_data.get("total_discount_amount")
        )
        username = message.from_user.username or message.from_user.first_name
        formatted_summary = format_user_summary(username, state_data["items"], user_counts, total_sum, summary)
        
        # Сохраняем результат
        if "user_results" not in state_data:
            state_data["user_results"] = {}
        state_data["user_results"][user_id] = {
            "summary": formatted_summary,
            "total_sum": float(total_sum),
            "selected_items": {str(idx): count for idx, count in user_counts.items() if count > 0}
        }
        
        logger.debug(f"Отправка итогового сообщения для user_id: {user_id}")
        
        # Отправляем итоговое сообщение в чат
        await message.answer(formatted_summary, parse_mode="HTML")
        
        # Кнопка для просмотра всех результатов
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="👥 Посмотреть итоги всех участников", callback_data="show_all_results"))
        await message.answer(
            "✅ Ваш выбор подтвержден и сохранен! Теперь каждый участник может сделать свой выбор независимо.",
            reply_markup=keyboard.as_markup()
        )
        
        logger.debug(f"Успешно обработаны данные WebApp для user_id: {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке данных из веб-приложения: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обработке данных из веб-приложения.") 