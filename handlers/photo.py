import logging
from decimal import Decimal
from aiogram import F, Router
from aiogram.types import Message
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.openai_service import process_receipt_with_openai
from utils.keyboards import create_items_keyboard_with_counters
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = Router()

class ReceiptStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_items_selection = State()

# Будет установлено из main.py
message_states: Dict[int, Dict[str, Any]] = {}

async def process_receipt_photo(message: Message, state: FSMContext):
    try:
        # Получаем фото с наилучшим разрешением
        photo = message.photo[-1]
        logger.info(f"Получено фото ID: {photo.file_id}, размер: {photo.file_size} байт")
        
        # Скачиваем фото
        file = await message.bot.get_file(photo.file_id)
        file_path = file.file_path
        logger.info(f"Получен путь к файлу: {file_path}")
        
        # Получаем бинарные данные фото
        file_bytes = await message.bot.download_file(file_path)
        image_data = file_bytes.read()
        logger.info(f"Фото скачано, размер: {len(image_data)} байт")
        
        # Отправляем сообщение о начале обработки
        processing_message = await message.answer("⏳ Обрабатываю чек...")
        
        # Обрабатываем чек через OpenAI
        logger.info("Отправляем фото в OpenAI для анализа...")
        items, service_charge, total_check_amount, total_discount_percent, total_discount_amount = await process_receipt_with_openai(image_data)
        
        if not items:
            logger.warning("OpenAI не смог распознать товарные позиции в чеке")
            await processing_message.edit_text("❌ Не удалось распознать чек. Пожалуйста, попробуйте еще раз или отправьте более четкое фото.")
            await state.clear()
            return
        
        logger.info(f"Успешно распознано {len(items)} позиций в чеке")
        
        # Переименовываем total_before_discounts и улучшаем расчеты
        total_items_cost = Decimal("0.00")  # Стоимость всех товарных позиций до применения скидок
        total_discounts = total_discount_amount if total_discount_amount is not None else Decimal("0.00")

        # Считаем сумму до скидок и сумму скидок
        for item in items:
            if item["total_amount_from_openai"] is not None:
                item_total = item["total_amount_from_openai"]
                total_items_cost += item_total
        
        # Итоговая сумма = сумма до скидок - сумма скидок
        calculated_total = total_items_cost - total_discounts
        
        # Добавляем сервисный сбор, если есть
        service_charge_amount = Decimal("0.00")
        if service_charge is not None:
            service_charge_amount = (calculated_total * service_charge / Decimal("100")).quantize(Decimal("0.01"))
            calculated_total += service_charge_amount

        # Формируем сообщение о распознанных позициях
        response_msg_text = "Позиции из чека — выберите, что добавить в свой счёт:\n"
        
        # Инициализируем переменную actual_discount_percent до условного блока
        actual_discount_percent = Decimal("0.00")
        
        # Добавляем информацию о скидках
        if total_discount_percent is not None or total_discount_amount is not None:
            # Рассчитываем фактический процент скидки
            if total_items_cost > 0:
                actual_discount_percent = (total_discounts * Decimal("100") / total_items_cost).quantize(Decimal("0.01"))
                response_msg_text += f"\n🎉 Применена скидка: {actual_discount_percent}% (-{total_discounts:.2f})"
        
        # Добавляем информацию о сервисном сборе
        if service_charge is not None:
            response_msg_text += f"\n💰 Сервисный сбор: {service_charge}% (+{service_charge_amount:.2f})"
        
        # Добавляем информацию о совпадении сумм
        if total_check_amount is not None:
            if abs(calculated_total - total_check_amount) < Decimal("0.01"):  # Учитываем возможные погрешности округления
                response_msg_text += f"\n✅ Итоговая сумма: {total_check_amount:.2f} (совпадает с расчетом)"
            else:
                response_msg_text += f"\n⚠️ Внимание: сумма в чеке ({total_check_amount:.2f}) не совпадает с расчетом ({calculated_total:.2f}). Возможно есть ошибки в распознавании."
        
        # Создаем пустой словарь счетчиков для пользователя
        empty_user_counts = {}
        
        # Создаем клавиатуру выбора
        keyboard = create_items_keyboard_with_counters(items, empty_user_counts)
        
        logger.info("Отправляем сообщение с результатами и клавиатурой")
        # Отправляем сообщение с информацией о чеке и клавиатурой
        result_message = await processing_message.edit_text(
            response_msg_text,
            reply_markup=keyboard
        )
        
        # Сохраняем данные в глобальный словарь message_states
        message_states[result_message.message_id] = {
            "items": items,
            "user_selections": {},  # Пустой словарь для выборов пользователей
            "service_charge_percent": service_charge,
            "total_check_amount": total_check_amount,
            "total_discount_percent": total_discount_percent,
            "total_discount_amount": total_discount_amount,
            "actual_discount_percent": actual_discount_percent,
        }
        
        logger.info(f"Состояние сохранено для message_id: {result_message.message_id}")
        
        # Устанавливаем состояние ожидания выбора товаров
        await state.set_state(ReceiptStates.waiting_for_items_selection)
        logger.info("Состояние установлено: waiting_for_items_selection")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обработке чека. Пожалуйста, попробуйте еще раз.")
        await state.clear()

@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    # Логируем параметры чата для диагностики
    chat_id = message.chat.id
    chat_type = message.chat.type
    chat_title = getattr(message.chat, 'title', 'Личное сообщение')
    current_state = await state.get_state()
    
    logger.info(f"Получено фото. ID чата: {chat_id}, Тип чата: {chat_type}, Название: {chat_title}, Текущее состояние: {current_state}")
    
    # Расширенное логирование для любых групп
    if hasattr(message.chat, 'is_forum'):
        logger.info(f"Дополнительные свойства: is_forum={message.chat.is_forum}")
        
    # Проверим, является ли это личным чатом
    is_personal_chat = (chat_type == ChatType.PRIVATE and chat_id > 0)
    logger.info(f"Решение: это личный чат? {is_personal_chat}")
    
    # Логика обработки фото
    if is_personal_chat:
        # В личке (один-на-один) — всегда обрабатываем фото как чек
        logger.info("Обрабатываем фото как чек (личный чат)")
        await process_receipt_photo(message, state)
    else:
        # Проверяем, находимся ли в состоянии ожидания фото
        should_process = (current_state == ReceiptStates.waiting_for_photo.state)
        logger.info(f"Это групповой чат. Обрабатываем фото? {should_process}")
        
        if should_process:
            logger.info("Обрабатываем фото как чек (группа, в состоянии ожидания)")
            await process_receipt_photo(message, state)
        else:
            logger.info("Игнорируем фото (группа, нет состояния ожидания)")
            # Игнорируем фото 