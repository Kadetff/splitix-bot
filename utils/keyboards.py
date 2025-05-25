from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
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
    
    # Убраны кнопки веб-интерфейса - используем только тестовое приложение
    if chat_type != "private":
        # Для группового чата - только кнопка промежуточного итога
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

def create_test_webapp_inline_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    """
    Создает Inline-клавиатуру с кнопкой WebApp для тестирования.
    
    Args:
        webapp_url: URL веб-приложения
        
    Returns:
        InlineKeyboardMarkup с кнопкой WebApp
    """
    builder = InlineKeyboardBuilder()
    
    try:
        webapp_button = InlineKeyboardButton(
            text="🧪 Открыть тестовый WebApp (Inline)",
            web_app=WebAppInfo(url=webapp_url)
        )
        builder.row(webapp_button)
        
        # Дополнительная кнопка для информации
        builder.row(InlineKeyboardButton(
            text="ℹ️ О WebApp",
            callback_data="webapp_info"
        ))
        
    except Exception as e:
        logger.error(f"Ошибка при создании Inline WebApp кнопки: {e}", exc_info=True)
        # Fallback кнопка при ошибке
        builder.row(InlineKeyboardButton(
            text="❌ Ошибка создания WebApp",
            callback_data="webapp_error"
        ))
    
    return builder.as_markup()

def create_test_webapp_reply_keyboard(webapp_url: str) -> ReplyKeyboardMarkup:
    """
    Создает Reply-клавиатуру с кнопкой WebApp для тестирования.
    
    Args:
        webapp_url: URL веб-приложения
        
    Returns:
        ReplyKeyboardMarkup с кнопкой WebApp
    """
    builder = ReplyKeyboardBuilder()
    
    try:
        webapp_button = KeyboardButton(
            text="🧪 Открыть тестовый WebApp (Reply)",
            web_app=WebAppInfo(url=webapp_url)
        )
        builder.row(webapp_button)
        
        # Кнопка для убирания клавиатуры
        builder.row(KeyboardButton(text="🔙 Убрать клавиатуру"))
        
    except Exception as e:
        logger.error(f"Ошибка при создании Reply WebApp кнопки: {e}", exc_info=True)
        # Fallback кнопка при ошибке
        builder.row(KeyboardButton(text="❌ Ошибка создания WebApp"))
        builder.row(KeyboardButton(text="🔙 Убрать клавиатуру"))
    
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False) 