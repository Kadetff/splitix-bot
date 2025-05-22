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
    logger.critical("!!!! DEBUG_WEBAPP_ROUTER: handle_webapp_data_specific_filter (F.web_app_data) TRIGGERED !!!!")
    if message.web_app_data and message.web_app_data.data:
        logger.critical(f"!!!! DEBUG_WEBAPP_ROUTER: WebApp Data Received: {message.web_app_data.data} !!!!")
        logger.critical(f"Full message object: {message.model_dump_json(indent=2)}")
        
        query_id = None
        try:
            data = json.loads(message.web_app_data.data)
            query_id = data.get('query_id') 
            logger.info(f"Parsed web_app_data: {data}")

            if query_id:
                logger.info(f"Attempting to answer WebApp query_id: {query_id}")
                await message.bot.answer_web_app_query(
                    web_app_query_id=query_id,
                    result=InlineQueryResultArticle(
                        id=str(query_id), 
                        title="Получено ботом (F.web_app_data)",
                        input_message_content=InputTextMessageContent(message_text="DEBUG: Бот получил данные от WebApp (F.web_app_data).")
                    )
                )
                logger.info(f"Successfully called answer_web_app_query for query_id: {query_id}")
                await message.answer(f"DEBUG: Данные WebApp (c query_id={query_id}) получены и подтверждены фильтром F.web_app_data.")
            else:
                logger.warning("!!!! DEBUG_WEBAPP_ROUTER: query_id not found in web_app_data. Cannot call answer_web_app_query. !!!!")
                await message.answer("DEBUG: Данные WebApp получены (F.web_app_data, query_id отсутствует).")
                
        except json.JSONDecodeError:
            logger.error("!!!! DEBUG_WEBAPP_ROUTER: JSONDecodeError parsing message.web_app_data.data !!!!")
            await message.answer("DEBUG: Ошибка: данные от WebApp не в формате JSON (F.web_app_data).")
        except Exception as e:
            logger.error(f"!!!! DEBUG_WEBAPP_ROUTER: Unexpected error processing web_app_data: {e} !!!!", exc_info=True)
            await message.answer("DEBUG: Неожиданная ошибка при парсинге/обработке данных от WebApp (F.web_app_data).")
            
    else:
        # Эта ветка не должна сработать, если F.web_app_data работает правильно, 
        # так как сам фильтр уже гарантирует наличие message.web_app_data
        logger.error("!!!! DEBUG_WEBAPP_ROUTER: F.web_app_data triggered, but web_app_data or data is missing (SHOULD NOT HAPPEN) !!!!")

# Универсальный обработчик для отладки всех сообщений в webapp роутере
@router.message()
async def handle_all_messages_webapp_router(message: Message):
    logger.critical(f"!!!! WEBAPP_ROUTER: Получено сообщение (НЕ F.web_app_data) !!!! content_type: {message.content_type}")
    logger.critical(f"!!!! WEBAPP_ROUTER: Полные данные сообщения: {message.model_dump_json(indent=2)}")
    
    # Проверяем, есть ли web_app_data в этом сообщении (хотя фильтр его не поймал)
    if hasattr(message, 'web_app_data') and message.web_app_data:
        logger.critical(f"!!!! WEBAPP_ROUTER: НАЙДЕНО web_app_data в fallback обработчике !!!! data: {message.web_app_data.data}")
        # Перенаправляем на основной обработчик
        await handle_webapp_data_specific_filter(message)
    else:
        logger.critical(f"!!!! WEBAPP_ROUTER: web_app_data отсутствует в fallback обработчике !!!!") 