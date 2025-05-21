import json
import logging
from aiogram import Router
from aiogram.types import Message

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
logger.propagate = False

router = Router()

@router.message()
async def handle_anything_in_webapp_router(message: Message):
    logger.critical("!!!! DEBUG_WEBAPP_ROUTER: handle_anything_in_webapp_router TRIGGERED !!!!")
    logger.critical(f"Message object: {message.model_dump_json(indent=2)}") # Логируем весь объект сообщения
    
    if message.web_app_data:
        logger.critical(f"!!!! DEBUG_WEBAPP_ROUTER: WebApp Data DETECTED: {message.web_app_data.data} !!!!")
        # Здесь можно будет добавить логику ответа, если данные придут
        try:
            data = json.loads(message.web_app_data.data)
            query_id = data.get('query_id')
            if query_id:
                logger.info(f"Attempting to answer WebApp query_id: {query_id} from universal handler")
                # Попытка ответить, если есть query_id
                from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
                await message.bot.answer_web_app_query(
                    web_app_query_id=query_id,
                    result=InlineQueryResultArticle(
                        id=str(query_id),
                        title="Получено (универсальный)",
                        input_message_content=InputTextMessageContent(message_text="DEBUG: Бот получил данные от WebApp (универсальный обработчик).")
                    )
                )
                logger.info(f"Successfully called answer_web_app_query for query_id: {query_id} (universal)")
            else:
                logger.warning("query_id not found in detected web_app_data (universal)")
            await message.answer("DEBUG: WebApp данные получены и обработаны универсальным хендлером.")
        except Exception as e:
            logger.error(f"Error processing detected web_app_data in universal handler: {e}", exc_info=True)
            await message.answer("DEBUG: Ошибка обработки WebApp данных в универсальном хендлере.")
    else:
        logger.warning("!!!! DEBUG_WEBAPP_ROUTER: WebApp Data NOT detected in this message. !!!!")
        logger.warning(f"Content type: {message.content_type}")
        logger.warning(f"Text: {message.text}") 