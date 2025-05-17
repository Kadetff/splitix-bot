from decimal import Decimal
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config.settings import WEBAPP_URL
import logging

logger = logging.getLogger(__name__)

def create_items_keyboard_with_counters(items: list[dict], user_specific_counts: dict[int, int], view_mode: str = "default", message_id: int = None, chat_type: str = None) -> InlineKeyboardMarkup:
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
        
        # Добавляем кнопку для запуска веб-приложения только если это личный чат
        # и только если у нас есть message_id и валидный WEBAPP_URL
        is_private_chat = chat_type == "private"
        if is_private_chat and message_id is not None and WEBAPP_URL and not ("http://localhost" in WEBAPP_URL or "http://127.0.0.1" in WEBAPP_URL):
            # Очищаем URL от кавычек, если они есть
            clean_url = WEBAPP_URL.strip('"\'')
            
            # Дополнительная проверка, что message_id валидный
            if isinstance(message_id, int) and message_id > 0:
                # Используем параметр в URL вместо query параметра
                webapp_url = f"{clean_url}/{message_id}"
                
                # Логируем информацию о создании кнопки
                logger.info(f"Создаем кнопку WebApp с URL: {webapp_url}, тип чата: {chat_type}")
                
                try:
                    # Создаем WebApp кнопку
                    webapp_button = InlineKeyboardButton(
                        text="🌐 Открыть в веб-интерфейсе", 
                        web_app=WebAppInfo(url=webapp_url)
                    )
                    
                    # Добавляем кнопку в клавиатуру
                    builder.row(webapp_button)
                    logger.info(f"WebApp кнопка успешно создана для личного чата")
                except Exception as e:
                    logger.error(f"Ошибка при создании кнопки WebApp: {e}", exc_info=True)
            else:
                logger.warning(f"Невалидный message_id: {message_id}, тип: {type(message_id)}. WebApp кнопка не будет добавлена.")
        
        # Для групповых чатов добавляем специальную кнопку с инструкцией
        elif not is_private_chat and message_id is not None and WEBAPP_URL:
            # Получаем bot_username из конфигурации
            bot_username = "Splitix_bot"  # Fallback значение, если не сможем получить динамически
            
            # Добавляем кнопку для перехода в личный чат с ботом
            builder.row(InlineKeyboardButton(
                text="🌐 Открыть мини-приложение (в личном чате)", 
                url=f"https://t.me/{bot_username}?start=webapp_{message_id}"
            ))
            
            # Добавляем кнопку с инструкцией по использованию inline режима
            builder.row(InlineKeyboardButton(
                text="ℹ️ Как использовать в групповом чате", 
                callback_data="show_inline_help"
            ))
        
        builder.row(InlineKeyboardButton(text="📊 Мой текущий выбор", callback_data="show_my_summary"))
        builder.row(InlineKeyboardButton(text="📈 Общий итог по чеку", callback_data="show_total_summary"))
    elif view_mode == "total_summary_display":
        builder.row(InlineKeyboardButton(text="⬅️ Назад к моему выбору", callback_data="back_to_selection"))
    elif view_mode == "my_summary_display":
        builder.row(InlineKeyboardButton(text="⬅️ Назад к выбору", callback_data="back_to_selection"))

    return builder.as_markup() 