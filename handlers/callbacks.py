import logging
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, WebAppInfo
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.keyboards import create_items_keyboard_with_counters
from handlers.photo import ReceiptStates
from config.settings import WEBAPP_URL
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = Router()

# Будет установлено из main.py
message_states: Dict[int, Dict[str, Any]] = {}

@router.callback_query(F.data.startswith("increment_item:"), ReceiptStates.waiting_for_items_selection)
async def handle_item_increment(callback: CallbackQuery, state: FSMContext):
    try:
        # Логируем действие для отладки
        logger.info(f"Increment item callback от пользователя {callback.from_user.id}, data={callback.data}")
        
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
        
        logger.info(f"Текущие выборы пользователя {user_id}: {user_counts}")
        
        # Получаем информацию о товаре и текущем выборе
        item_info = items[item_idx]
        openai_quantity = item_info.get("quantity_from_openai", 1)
        current_count = user_counts.get(str(item_idx), 0)  # Используем строковые ключи для совместимости
        
        logger.info(f"Текущий счетчик для item_idx={item_idx}: {current_count}, max={openai_quantity}")
        
        # Увеличиваем количество выбранных товаров или сбрасываем при достижении максимума
        if current_count < openai_quantity:
            user_counts[str(item_idx)] = current_count + 1
            count_message = f"Ваш счетчик для '{item_info.get('description', 'N/A')[:20]}...' увеличен до {user_counts[str(item_idx)]}"
        else:
            user_counts[str(item_idx)] = 0
            count_message = f"Ваш счетчик для '{item_info.get('description', 'N/A')[:20]}...' сброшен"
        
        logger.info(f"Обновленные выборы пользователя {user_id}: {user_counts}")
        
        # Сохраняем обновленный выбор пользователя в глобальное состояние
        message_states[message_id]["user_selections"][user_id] = user_counts
        
        # Обновляем клавиатуру для ТЕКУЩЕГО пользователя
        try:
            keyboard = create_items_keyboard_with_counters(
                items, 
                user_counts, 
                chat_type=callback.message.chat.type,
                message_id=message_id
            )
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            logger.info(f"Клавиатура успешно обновлена для пользователя {user_id}")
        except Exception as keyboard_error:
            logger.error(f"Ошибка при обновлении клавиатуры: {keyboard_error}", exc_info=True)
            
            # Пробуем создать простую клавиатуру без WebApp
            try:
                simple_keyboard = InlineKeyboardBuilder()
                for idx, item in enumerate(items):
                    description = item.get("description", "N/A")[:25]
                    item_current_count = user_counts.get(str(idx), 0)
                    item_openai_quantity = item.get("quantity_from_openai", 1)
                    simple_keyboard.row(InlineKeyboardButton(
                        text=f"[{item_current_count}/{item_openai_quantity}] {description}", 
                        callback_data=f"increment_item:{idx}"
                    ))
                
                simple_keyboard.row(InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="confirm_selection"))
                await callback.message.edit_reply_markup(reply_markup=simple_keyboard.as_markup())
                logger.info(f"Простая клавиатура успешно создана для пользователя {user_id}")
            except Exception as simple_error:
                logger.error(f"Критическая ошибка при создании простой клавиатуры: {simple_error}", exc_info=True)
                await callback.answer("Ошибка при обновлении интерфейса. Пожалуйста, попробуйте еще раз.", show_alert=True)
        
        # Отправляем уведомление
        await callback.answer(count_message)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке increment_item: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.")

@router.callback_query(F.data == "confirm_selection", ReceiptStates.waiting_for_items_selection)
async def handle_confirm_selection(callback: CallbackQuery, state: FSMContext):
    try:
        # Логируем действие для отладки
        logger.info(f"Confirm selection callback от пользователя {callback.from_user.id}")
        
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
        
        logger.info(f"Выбор пользователя {user_id} для подтверждения: {user_counts}")
        
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
        for idx_str, count in user_counts.items():
            if count > 0:
                idx = int(idx_str)  # Преобразуем строковый индекс в целое число
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
        if actual_discount_percent is not None and actual_discount_percent > 0:
            discount_amount = (total_sum * actual_discount_percent / Decimal("100")).quantize(Decimal("0.01"))
            total_sum -= discount_amount
            summary += f"\n<b>Скидка ({actual_discount_percent}%): -{discount_amount:.2f}</b>"
        elif total_discount_amount is not None and total_check_sum > 0:
            user_discount = (total_discount_amount * total_sum / total_check_sum).quantize(Decimal("0.01"))
            total_sum -= user_discount
            summary += f"\n<b>Скидка: -{user_discount:.2f}</b>"
        
        # Добавляем итоговую сумму
        summary += f"\n\n<b>Итоговая сумма: {total_sum:.2f}</b>"
        
        # Сохраняем результат пользователя в глобальное состояние
        if "user_results" not in message_data:
            message_data["user_results"] = {}
        
        message_data["user_results"][user_id] = {
            "summary": summary,
            "total_sum": float(total_sum),
            "selected_items": {str(idx): count for idx, count in user_counts.items() if count > 0}
        }
        
        # Отправляем итоговое сообщение в чат
        await callback.message.answer(summary, parse_mode="HTML")
        
        # Создаем кнопку для просмотра всех результатов
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="👥 Посмотреть итоги всех участников", callback_data="show_all_results"))
        
        # Отправляем дополнительное сообщение с кнопкой просмотра всех результатов
        await callback.message.answer(
            "✅ Ваш выбор подтвержден и сохранен! Теперь каждый участник может сделать свой выбор независимо.",
            reply_markup=keyboard.as_markup()
        )
        
        await callback.answer("✅ Ваш выбор подтвержден!")
        
        # Не очищаем состояние FSM, чтобы другие пользователи могли сделать свой выбор
        # await state.clear()
        
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
        keyboard = create_items_keyboard_with_counters(items, user_counts, view_mode="my_summary_display", chat_type=callback.message.chat.type)
        
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
        keyboard = create_items_keyboard_with_counters(items, aggregated_counts, view_mode="total_summary_display", chat_type=callback.message.chat.type)
        
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
        keyboard = create_items_keyboard_with_counters(items, user_counts, chat_type=callback.message.chat.type)
        
        # Обновляем сообщение
        await callback.message.edit_text(
            "Распознанные позиции. Выберите количество или подтвердите:",
            reply_markup=keyboard
        )
        await callback.answer("Возврат к выбору позиций.")
        
    except Exception as e:
        logger.error(f"Ошибка при возврате к выбору: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.")

@router.callback_query(F.data == "show_inline_help")
async def process_show_inline_help(callback: CallbackQuery):
    """Обработчик для показа информации о том, как использовать inline-режим."""
    try:
        # Отправляем сообщение с инструкцией по использованию inline-режима
        bot_username = (await callback.bot.get_me()).username
        await callback.answer("Открываю инструкцию")
        
        message_text = (
            f"<b>Как использовать веб-приложение в группе?</b>\n\n"
            f"1. Напишите в любом чате <code>@{bot_username}</code>\n"
            f"2. Выберите пункт <b>🌐 Открыть веб-приложение</b>\n"
            f"3. Нажмите на появившуюся кнопку в сообщении\n\n"
            f"<i>Ограничения Telegram не позволяют напрямую открывать веб-приложения "
            f"в групповых чатах через обычные кнопки, но inline-режим работает!</i>"
        )
        
        # Создаем клавиатуру с кнопкой возврата
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_selection"))
        
        # Отправляем сообщение с инструкцией
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при показе инструкции по inline-режиму: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при загрузке инструкции")

@router.callback_query(F.data == "show_split_instructions")
async def handle_show_instructions(callback: CallbackQuery, state: FSMContext):
    """Показывает инструкцию по использованию функционала для разделения чека."""
    try:
        instructions_text = (
            "<b>📝 Как разделить чек с помощью бота:</b>\n\n"
            "<b>В личном чате:</b>\n"
            "1. Отправьте фото чека боту\n"
            "2. Нажмите на кнопку 'Открыть мини-приложение'\n"
            "3. Выберите позиции, которые вы заказали\n"
            "4. Нажмите 'Подтвердить'\n\n"
            
            "<b>В групповом чате:</b>\n"
            "1. Используйте команду /split\n"
            "2. Отправьте фото чека\n"
            "3. Нажмите на кнопку 'Открыть мини-приложение (в личном чате)'\n"
            "4. Бот откроет личный чат для выбора позиций\n"
            "5. После подтверждения выбора бот отправит вам сообщение с итогами\n\n"
            
            "<i>💡 Совет: Чтобы получить лучший результат, отправляйте четкое изображение чека с хорошо видимым текстом и суммами.</i>"
        )
        
        # Создаем кнопку возврата
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="⬅️ Вернуться", callback_data="back_to_receipt"))
        
        # Отправляем сообщение с инструкцией
        await callback.message.edit_text(
            instructions_text,
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при показе инструкции: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.")

@router.callback_query(F.data == "back_to_receipt")
async def handle_back_to_receipt(callback: CallbackQuery, state: FSMContext):
    """Возвращает пользователя к исходному сообщению с чеком."""
    try:
        # Получаем message_id текущего сообщения
        message_id = callback.message.message_id
        
        # Проверяем, есть ли данные для этого сообщения
        if message_id not in message_states:
            logger.warning(f"Состояние для message_id {message_id} не найдено")
            await callback.answer("Информация о чеке не найдена. Возможно, она устарела.", show_alert=True)
            return
            
        # Получаем данные о чеке
        receipt_data = message_states[message_id]
        items = receipt_data.get("items", [])
        service_charge = receipt_data.get("service_charge_percent")
        total_check_amount = receipt_data.get("total_check_amount")
        total_discount_percent = receipt_data.get("total_discount_percent")
        total_discount_amount = receipt_data.get("total_discount_amount")
        actual_discount_percent = receipt_data.get("actual_discount_percent", Decimal("0.00"))
        
        # Формируем сообщение с позициями
        response_msg_text = "<b>📋 Распознанные позиции из чека:</b>\n\n"
        
        # Добавляем информацию о распознанных позициях
        for idx, item in enumerate(items):
            description = item.get("description", "N/A")
            quantity = item.get("quantity_from_openai", 1)
            unit_price = item.get("unit_price_from_openai")
            total_amount = item.get("total_amount_from_openai")
            
            # Определяем, является ли товар весовым
            is_weight_item = False
            if quantity == 1 and total_amount is not None and unit_price is not None:
                price_diff = abs(total_amount - unit_price)
                is_weight_item = price_diff > Decimal("0.01")
                
            # Формируем строку позиции
            if is_weight_item and total_amount is not None:
                price_info = f"{total_amount:.2f}"
                item_line = f"• {description}: {price_info}\n"
            elif unit_price is not None:
                price_info = f"{unit_price:.2f} × {quantity} = {unit_price * quantity:.2f}"
                item_line = f"• {description}: {price_info}\n"
            elif total_amount is not None:
                price_info = f"{total_amount:.2f}"
                item_line = f"• {description}: {price_info}\n"
            else:
                item_line = f"• {description}\n"
                
            response_msg_text += item_line
        
        # Добавляем информацию о скидках и сервисном сборе
        response_msg_text += "\n<b>📊 Итоговая информация:</b>\n"
        
        if actual_discount_percent > 0:
            response_msg_text += f"🎉 Скидка: {actual_discount_percent}% (-{total_discount_amount:.2f})\n"
        
        if service_charge is not None:
            service_charge_amount = Decimal("0.00")
            if total_check_amount is not None:
                calculated_total = total_check_amount
                service_charge_amount = (calculated_total * service_charge / Decimal("100")).quantize(Decimal("0.01"))
            response_msg_text += f"💰 Сервисный сбор: {service_charge}% (+{service_charge_amount:.2f})\n"
        
        if total_check_amount is not None:
            response_msg_text += f"✅ Итоговая сумма: {total_check_amount:.2f}\n"
            
        # Создаем клавиатуру для WebApp или перехода в личный чат
        keyboard = InlineKeyboardBuilder()
        is_private_chat = callback.message.chat.type == ChatType.PRIVATE
        bot_username = "Splitix_bot"  # Fallback значение
        
        # Опциональная кнопка для отображения инструкции
        keyboard.row(InlineKeyboardButton(
            text="ℹ️ Инструкция по использованию",
            callback_data="show_split_instructions"
        ))
        
        # Добавляем кнопку для WebApp или перехода в личный чат
        if WEBAPP_URL and not ("http://localhost" in WEBAPP_URL or "http://127.0.0.1" in WEBAPP_URL):
            if is_private_chat:
                # В личном чате добавляем WebApp кнопку
                clean_url = WEBAPP_URL.strip('"\'')
                webapp_url = f"{clean_url}/{message_id}"
                
                try:
                    keyboard.row(InlineKeyboardButton(
                        text="🌐 Открыть мини-приложение", 
                        web_app=WebAppInfo(url=webapp_url)
                    ))
                except Exception as e:
                    logger.error(f"Ошибка при создании кнопки WebApp: {e}", exc_info=True)
            else:
                # В групповом чате добавляем кнопку для перехода в личный чат
                keyboard.row(InlineKeyboardButton(
                    text="🌐 Открыть мини-приложение (в личном чате)", 
                    url=f"https://t.me/{bot_username}?start=webapp_{message_id}"
                ))
        
        # Добавляем сообщение о мини-приложении
        webapp_info = ""
        if WEBAPP_URL and not ("http://localhost" in WEBAPP_URL or "http://127.0.0.1" in WEBAPP_URL):
            if is_private_chat:
                webapp_info = "\n\n<i>💡 Нажмите на кнопку ниже, чтобы открыть мини-приложение и выбрать свои позиции</i>"
            else:
                webapp_info = "\n\n<i>💡 В групповом чате нажмите на кнопку ниже, чтобы перейти в личный чат с ботом и открыть мини-приложение</i>"
        else:
            webapp_info = "\n\n<i>⚠️ Веб-приложение временно недоступно</i>" if WEBAPP_URL else ""
            
        # Добавляем информацию о возможности разделения чека между участниками
        share_info = "\n\n<b>👥 Этот чек могут разделить несколько участников!</b> Каждый может указать свои позиции независимо от других."
        
        # Отправляем сообщение с распознанными позициями и кнопкой WebApp
        await callback.message.edit_text(
            response_msg_text + webapp_info + share_info,
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML"
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при возврате к чеку: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.")

@router.callback_query(F.data == "show_all_results")
async def handle_show_all_results(callback: CallbackQuery):
    """Показывает итоги всех участников"""
    try:
        # Логируем действие для отладки
        logger.info(f"Show all results callback от пользователя {callback.from_user.id}")
        
        # Получаем message_id сообщения с клавиатурой
        message_id = callback.message.message_id
        
        # Ищем данные для чека в состояниях сообщений
        found_data = None
        for msg_id, data in message_states.items():
            if "user_results" in data:
                # Используем либо запрошенный message_id, либо в крайнем случае любой найденный
                if msg_id == message_id or found_data is None:
                    found_data = (msg_id, data)
                    if msg_id == message_id:
                        break
        
        if found_data:
            msg_id, message_data = found_data
            user_results = message_data.get("user_results", {})
            
            logger.info(f"Найдены результаты пользователей: {user_results}")
            
            if not user_results:
                logger.warning("В user_results нет данных")
                # Попробуем использовать user_selections вместо user_results
                if "user_selections" in message_data and message_data["user_selections"]:
                    logger.info("Используем user_selections для формирования итогов")
                    # Формируем сообщение с итогами всех участников на основе user_selections
                    all_results = "<b>📊 Итоги всех участников:</b>\n\n"
                    
                    # Расчет общей суммы всех позиций в чеке для распределения скидки
                    items = message_data.get("items", [])
                    service_charge_percent = message_data.get("service_charge_percent")
                    actual_discount_percent = message_data.get("actual_discount_percent")
                    total_discount_amount = message_data.get("total_discount_amount")
                    
                    total_check_sum = Decimal("0.00")
                    for item in items:
                        if item.get("total_amount_from_openai") is not None:
                            total_check_sum += item["total_amount_from_openai"]
                    
                    total_group_sum = Decimal("0.00")
                    user_selections = message_data.get("user_selections", {})
                    
                    for user_id_str, user_counts in user_selections.items():
                        # Пропускаем пользователей без выбора
                        if not any(user_counts.values()):
                            continue
                            
                        # Получаем имя пользователя
                        try:
                            user_id = int(user_id_str)
                            user = await callback.bot.get_chat_member(callback.message.chat.id, user_id)
                            user_name = user.user.username or f"{user.user.first_name}"
                        except Exception as e:
                            logger.error(f"Ошибка при получении информации о пользователе: {e}")
                            user_name = f"User {user_id_str}"
                        
                        # Рассчитываем сумму для пользователя
                        user_sum = Decimal("0.00")
                        for idx_str, count in user_counts.items():
                            if count > 0:
                                idx = int(idx_str)
                                if idx < len(items):
                                    item = items[idx]
                                    
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
                                    if item.get("discount_percent") is not None:
                                        discount_amount = (item_total * item["discount_percent"] / Decimal("100")).quantize(Decimal("0.01"))
                                        item_total -= discount_amount
                                    elif item.get("discount_amount") is not None:
                                        if openai_quantity > 0:
                                            item_discount = (item["discount_amount"] * Decimal(count) / Decimal(str(openai_quantity))).quantize(Decimal("0.01"))
                                            item_total -= item_discount
                                    
                                    user_sum += item_total
                        
                        # Применяем сервисный сбор
                        if service_charge_percent is not None:
                            service_amount = (user_sum * service_charge_percent / Decimal("100")).quantize(Decimal("0.01"))
                            user_sum += service_amount
                        
                        # Применяем скидку
                        if actual_discount_percent is not None and actual_discount_percent > 0:
                            discount_amount = (user_sum * actual_discount_percent / Decimal("100")).quantize(Decimal("0.01"))
                            user_sum -= discount_amount
                        elif total_discount_amount is not None and total_check_sum > 0:
                            user_discount = (total_discount_amount * user_sum / total_check_sum).quantize(Decimal("0.01"))
                            user_sum -= user_discount
                        
                        total_group_sum += user_sum
                        all_results += f"@{user_name}: {user_sum:.2f}\n"
                    
                    if total_group_sum > 0:
                        # Добавляем общую сумму группы
                        all_results += f"\n<b>💰 Общая сумма группы: {total_group_sum:.2f}</b>"
                        
                        # Отправляем сообщение с итогами
                        await callback.message.answer(all_results, parse_mode="HTML")
                        await callback.answer("✅ Итоги всех участников")
                        return
                    else:
                        logger.warning("Общая сумма группы равна 0")
                
                await callback.answer("Ни один из участников еще не сделал свой выбор", show_alert=True)
                return
                
            # Формируем сообщение с итогами всех участников на основе user_results
            all_results = "<b>📊 Итоги всех участников:</b>\n\n"
            
            total_group_sum = Decimal("0.00")
            for user_id_str, result in user_results.items():
                # Получаем имя пользователя
                try:
                    user_id = int(user_id_str)
                    user = await callback.bot.get_chat_member(callback.message.chat.id, user_id)
                    user_name = user.user.username or f"{user.user.first_name}"
                except Exception as e:
                    logger.error(f"Ошибка при получении информации о пользователе: {e}")
                    user_name = f"User {user_id_str}"
                
                # Получаем сумму пользователя
                user_sum = result.get("total_sum", 0)
                total_group_sum += Decimal(str(user_sum))
                
                # Добавляем в итог
                all_results += f"@{user_name}: {user_sum:.2f}\n"
            
            # Добавляем общую сумму группы
            all_results += f"\n<b>💰 Общая сумма группы: {total_group_sum:.2f}</b>"
            
            # Отправляем сообщение с итогами
            await callback.message.answer(all_results, parse_mode="HTML")
            await callback.answer("✅ Итоги всех участников")
            
        else:
            logger.warning("Не найдены данные о результатах")
            await callback.answer("Данные о результатах не найдены", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка при отображении итогов всех участников: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.") 