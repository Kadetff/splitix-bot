from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config.settings import WEBAPP_URL, BOT_USERNAME
import logging

logger = logging.getLogger(__name__)

def create_receipt_keyboard(message_id: int, chat_type: str = "private") -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для сообщения с чеком.
    
    Args:
        message_id: ID сообщения с чеком
        chat_type: Тип чата ("private" или "group")
    
    Returns:
        InlineKeyboardMarkup с кнопками:
        - Для личного чата: Mini App, Инструкция
        - Для группового чата: Открыть Mini App (в ЛС), Промежуточный итог, Инструкция
    """
    builder = InlineKeyboardBuilder()
    
    # Очищаем URL от кавычек, если они есть
    clean_url = WEBAPP_URL.strip('"\'')
    webapp_url = f"{clean_url}/{message_id}"
    
    if chat_type == "private":
        # Для личного чата
        try:
            webapp_button = InlineKeyboardButton(
                text="🌐 Открыть в веб-интерфейсе",
                web_app=WebAppInfo(url=webapp_url)
            )
            builder.row(webapp_button)
        except Exception as e:
            logger.error(f"Ошибка при создании кнопки WebApp: {e}", exc_info=True)
    else:
        # Для группового чата
        # Кнопка для перехода в личный чат с ботом
        builder.row(InlineKeyboardButton(
            text="🌐 Открыть мини-приложение (в личном чате)",
            url=f"https://t.me/{BOT_USERNAME}?start=webapp_{message_id}"
        ))
        
        # Кнопка промежуточного итога
        builder.row(InlineKeyboardButton(
            text="📊 Промежуточный итог",
            callback_data=f"show_intermediate_summary:{message_id}"
        ))
    
    # Кнопка с инструкцией (общая для обоих режимов)
    builder.row(InlineKeyboardButton(
        text="ℹ️ Инструкция",
        callback_data="show_instructions"
    ))
    
    return builder.as_markup() 