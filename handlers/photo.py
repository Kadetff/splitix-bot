import logging
import aiohttp
from decimal import Decimal
from aiogram import F, Router
from aiogram.types import Message
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.openai_service import process_receipt_with_openai
from utils.keyboards import create_receipt_keyboard
from utils.api import check_api_health, prepare_data_for_api
from utils.formatters import format_item_line, calculate_totals
from typing import Dict, Any
from config.settings import WEBAPP_URL

logger = logging.getLogger(__name__)
router = Router()

class ReceiptStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_items_selection = State()

# Будет установлено из main.py
message_states: Dict[int, Dict[str, Any]] = {}

async def save_receipt_data_to_api(message_id: int, data: Dict[str, Any]) -> bool:
    """Сохраняет данные чека в API для веб-приложения"""
    if not WEBAPP_URL or "http://localhost" in WEBAPP_URL or "http://127.0.0.1" in WEBAPP_URL:
        logger.warning("WEBAPP_URL не настроен или использует localhost")
        return False
    
    clean_url = WEBAPP_URL.strip('"\'')
    timeout = aiohttp.ClientTimeout(total=5.0)
    
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            if not await check_api_health(session, clean_url):
                return False
            
            api_url = f"{clean_url}/api/receipt/{message_id}"
            serializable_data = prepare_data_for_api(data)
            
            async with session.post(api_url, json=serializable_data) as response:
                if response.status == 200:
                    logger.info(f"Данные чека сохранены для message_id: {message_id}")
                    return True
                error_text = await response.text()
                logger.error(f"Ошибка API: {response.status}, {error_text}")
                return False
                
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}", exc_info=True)
        return False

async def process_receipt_photo(message: Message, state: FSMContext):
    """Обрабатывает фото чека"""
    try:
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        image_data = file_bytes.read()
        
        processing_message = await message.answer("⏳ Обрабатываю чек...")
        
        items, service_charge, total_check_amount, total_discount_percent, total_discount_amount = await process_receipt_with_openai(image_data)
        
        if not items:
            await processing_message.edit_text("❌ Не удалось распознать чек. Пожалуйста, попробуйте еще раз или отправьте более четкое фото.")
            await state.clear()
            return
        
        calculated_total, service_charge_amount, actual_discount_percent = calculate_totals(
            items, service_charge, total_discount_amount
        )
        
        # Формируем сообщение
        response_msg_text = "<b>📋 Распознанные позиции из чека:</b>\n\n"
        response_msg_text += "".join(format_item_line(item) for item in items)
        
        response_msg_text += "\n<b>📊 Итоговая информация:</b>\n"
        
        if total_discount_amount is not None:
            response_msg_text += f"🎉 Скидка: {actual_discount_percent}% (-{total_discount_amount:.2f})\n"
        
        if service_charge is not None:
            response_msg_text += f"💰 Сервисный сбор: {service_charge}% (+{service_charge_amount:.2f})\n"
        
        if total_check_amount is not None:
            if abs(calculated_total - total_check_amount) < Decimal("0.01"):
                response_msg_text += f"✅ Итоговая сумма: {total_check_amount:.2f} (совпадает с расчетом)\n"
            else:
                response_msg_text += f"⚠️ Внимание: сумма в чеке ({total_check_amount:.2f}) не совпадает с расчетом ({calculated_total:.2f})\n"
        
        # Сохраняем данные
        receipt_data = {
            "items": items,
            "user_selections": {},
            "service_charge_percent": service_charge,
            "total_check_amount": total_check_amount,
            "total_discount_percent": total_discount_percent,
            "total_discount_amount": total_discount_amount,
            "actual_discount_percent": actual_discount_percent,
        }
        
        message_states[processing_message.message_id] = receipt_data
        
        # Сохраняем в API
        await save_receipt_data_to_api(processing_message.message_id, receipt_data)
        
        # Создаем клавиатуру
        keyboard = create_receipt_keyboard(
            processing_message.message_id,
            message.chat.type
        )
        
        # Отправляем итоговое сообщение
        await processing_message.edit_text(
            response_msg_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(ReceiptStates.waiting_for_items_selection)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обработке фото. Пожалуйста, попробуйте еще раз.")

@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    """Обработчик сообщений с фото"""
    current_state = await state.get_state()
    
    # В личном чате обрабатываем фото сразу
    if message.chat.type == ChatType.PRIVATE:
        await process_receipt_photo(message, state)
    # В групповом чате только после команды /split
    elif current_state == ReceiptStates.waiting_for_photo:
        await process_receipt_photo(message, state)