import logging
import aiohttp
import json
import asyncio
from decimal import Decimal
from aiogram import F, Router
from aiogram.types import Message, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.openai_service import process_receipt_with_openai
from utils.keyboards import create_receipt_keyboard
from typing import Dict, Any, Optional
from config.settings import WEBAPP_URL

logger = logging.getLogger(__name__)
router = Router()

class ReceiptStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_items_selection = State()

# Будет установлено из main.py
message_states: Dict[int, Dict[str, Any]] = {}

async def check_api_health(session: aiohttp.ClientSession, base_url: str) -> bool:
    """Проверяет доступность API"""
    try:
        async with session.get(f"{base_url}/health") as response:
            if response.status != 200:
                return False
            data = await response.json()
            return data.get("status") == "ok"
    except Exception as e:
        logger.error(f"Ошибка при проверке API: {e}")
        return False

def prepare_data_for_api(data: Dict[str, Any]) -> Dict[str, Any]:
    """Подготавливает данные для отправки в API"""
    serializable_data = {}
    for key, value in data.items():
        if key == "items":
            serializable_data[key] = [
                {k: float(v) if isinstance(v, Decimal) else v 
                 for k, v in item.items()}
                for item in value
            ]
        elif isinstance(value, Decimal):
            serializable_data[key] = float(value)
        else:
            serializable_data[key] = value
    return serializable_data

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

def format_item_line(item: Dict[str, Any]) -> str:
    """Форматирует строку товара для сообщения"""
    description = item.get("description", "N/A")
    quantity = item.get("quantity_from_openai", 1)
    unit_price = item.get("unit_price_from_openai")
    total_amount = item.get("total_amount_from_openai")
    
    if quantity == 1 and total_amount is not None and unit_price is not None:
        price_diff = abs(total_amount - unit_price)
        if price_diff > Decimal("0.01"):
            return f"• {description}: {total_amount:.2f}\n"
    
    if unit_price is not None:
        return f"• {description}: {unit_price:.2f} × {quantity} = {unit_price * quantity:.2f}\n"
    elif total_amount is not None:
        return f"• {description}: {total_amount:.2f}\n"
    
    return f"• {description}\n"

def calculate_totals(items: list, service_charge: Optional[Decimal], 
                    total_discount_amount: Optional[Decimal]) -> tuple:
    """Рассчитывает итоговые суммы"""
    total_items_cost = sum(
        item["total_amount_from_openai"] 
        for item in items 
        if item.get("total_amount_from_openai") is not None
    )
    
    total_discounts = total_discount_amount or Decimal("0.00")
    calculated_total = total_items_cost - total_discounts
    
    service_charge_amount = Decimal("0.00")
    if service_charge is not None:
        service_charge_amount = (calculated_total * service_charge / Decimal("100")).quantize(Decimal("0.01"))
        calculated_total += service_charge_amount
    
    actual_discount_percent = Decimal("0.00")
    if total_items_cost > 0:
        actual_discount_percent = (total_discounts * Decimal("100") / total_items_cost).quantize(Decimal("0.01"))
    
    return calculated_total, service_charge_amount, actual_discount_percent

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
    
    if current_state == ReceiptStates.waiting_for_photo:
        await process_receipt_photo(message, state)
    else:
        await message.answer("Пожалуйста, используйте команду /split для начала разделения чека.") 