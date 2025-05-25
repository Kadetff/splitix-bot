import json
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, InlineQueryResultArticle, InputTextMessageContent

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
logger.propagate = False

router = Router()

@router.message(F.web_app_data)
async def handle_webapp_data_specific_filter(message: Message):
    """
    Обработчик данных от WebApp.
    Создает одинаковые сообщения для обеих типов кнопок (Inline и Reply).
    """
    logger.critical("!!!! WEBAPP DATA RECEIVED !!!!")
    
    if message.web_app_data and message.web_app_data.data:
        logger.critical(f"!!!! WebApp Data: {message.web_app_data.data} !!!!")
        
        raw_data = message.web_app_data.data
        logger.critical(f"!!!! RAW DATA: '{raw_data}' !!!!")
        
        # Простая проверка: если данные = "Привет", это наш простой тест
        if raw_data.strip() == "Привет":
            logger.critical(f"!!!! УСПЕХ! Получили простое сообщение: '{raw_data}' !!!!")
            
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
            
            logger.critical(f"!!!! PARSED: button_type={button_type}, source={source}, payload={payload} !!!!")

            # УНИФИЦИРОВАННЫЙ ОТВЕТ (одинаковый внешний вид для всех типов)
            response = f"✅ **Данные от WebApp получены!**\n\n"
            
            # Показываем тип кнопки только в техническом блоке
            if button_type == 'inline':
                response += f"🔵 **Тип кнопки**: Inline\n"
            elif button_type == 'reply':
                response += f"🟢 **Тип кнопки**: Reply\n"
            else:
                response += f"⚪ **Тип кнопки**: {button_type}\n"
            
            # Показываем содержимое данных
            if isinstance(payload, str):
                response += f"💬 **Сообщение**: `{payload}`\n"
            elif isinstance(payload, dict):
                if 'message' in payload:
                    response += f"💬 **Сообщение**: `{payload['message']}`\n"
                if 'items' in payload:
                    response += f"📦 **Элементы**: `{payload['items']}`\n"
                if 'count' in payload:
                    response += f"🔢 **Количество**: `{payload['count']}`\n"
            
            response += f"⏰ **Время**: {message.date.strftime('%H:%M:%S')}\n"
            response += f"🔧 **Источник**: {source}"

            await message.answer(response, parse_mode="Markdown")
                
        except json.JSONDecodeError:
            logger.error(f"!!!! JSONDecodeError parsing web_app_data: '{raw_data}' !!!!")
            
            # УНИФИЦИРОВАННЫЙ ОТВЕТ для текстовых данных
            response = f"📝 **Текстовые данные от WebApp**\n\n"
            response += f"💬 **Содержимое**: `{raw_data}`\n"
            response += f"⏰ **Время**: {message.date.strftime('%H:%M:%S')}\n"
            response += f"⚠️ **Формат**: Не JSON"
            
            await message.answer(response, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"!!!! Unexpected error processing web_app_data: {e} !!!!", exc_info=True)
            
            # УНИФИЦИРОВАННЫЙ ОТВЕТ для ошибок
            response = f"❌ **Ошибка обработки WebApp данных**\n\n"
            response += f"🚫 **Ошибка**: `{str(e)}`\n"
            response += f"⏰ **Время**: {message.date.strftime('%H:%M:%S')}"
            
            await message.answer(response, parse_mode="Markdown")
            
    else:
        # Эта ветка не должна сработать при правильной работе фильтра F.web_app_data
        logger.error("!!!! F.web_app_data triggered, but web_app_data is missing !!!!")

# Универсальный обработчик для отладки всех сообщений в webapp роутере
@router.message()
async def handle_all_messages_webapp_router(message: Message):
    """
    Fallback обработчик для отладки сообщений, не пойманных основным фильтром.
    """
    logger.critical(f"!!!! WEBAPP_ROUTER FALLBACK !!!! content_type: {message.content_type}")
    logger.critical(f"!!!! Message data: {message.model_dump_json(indent=2)}")
    
    # Проверяем, есть ли web_app_data в этом сообщении
    if hasattr(message, 'web_app_data') and message.web_app_data:
        logger.critical(f"!!!! FOUND web_app_data in fallback !!!! data: {message.web_app_data.data}")
        # Перенаправляем на основной обработчик
        await handle_webapp_data_specific_filter(message)
    else:
        logger.critical(f"!!!! NO web_app_data in fallback !!!!") 