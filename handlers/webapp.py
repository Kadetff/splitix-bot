import json
import logging
from aiogram import Router, F
from aiogram.types import Message, Update
from aiogram.fsm.context import FSMContext
from handlers.photo import ReceiptStates
from handlers.callbacks import handle_confirm_selection
from decimal import Decimal

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
    logger.debug(f"Получено сообщение: {message}")
    
    # Проверяем наличие web_app_data
    if hasattr(message, 'web_app_data') and message.web_app_data:
        logger.info(f"Обнаружены данные WebApp: {message.web_app_data.data}")
        # Перенаправляем на обработчик WebApp данных
        await handle_webapp_data(message, state)
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
            # Попробуем распарсить текст как JSON
            try_parse = json.loads(message.text)
            logger.info(f"Сообщение содержит JSON: {message.text}")
            
            # Проверяем, содержит ли JSON данные messageId и selectedItems
            if 'messageId' in try_parse and 'selectedItems' in try_parse:
                logger.info(f"Найдены данные WebApp в тексте сообщения: {message.text}")
                
                # Создаем временные данные для обработки
                class WebAppData:
                    def __init__(self, data):
                        self.data = data
                
                # Добавляем web_app_data к сообщению
                message.web_app_data = WebAppData(message.text)
                
                # Перенаправляем на обработку в handle_webapp_data
                logger.info("Перенаправляем на обработку в handle_webapp_data")
                await handle_webapp_data(message, state)
                return
        except json.JSONDecodeError:
            pass
    
    # Если это регулярное сообщение без обработки, просто логируем
    logger.debug("Сообщение не опознано как данные WebApp, пропускаем")

@router.message(F.web_app_data)
async def handle_webapp_data(message: Message, state: FSMContext):
    """Обработчик данных, полученных от веб-приложения"""
    try:
        logger.debug(f"Получен объект сообщения: {message}")
        logger.info(f"Получены данные от веб-приложения: {getattr(message.web_app_data, 'data', 'None')}")
        
        # Проверяем наличие данных
        if not hasattr(message, 'web_app_data') or not message.web_app_data:
            logger.warning("WebApp данные отсутствуют в сообщении")
            await message.answer("❌ Не удалось получить данные из мини-приложения. Пожалуйста, попробуйте снова.")
            return
            
        # Получаем данные
        webapp_data = message.web_app_data.data
        
        # Проверяем, что данные не пустые
        if not webapp_data:
            logger.warning("WebApp данные пустые")
            await message.answer("❌ Получены пустые данные из мини-приложения. Пожалуйста, попробуйте снова.")
            return
        
        # Парсим JSON-данные
        data = json.loads(webapp_data)
        logger.debug(f"Распарсенные данные: {data}")
        
        message_id = data.get('messageId')
        # Преобразуем messageId в int, если это строка
        if isinstance(message_id, str):
            try:
                message_id = int(message_id)
                logger.debug(f"messageId преобразован из строки в число: {message_id}")
            except ValueError:
                logger.error(f"Не удалось преобразовать messageId '{message_id}' в число")
        
        selected_items = data.get('selectedItems', {})
        
        logger.debug(f"message_id: {message_id}, тип: {type(message_id)}")
        logger.debug(f"selected_items: {selected_items}, тип: {type(selected_items)}")
        logger.debug(f"Доступные message_states: {list(message_states.keys())}")
        
        if not message_id:
            logger.warning("messageId отсутствует в данных")
            await message.answer("❌ Не удалось обработать выбор: отсутствует идентификатор сообщения.")
            return
        
        if message_id not in message_states:
            # Попробуем преобразовать ключи message_states в строки для сравнения
            logger.debug(f"message_id {message_id} не найден напрямую, пробуем найти ключ по строковому представлению")
            str_keys = {str(k): k for k in message_states.keys()}
            logger.debug(f"Строковые ключи message_states: {str_keys}")
            
            if str(message_id) in str_keys:
                actual_key = str_keys[str(message_id)]
                logger.debug(f"Найден ключ {actual_key} по строковому представлению {message_id}")
                message_id = actual_key
            else:
                logger.warning(f"Не найдено состояние для message_id: {message_id}")
                logger.warning(f"Доступные ключи: {list(message_states.keys())}")
                await message.answer("❌ Не удалось обработать выбор из веб-приложения. Попробуйте еще раз.")
                return
        
        # Получаем данные из состояния
        message_data = message_states[message_id]
        logger.debug(f"Найдены данные для message_id {message_id}: {message_data.keys()}")
        
        # Получаем user_id
        user_id = message.from_user.id
        
        # Обновляем выбор пользователя
        if 'user_selections' not in message_data:
            message_data['user_selections'] = {}
        
        user_selections = message_data['user_selections']
        # Преобразуем строковые ключи в числа и убедимся, что значения тоже числа
        user_selections[user_id] = {int(idx): int(count) for idx, count in selected_items.items()}
        
        # Формируем сообщение с итогами
        user_mention = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.first_name}"
        summary = f"<b>✅ {user_mention}, ваш выбор подтвержден!</b>\n\n"
        summary += f"<b>📋 Выбранные позиции:</b>\n"
        
        items = message_data.get("items", [])
        service_charge_percent = message_data.get("service_charge_percent")
        actual_discount_percent = message_data.get("actual_discount_percent")
        total_discount_amount = message_data.get("total_discount_amount")
        
        # Расчет общей суммы всех позиций в чеке для распределения скидки
        total_check_sum = Decimal("0.00")
        for item in items:
            if item.get("total_amount_from_openai") is not None:
                total_check_sum += Decimal(str(item["total_amount_from_openai"]))
        
        # Считаем сумму выбранных товаров
        total_sum = Decimal("0.00")
        for idx_str, count in selected_items.items():
            idx = int(idx_str)
            if idx < len(items) and count > 0:
                item = items[idx]
                description = item.get("description", "N/A")
                
                # Определяем, является ли товар весовым
                is_weight_item = False
                openai_quantity = item.get("quantity_from_openai", 1)
                total_amount_openai = item.get("total_amount_from_openai")
                unit_price_openai = item.get("unit_price_from_openai")
                
                if openai_quantity == 1 and total_amount_openai is not None and unit_price_openai is not None:
                    price_diff = abs(Decimal(str(total_amount_openai)) - Decimal(str(unit_price_openai)))
                    is_weight_item = price_diff > Decimal("0.01")
                
                # Расчет стоимости
                if is_weight_item and total_amount_openai is not None:
                    item_total = Decimal(str(total_amount_openai))
                elif unit_price_openai is not None:
                    item_total = Decimal(str(unit_price_openai)) * Decimal(count)
                elif total_amount_openai is not None and openai_quantity > 0:
                    try:
                        unit_price = Decimal(str(total_amount_openai)) / Decimal(str(openai_quantity))
                        item_total = unit_price * Decimal(count)
                    except Exception:
                        item_total = Decimal(str(total_amount_openai))
                else:
                    continue
                
                # Добавляем позицию в итог с форматированной ценой за единицу
                total_sum += item_total
                unit_price_str = ""
                if unit_price_openai:
                    unit_price_str = f" (цена: {Decimal(str(unit_price_openai)):.2f})"
                    
                summary += f"• {description}: {count} шт.{unit_price_str} = <b>{item_total:.2f}</b>\n"
        
        # Добавляем разделитель
        summary += "\n<b>📊 Расчет итоговой суммы:</b>\n"
        summary += f"• Сумма выбранных позиций: <b>{total_sum:.2f}</b>\n"
        
        # Применяем скидку
        discount_applied = False
        if actual_discount_percent and actual_discount_percent > 0:
            discount_amount = (total_sum * Decimal(str(actual_discount_percent)) / Decimal("100")).quantize(Decimal("0.01"))
            total_sum -= discount_amount
            summary += f"• Скидка ({actual_discount_percent}%): <b>-{discount_amount:.2f}</b>\n"
            discount_applied = True
        elif total_discount_amount is not None and total_check_sum > 0:
            user_discount = (Decimal(str(total_discount_amount)) * total_sum / total_check_sum).quantize(Decimal("0.01"))
            total_sum -= user_discount
            summary += f"• Скидка: <b>-{user_discount:.2f}</b>\n"
            discount_applied = True
        
        # Добавляем информацию о сервисном сборе
        if service_charge_percent is not None:
            service_amount = (total_sum * Decimal(str(service_charge_percent)) / Decimal("100")).quantize(Decimal("0.01"))
            total_sum += service_amount
            summary += f"• Плата за обслуживание ({service_charge_percent}%): <b>+{service_amount:.2f}</b>\n"
        
        # Добавляем итоговую сумму
        summary += f"\n<b>💰 Итоговая сумма к оплате: {total_sum:.2f}</b>"
        
        # Добавляем полезную информацию
        summary += "\n\n<i>Спасибо за использование бота СплитЧек! Надеемся, это было полезно.</i>"
        
        # Отправляем итоговое сообщение в чат
        await message.answer(summary, parse_mode="HTML")
        
        # Очищаем состояние FSM
        await state.clear()
        
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при парсинге JSON из веб-приложения: {e}")
        await message.answer("❌ Ошибка при обработке данных из веб-приложения. Неверный формат данных.")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке данных из веб-приложения: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обработке данных из веб-приложения.") 