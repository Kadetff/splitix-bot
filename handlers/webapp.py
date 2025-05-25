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
    Поддерживает запуск как из Reply-клавиатуры, так и из Inline-клавиатуры.
    """
    logger.critical("!!!! WEBAPP DATA RECEIVED !!!!")
    
    # Определяем тип источника WebApp данных
    source_type = "Unknown"
    if message.reply_to_message:
        source_type = "Reply-клавиатура"
    elif hasattr(message, 'via_bot') and message.via_bot:
        source_type = "Inline-клавиатура (через answerWebAppQuery)"
    else:
        source_type = "Inline-клавиатура"
    
    logger.critical(f"!!!! Источник данных: {source_type} !!!!")
    
    if message.web_app_data and message.web_app_data.data:
        logger.critical(f"!!!! WebApp Data: {message.web_app_data.data} !!!!")
        logger.critical(f"!!!! Full message: {message.model_dump_json(indent=2)} !!!!")
        
        raw_data = message.web_app_data.data
        logger.critical(f"!!!! RAW DATA: '{raw_data}' !!!!")
        
        # Простая проверка: если данные = "Привет", это наш простой тест
        if raw_data.strip() == "Привет":
            logger.critical(f"!!!! УСПЕХ! Получили простое сообщение: '{raw_data}' !!!!")
            response = f"🎉 **УСПЕХ!** Бот получил сообщение от WebApp!\n\n"
            response += f"📱 **Источник**: {source_type}\n"
            response += f"💬 **Сообщение**: `{raw_data}`\n"
            response += f"⏰ **Время**: {message.date.strftime('%H:%M:%S')}"
            
            await message.answer(response, parse_mode="Markdown")
            return
        
        # Пытаемся парсить как JSON для сложных данных
        query_id = None
        try:
            data = json.loads(raw_data)
            query_id = data.get('query_id') 
            logger.info(f"Parsed web_app_data: {data}")

            # Формируем детальный ответ
            response = f"✅ **Данные от WebApp получены!**\n\n"
            response += f"📱 **Источник**: {source_type}\n"
            response += f"🔢 **Query ID**: `{query_id or 'отсутствует'}`\n"
            
            # Показываем информацию о выбранных товарах, если есть
            selected_items = data.get('selected_items', {})
            if selected_items:
                response += f"📊 **Выбрано позиций**: {len(selected_items)}\n"
                response += f"📝 **Детали выбора**: `{selected_items}`\n"
            
            response += f"\n📄 **Полные данные**: ```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"

            # Для Reply-кнопок может быть query_id для ответа
            if query_id and source_type == "Reply-клавиатура":
                logger.info(f"Attempting to answer WebApp query_id: {query_id}")
                await message.bot.answer_web_app_query(
                    web_app_query_id=query_id,
                    result=InlineQueryResultArticle(
                        id=str(query_id), 
                        title="Данные получены ботом",
                        input_message_content=InputTextMessageContent(
                            message_text=f"✅ Бот успешно получил данные от WebApp (источник: {source_type})"
                        )
                    )
                )
                logger.info(f"Successfully called answer_web_app_query for query_id: {query_id}")
                response += f"\n🔄 **Статус**: WebApp query подтвержден"
            else:
                response += f"\n⚠️ **Статус**: {'query_id отсутствует' if not query_id else 'Inline-источник, answerWebAppQuery уже выполнен'}"
                
            await message.answer(response, parse_mode="Markdown")
                
        except json.JSONDecodeError:
            logger.error(f"!!!! JSONDecodeError parsing web_app_data: '{raw_data}' !!!!")
            response = f"📝 **Текстовые данные от WebApp**\n\n"
            response += f"📱 **Источник**: {source_type}\n"
            response += f"💬 **Содержимое**: `{raw_data}`\n"
            response += f"⚠️ **Формат**: Не JSON"
            
            await message.answer(response, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"!!!! Unexpected error processing web_app_data: {e} !!!!", exc_info=True)
            response = f"❌ **Ошибка обработки WebApp данных**\n\n"
            response += f"📱 **Источник**: {source_type}\n"
            response += f"🚫 **Ошибка**: `{str(e)}`"
            
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