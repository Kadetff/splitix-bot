import json
import logging
import uuid
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
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
    logger.critical(f"[DEBUG_WEBAPP_ROUTER] handle_all_messages ВЫЗВАН! Сообщение: {message}")
    
    # Проверяем наличие web_app_data
    if hasattr(message, 'web_app_data') and message.web_app_data:
        logger.info(f"[DEBUG_WEBAPP_ROUTER] WebApp данные ОБНАРУЖЕНЫ в handle_all_messages: {message.web_app_data.data}")
        # await handle_webapp_data(message, state) # <--- ВРЕМЕННО ЗАКОММЕНТИРОВАНО ДЛЯ ТЕСТА
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

# ВРЕМЕННО ОТКЛЮЧАЕМ СПЕЦИФИЧНЫЙ ОБРАБОТЧИК ДЛЯ ТЕСТА
# @router.message(F.web_app_data)
# async def handle_webapp_data(message: Message, state: FSMContext):
#     logger.info('=== Вызван handle_webapp_data ===')
#     try:
#         logger.info(f"Получены данные от WebApp: {getattr(message.web_app_data, 'data', None)} | message: {message}")
#         # Парсим JSON данные
#         try:
#             data = json.loads(message.web_app_data.data)
#             logger.info(f"[handle_webapp_data] Распарсенные данные: {data}")
#         except json.JSONDecodeError as e:
#             logger.error(f"[handle_webapp_data] Ошибка при парсинге JSON: {e}")
#             await message.answer("❌ Ошибка при обработке данных. Пожалуйста, попробуйте еще раз.")
#             return
#         
#         message_id = data.get('message_id')
#         selected_items = data.get('selected_items', {})
#         query_id = data.get('query_id')
#
#         logger.info(f"[handle_webapp_data] message_id: {message_id}, query_id: {query_id}, selected_items: {selected_items}")
#
#         if not message_id or not query_id:
#             logger.error(f"[handle_webapp_data] Отсутствуют обязательные поля: message_id={message_id}, query_id={query_id}")
#             if query_id:
#                 try:
#                     await message.bot.answer_web_app_query(
#                         web_app_query_id=query_id,
#                         result=InlineQueryResultArticle(
#                             id=str(uuid.uuid4()),
#                             title="Ошибка данных",
#                             input_message_content=InputTextMessageContent(
#                                 message_text="❌ Ошибка: отсутствуют необходимые данные в запросе от WebApp."
#                             )
#                         )
#                     )
#                     logger.info(f"[handle_webapp_data] Отправлен ответ WebApp (ошибка данных) для query_id: {query_id}")
#                 except Exception as e_ans:
#                     logger.error(f"[handle_webapp_data] Ошибка при отправке ответа WebApp (ошибка данных): {e_ans}")
#             await message.answer("❌ Ошибка: отсутствуют необходимые данные. Пожалуйста, попробуйте еще раз.")
#             return
#
#         logger.info(f"[handle_webapp_data] Пользователь {message.from_user.id} выбрал: {selected_items} для message_id: {message_id}")
#
#         try:
#             await message.bot.answer_web_app_query(
#                 web_app_query_id=query_id,
#                 result=InlineQueryResultArticle(
#                     id=str(uuid.uuid4()),
#                     title="Выбор сохранен!",
#                     input_message_content=InputTextMessageContent(
#                         message_text=f"Ваш выбор для чека (ID сообщения: {message_id}) был успешно обработан."
#                     )
#                 )
#             )
#             logger.info(f"[handle_webapp_data] Успешно отправлен ответ WebApp для query_id: {query_id}")
#         except Exception as e:
#             logger.error(f"[handle_webapp_data] Ошибка при отправке ответа WebApp (answer_web_app_query): {e}")
#             await message.answer("⚠️ Не удалось подтвердить операцию в WebApp, но данные могли быть обработаны. Пожалуйста, проверьте.")
#             return
#
#         items_text_list = []
#         for item_idx, count in selected_items.items():
#             items_text_list.append(f"Товар с индексом {item_idx}: {count} шт.")
#         items_text = "\n".join(items_text_list)
#         
#         calculated_total_str = "не рассчитана"
#
#         await message.answer(
#             f"✅ Ваш выбор для чека (ID сообщения: {message_id}) сохранен!\n\n"
#             f"Выбранные позиции:\n{items_text}\n\n"
#             f"Итого: {calculated_total_str}",
#         )
#         logger.info(f"[handle_webapp_data] Данные успешно обработаны и сообщение отправлено в чат для пользователя {message.from_user.id}")
#
#     except Exception as e:
#         logger.error(f"[handle_webapp_data] Глобальная ошибка при обработке данных: {e}", exc_info=True)
#         if data and data.get('query_id'):
#             try:
#                 await message.bot.answer_web_app_query(
#                     web_app_query_id=data.get('query_id'),
#                     result=InlineQueryResultArticle(
#                         id=str(uuid.uuid4()),
#                         title="Ошибка сервера",
#                         input_message_content=InputTextMessageContent(
#                             message_text="❌ Произошла внутренняя ошибка на сервере при обработке вашего выбора."
#                         )
#                     )
#                 )
#             except Exception as e_ans_err:
#                 logger.error(f"[handle_webapp_data] Ошибка при отправке ответа WebApp (глобальная ошибка): {e_ans_err}")
#         await message.answer("❌ Произошла серьезная ошибка при обработке данных. Пожалуйста, попробуйте еще раз.") 