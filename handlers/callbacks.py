import logging
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from utils.keyboards import create_items_keyboard_with_counters
from handlers.photo import ReceiptStates
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = Router()

# Будет установлено из main.py
message_states: Dict[int, Dict[str, Any]] = {}

@router.callback_query(F.data.startswith("increment_item:"), ReceiptStates.waiting_for_items_selection)
async def handle_item_increment(callback: CallbackQuery, state: FSMContext):
    try:
        # Получаем индекс товара из callback_data
        item_idx = int(callback.data.split(":")[1])
        
        # Получаем message_id сообщения с клавиатурой
        message_id = callback.message.message_id
        
        # Проверяем, есть ли данные для этого сообщения
        if message_id not in message_states:
            logger.warning(f"Состояние для message_id {message_id} не найдено")
            await callback.answer("Состояние для этого списка не найдено. Возможно, он устарел.", show_alert=True)
            return
        
        # Получаем данные из состояния
        message_data = message_states[message_id]
        items = message_data.get("items", [])
        
        # Проверяем индекс
        if item_idx < 0 or item_idx >= len(items):
            logger.error(f"Неверный item_idx {item_idx} для message_id {message_id}")
            await callback.answer("Ошибка: неверный индекс позиции.")
            return
        
        # Получаем user_id
        user_id = callback.from_user.id
        
        # Получаем или инициализируем словарь выборов пользователя
        user_selections = message_data.setdefault("user_selections", {})
        user_counts = user_selections.setdefault(user_id, {})
        
        # Получаем информацию о товаре и текущем выборе
        item_info = items[item_idx]
        openai_quantity = item_info.get("quantity_from_openai", 1)
        current_count = user_counts.get(item_idx, 0)
        
        # Увеличиваем количество выбранных товаров или сбрасываем при достижении максимума
        if current_count < openai_quantity:
            user_counts[item_idx] = current_count + 1
            count_message = f"Ваш счетчик для '{item_info.get('description', 'N/A')[:20]}...' увеличен до {user_counts[item_idx]}"
        else:
            user_counts[item_idx] = 0
            count_message = f"Ваш счетчик для '{item_info.get('description', 'N/A')[:20]}...' сброшен"
        
        # Обновляем клавиатуру
        keyboard = create_items_keyboard_with_counters(items, user_counts)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        
        # Отправляем уведомление
        await callback.answer(count_message)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке increment_item: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.")

@router.callback_query(F.data == "confirm_selection", ReceiptStates.waiting_for_items_selection)
async def handle_confirm_selection(callback: CallbackQuery, state: FSMContext):
    try:
        # Получаем message_id сообщения с клавиатурой
        message_id = callback.message.message_id
        
        # Проверяем, есть ли данные для этого сообщения
        if message_id not in message_states:
            logger.warning(f"Состояние для message_id {message_id} не найдено")
            await callback.answer("Состояние для этого списка не найдено. Возможно, он устарел.", show_alert=True)
            return
        
        # Получаем данные из состояния
        message_data = message_states[message_id]
        items = message_data.get("items", [])
        service_charge_percent = message_data.get("service_charge_percent")
        actual_discount_percent = message_data.get("actual_discount_percent")
        total_discount_amount = message_data.get("total_discount_amount")
        
        # Получаем user_id
        user_id = callback.from_user.id
        
        # Получаем выбор пользователя
        user_selections = message_data.get("user_selections", {})
        user_counts = user_selections.get(user_id, {})
        
        # Проверяем, есть ли выбранные товары
        if not any(user_counts.values()):
            await callback.answer("❌ Выберите хотя бы один товар")
            return
        
        # Формируем сообщение с итогами
        user_mention = f"@{callback.from_user.username}" if callback.from_user.username else f"{callback.from_user.first_name}"
        summary = f"<b>{user_mention}, ваш выбор:</b>\n\n"
        total_sum = Decimal("0.00")
        
        # Расчет общей суммы всех позиций в чеке для распределения скидки
        total_check_sum = Decimal("0.00")
        for item in items:
            if item.get("total_amount_from_openai") is not None:
                total_check_sum += item["total_amount_from_openai"]
        
        # Формируем список выбранных товаров и считаем сумму
        for idx, count in user_counts.items():
            if count > 0:
                item = items[idx]
                description = item.get("description", "N/A")
                
                # Определяем, является ли товар весовым
                is_weight_item = False
                openai_quantity = item.get("quantity_from_openai", 1)
                total_amount_openai = item.get("total_amount_from_openai")
                unit_price_openai = item.get("unit_price_from_openai")
                
                if openai_quantity == 1 and total_amount_openai is not None and unit_price_openai is not None:
                    price_diff = abs(total_amount_openai - unit_price_openai)
                    is_weight_item = price_diff > Decimal("0.01")
                
                # Расчет стоимости
                if is_weight_item and total_amount_openai is not None:
                    item_total = total_amount_openai
                elif unit_price_openai is not None:
                    item_total = unit_price_openai * Decimal(count)
                elif total_amount_openai is not None and openai_quantity > 0:
                    try:
                        unit_price = total_amount_openai / Decimal(str(openai_quantity))
                        item_total = unit_price * Decimal(count)
                    except Exception:
                        item_total = total_amount_openai
                else:
                    continue
                
                # Применяем скидки на товар, если есть
                discount_info = ""
                if item.get("discount_percent") is not None:
                    discount_amount = (item_total * item["discount_percent"] / Decimal("100")).quantize(Decimal("0.01"))
                    item_total -= discount_amount
                    discount_info = f" (скидка {item['discount_percent']}%)"
                elif item.get("discount_amount") is not None:
                    if openai_quantity > 0:
                        item_discount = (item["discount_amount"] * Decimal(count) / Decimal(str(openai_quantity))).quantize(Decimal("0.01"))
                        item_total -= item_discount
                        discount_info = f" (скидка {item_discount:.2f})"
                
                # Добавляем позицию в итог
                total_sum += item_total
                summary += f"- {description}: {count} шт. = {item_total:.2f}{discount_info}\n"
        
        # Добавляем информацию о сервисном сборе
        if service_charge_percent is not None:
            service_amount = (total_sum * service_charge_percent / Decimal("100")).quantize(Decimal("0.01"))
            total_sum += service_amount
            summary += f"\n<b>Плата за обслуживание ({service_charge_percent}%): {service_amount:.2f}</b>"
        
        # Добавляем информацию об общей скидке
        if actual_discount_percent is not None:
            discount_amount = (total_sum * actual_discount_percent / Decimal("100")).quantize(Decimal("0.01"))
            total_sum -= discount_amount
            summary += f"\n<b>Скидка ({actual_discount_percent}%): -{discount_amount:.2f}</b>"
        elif total_discount_amount is not None and total_check_sum > 0:
            user_discount = (total_discount_amount * total_sum / total_check_sum).quantize(Decimal("0.01"))
            total_sum -= user_discount
            summary += f"\n<b>Скидка: -{user_discount:.2f}</b>"
        
        # Добавляем итоговую сумму
        summary += f"\n\n<b>Итоговая сумма: {total_sum:.2f}</b>"
        
        # Отправляем итоговое сообщение в чат
        await callback.message.answer(summary, parse_mode="HTML")
        await callback.answer("✅ Ваш выбор подтвержден!")
        
        # Очищаем состояние FSM
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при подтверждении выбора: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.")

@router.callback_query(F.data == "show_my_summary", ReceiptStates.waiting_for_items_selection)
async def handle_show_my_summary(callback: CallbackQuery, state: FSMContext):
    try:
        # Получаем message_id сообщения с клавиатурой
        message_id = callback.message.message_id
        
        # Проверяем, есть ли данные для этого сообщения
        if message_id not in message_states:
            logger.warning(f"Состояние для message_id {message_id} не найдено")
            await callback.answer("Состояние для этого списка не найдено. Возможно, он устарел.", show_alert=True)
            return
        
        # Получаем данные из состояния
        message_data = message_states[message_id]
        items = message_data.get("items", [])
        
        # Получаем user_id и его выбор
        user_id = callback.from_user.id
        user_selections = message_data.get("user_selections", {})
        user_counts = user_selections.get(user_id, {})
        
        # Формируем сообщение с текущим выбором
        user_mention = f"@{callback.from_user.username}" if callback.from_user.username else f"{callback.from_user.first_name}"
        summary_text = f"**{user_mention}, ваш текущий выбор:**\\n\\n"
        
        # Создаем клавиатуру с текущим выбором
        keyboard = create_items_keyboard_with_counters(items, user_counts, view_mode="my_summary_display")
        
        # Обновляем сообщение
        await callback.message.edit_text(summary_text, reply_markup=keyboard)
        await callback.answer("Отображен ваш текущий выбор.")
        
    except Exception as e:
        logger.error(f"Ошибка при показе текущего выбора: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.")

@router.callback_query(F.data == "show_total_summary", ReceiptStates.waiting_for_items_selection)
async def handle_show_total_summary(callback: CallbackQuery, state: FSMContext):
    try:
        # Получаем message_id сообщения с клавиатурой
        message_id = callback.message.message_id
        
        # Проверяем, есть ли данные для этого сообщения
        if message_id not in message_states:
            logger.warning(f"Состояние для message_id {message_id} не найдено")
            await callback.answer("Состояние для этого списка не найдено. Возможно, он устарел.", show_alert=True)
            return
        
        # Получаем данные из состояния
        message_data = message_states[message_id]
        items = message_data.get("items", [])
        
        # Получаем все выборы пользователей
        user_selections = message_data.get("user_selections", {})
        
        # Рассчитываем агрегированные счетчики
        aggregated_counts = {idx: 0 for idx in range(len(items))}
        for _user_id, user_counts in user_selections.items():
            for item_idx, count in user_counts.items():
                if item_idx in aggregated_counts:
                    aggregated_counts[item_idx] += count
        
        # Формируем сообщение
        summary_text = "**Общий итог по чеку (выбрано всеми / количество в чеке):**\\n\\n"
        
        # Создаем клавиатуру с общим итогом
        keyboard = create_items_keyboard_with_counters(items, aggregated_counts, view_mode="total_summary_display")
        
        # Обновляем сообщение
        await callback.message.edit_text(summary_text, reply_markup=keyboard)
        await callback.answer("Отображен общий итог по чеку.")
        
    except Exception as e:
        logger.error(f"Ошибка при показе общего итога: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.")

@router.callback_query(F.data == "back_to_selection", ReceiptStates.waiting_for_items_selection)
async def handle_back_to_selection(callback: CallbackQuery, state: FSMContext):
    try:
        # Получаем message_id сообщения с клавиатурой
        message_id = callback.message.message_id
        
        # Проверяем, есть ли данные для этого сообщения
        if message_id not in message_states:
            logger.warning(f"Состояние для message_id {message_id} не найдено")
            await callback.answer("Состояние для этого списка не найдено. Возможно, он устарел.", show_alert=True)
            return
        
        # Получаем данные из состояния
        message_data = message_states[message_id]
        items = message_data.get("items", [])
        
        # Получаем выбор пользователя
        user_id = callback.from_user.id
        user_selections = message_data.get("user_selections", {})
        user_counts = user_selections.get(user_id, {})
        
        # Создаем клавиатуру выбора
        keyboard = create_items_keyboard_with_counters(items, user_counts)
        
        # Обновляем сообщение
        await callback.message.edit_text(
            "Распознанные позиции. Выберите количество или подтвердите:",
            reply_markup=keyboard
        )
        await callback.answer("Возврат к выбору позиций.")
        
    except Exception as e:
        logger.error(f"Ошибка при возврате к выбору: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.") 