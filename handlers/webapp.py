import json
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, InlineQueryResultArticle, InputTextMessageContent
# FSMContext пока не нужен для базовой проверки получения данных
# from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)
# Убедитесь, что уровень логирования позволяет видеть DEBUG и CRITICAL сообщения
# В main.py или при конфигурации логирования установите нужный уровень, например:
# logging.basicConfig(level=logging.DEBUG, ...)
# Для этого логгера можно установить свой уровень:
if not logger.handlers: # Предотвращаем дублирование хендлеров при перезагрузках
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


router = Router()

# message_states пока не используем, чтобы упростить отладку
# message_states = {}

@router.message(F.web_app_data)
async def handle_webapp_data_debug(message: Message):
    logger.critical("!!!! DEBUG: handle_webapp_data_debug TRIGGERED !!!!")
    if message.web_app_data and message.web_app_data.data:
        logger.critical(f"!!!! DEBUG: WebApp Data Received: {message.web_app_data.data} !!!!")
        
        query_id = None
        try:
            data = json.loads(message.web_app_data.data)
            # Пытаемся извлечь query_id, если он есть (для совместимости с новым фронтендом)
            query_id = data.get('query_id') 
            # Также логируем messageId и selectedItems для информации
            message_id_from_data = data.get('messageId')
            selected_items_from_data = data.get('selectedItems')
            logger.info(f"Parsed web_app_data: messageId='{message_id_from_data}', selectedItems='{selected_items_from_data}', query_id='{query_id}'")

        except json.JSONDecodeError:
            logger.error("!!!! DEBUG: JSONDecodeError parsing message.web_app_data.data !!!!")
            await message.answer("DEBUG: Ошибка: данные от WebApp не в формате JSON.")
            return # Выходим, если не можем распарсить

        except Exception as e:
            logger.error(f"!!!! DEBUG: Unexpected error parsing message.web_app_data.data: {e} !!!!", exc_info=True)
            await message.answer("DEBUG: Неожиданная ошибка при парсинге данных от WebApp.")
            return


        if query_id:
            logger.info(f"Attempting to answer WebApp query_id: {query_id}")
            try:
                await message.bot.answer_web_app_query(
                    web_app_query_id=query_id,
                    result=InlineQueryResultArticle(
                        id=str(query_id), # ID должен быть строкой и уникальным
                        title="Получено ботом",
                        input_message_content=InputTextMessageContent(message_text="DEBUG: Бот получил данные от WebApp.")
                    )
                )
                logger.info(f"Successfully called answer_web_app_query for query_id: {query_id}")
                # После успешного answer_web_app_query можно также отправить сообщение в чат, если нужно
                await message.answer(f"DEBUG: Данные WebApp (c query_id={query_id}) получены и подтверждены.")
            except Exception as e:
                logger.error(f"!!!! DEBUG: Error calling answer_web_app_query for query_id {query_id}: {e} !!!!", exc_info=True)
                # Если answer_web_app_query не удался, фронтенд может показать таймаут.
                # Отправим хотя бы сообщение в чат.
                await message.answer(f"DEBUG: Данные WebApp (c query_id={query_id}) получены, но ошибка при подтверждении WebApp: {e}")
        else:
            logger.warning("!!!! DEBUG: query_id not found in web_app_data. Cannot call answer_web_app_query. !!!!")
            # Это сценарий для старого index.html или если query_id не передается
            await message.answer("DEBUG: Данные WebApp получены (query_id отсутствует).")
            
    else:
        logger.error("!!!! DEBUG: handle_webapp_data_debug TRIGGERED but message.web_app_data is None or data is empty !!!!")
        await message.answer("DEBUG: Получен запрос от WebApp, но данные WebApp пусты.")

# Этот обработчик для отлова ВСЕХ сообщений, если F.web_app_data по какой-то причине не сработал.
@router.message()
async def handle_all_messages_debug(message: Message):
    logger.critical(f"!!!! DEBUG: handle_all_messages_debug TRIGGERED (ChatID: {message.chat.id}) !!!!")
    logger.critical(f"Message content type: {message.content_type}")
    logger.critical(f"Message text: {message.text}")
    logger.critical(f"Message web_app_data: {message.web_app_data}") # Должно быть None, если web_app_data_handler не сработал

    # Попытка обработать данные, если они пришли как простой текст (старый fallback)
    if message.text:
        try:
            data = json.loads(message.text)
            if 'messageId' in data and 'selectedItems' in data:
                logger.critical("!!!! DEBUG: Fallback handler (handle_all_messages_debug) detected webapp-like JSON in message.text !!!!")
                await message.answer("DEBUG: WebApp-подобные данные получены как текст (старый fallback).")
            else:
                logger.debug("DEBUG: Text message in fallback handler is not webapp-like JSON.")
        except json.JSONDecodeError:
            logger.debug("DEBUG: Text message in fallback handler is not JSON.")
        except Exception as e:
            logger.error(f"DEBUG: Error in fallback handler text processing: {e}", exc_info=True)
    else:
        logger.debug("DEBUG: Fallback handler: No text in message.") 