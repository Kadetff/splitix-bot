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

@router.message()
async def handle_all_messages_in_webapp_router(message: Message, state: FSMContext):
    logger.critical(f"[DEBUG_WEBAPP_ROUTER_UNIVERSAL] Вызван УНИВЕРСАЛЬНЫЙ обработчик в webapp.router! Сообщение: {message.message_id}, ContentType: {message.content_type}")
    if message.web_app_data:
        logger.info(f"[DEBUG_WEBAPP_ROUTER_UNIVERSAL] ОБНАРУЖЕНЫ WebApp данные: {message.web_app_data.data}")
        # Здесь можно временно добавить логику из handle_webapp_data для теста, если этот лог появится
        # Например, парсинг и попытку вызвать answer_web_app_query
        # Для начала просто убедимся, что данные приходят сюда.
    else:
        logger.info(f"[DEBUG_WEBAPP_ROUTER_UNIVERSAL] WebApp данные НЕ обнаружены. Text: {message.text}")
    pass # На данном этапе просто логируем и ничего не делаем

# ВРЕМЕННО КОММЕНТИРУЕМ СПЕЦИФИЧНЫЙ ОБРАБОТЧИК
# @router.message(F.web_app_data)
# async def handle_webapp_data(message: Message, state: FSMContext):
#     logger.info('=== [webapp.py] Вызван handle_webapp_data (через F.web_app_data) ===')
#     data = None 
#     try:
# logger.info(f"[webapp.py] Получены данные от WebApp: {getattr(message.web_app_data, 'data', None)} | message_id_in_message_obj: {message.message_id}")
# ... (весь остальной код handle_webapp_data закомментирован)
# ...
# await message.answer("❌ Произошла серьезная внутренняя ошибка при обработке вашего выбора. Пожалуйста, попробуйте еще раз.") 