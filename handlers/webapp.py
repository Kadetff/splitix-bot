import json
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, InlineQueryResultArticle, InputTextMessageContent
import html

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
logger.propagate = False

router = Router()

def escape_markdown(text):
    """Экранирует специальные символы для Markdown"""
    if not isinstance(text, str):
        text = str(text)
    
    # Экранируем только критически важные символы Markdown
    # Убираем апострофы, точки и другие символы, которые не ломают разметку
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

@router.message(F.web_app_data)
async def handle_webapp_data_specific_filter(message: Message):
    """
    Обработчик данных от WebApp.
    Создает одинаковые сообщения для обеих типов кнопок (Inline и Reply).
    """
    logger.info("Получены данные от WebApp")
    
    if message.web_app_data and message.web_app_data.data:
        raw_data = message.web_app_data.data
        logger.info(f"WebApp данные: {raw_data}")
        
        # Простая проверка: если данные = "Привет", это наш простой тест
        if raw_data.strip() == "Привет":
            logger.info(f"Получено простое сообщение: {raw_data}")
            
            # УНИФИЦИРОВАННЫЙ ОТВЕТ (одинаковый для всех типов кнопок)
            response = f"🎉 **УСПЕХ! Бот получил сообщение от WebApp!**\n\n"
            response += f"💬 **Сообщение**: `{raw_data}`\n"
            response += f"⏰ **Время**: {message.date.strftime('%H:%M:%S')}"
            
            await message.answer(response, parse_mode="Markdown")
            return
        
        # Пытаемся парсить как JSON для сложных данных
        try:
            data = json.loads(raw_data)
            logger.info(f"Parsed web_app_data: {data}")

            # Извлекаем информацию о типе кнопки из данных
            button_type = data.get('button_type', 'unknown')
            query_id = data.get('query_id')
            payload = data.get('payload')
            source = data.get('source', 'unknown')
            
            logger.info(f"Parsed: button_type={button_type}, source={source}, payload={payload}")

            # УНИФИЦИРОВАННЫЙ ОТВЕТ (одинаковый внешний вид для всех типов)
            response = f"✅ **Данные от WebApp получены!**\n\n"
            
            # Показываем тип кнопки только в техническом блоке
            if button_type == 'inline':
                response += f"🔵 **Тип кнопки**: Inline\n"
            elif button_type == 'reply':
                response += f"🟢 **Тип кнопки**: Reply\n"
            else:
                response += f"⚪ **Тип кнопки**: {escape_markdown(button_type)}\n"
            
            # Показываем содержимое данных с правильным экранированием
            if isinstance(payload, str):
                response += f"💬 **Сообщение**: `{payload}`\n"
            elif isinstance(payload, dict):
                if 'message' in payload:
                    response += f"💬 **Сообщение**: `{payload['message']}`\n"
                if 'items' in payload:
                    # Массивы БЕЗ блоков кода - только иконка и обычный текст
                    items_str = str(payload['items'])
                    response += f"📦 **Элементы**: {items_str}\n"
                if 'count' in payload:
                    response += f"🔢 **Количество**: `{payload['count']}`\n"
            
            response += f"⏰ **Время**: {message.date.strftime('%H:%M:%S')}\n"
            response += f"🔧 **Источник**: {escape_markdown(source)}"

            await message.answer(response, parse_mode="Markdown")
                
        except json.JSONDecodeError:
            logger.error(f"JSONDecodeError parsing web_app_data: {raw_data}")
            
            # УНИФИЦИРОВАННЫЙ ОТВЕТ для текстовых данных
            response = f"📝 **Текстовые данные от WebApp**\n\n"
            response += f"💬 **Содержимое**: `{raw_data}`\n"
            response += f"⏰ **Время**: {message.date.strftime('%H:%M:%S')}\n"
            response += f"⚠️ **Формат**: Не JSON"
            
            await message.answer(response, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Unexpected error processing web_app_data: {e}", exc_info=True)
            
            # УНИФИЦИРОВАННЫЙ ОТВЕТ для ошибок
            response = f"❌ **Ошибка обработки WebApp данных**\n\n"
            response += f"🚫 **Ошибка**: `{str(e)}`\n"
            response += f"⏰ **Время**: {message.date.strftime('%H:%M:%S')}"
            
            await message.answer(response, parse_mode="Markdown")
            
    else:
        # Эта ветка не должна сработать при правильной работе фильтра F.web_app_data
        logger.error("F.web_app_data triggered, but web_app_data is missing")

# Универсальный обработчик для отладки всех сообщений в webapp роутере
@router.message()
async def handle_all_messages_webapp_router(message: Message):
    """
    Fallback обработчик для отладки сообщений, не пойманных основным фильтром.
    """
    logger.debug(f"WebApp router fallback: content_type={message.content_type}")
    
    # Проверяем, есть ли web_app_data в этом сообщении
    if hasattr(message, 'web_app_data') and message.web_app_data:
        logger.info(f"Found web_app_data in fallback: {message.web_app_data.data}")
        # Перенаправляем на основной обработчик
        await handle_webapp_data_specific_filter(message)
    else:
        logger.debug("No web_app_data in fallback") 