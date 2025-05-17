import logging
import aiohttp
import json
import asyncio
from decimal import Decimal
from aiogram import F, Router
from aiogram.types import Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.openai_service import process_receipt_with_openai
from utils.keyboards import create_items_keyboard_with_counters
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
    if not WEBAPP_URL:
        logger.warning("WEBAPP_URL не настроен, данные не будут сохранены в API")
        return False
    
    # Проверяем, что URL не содержит http://localhost
    if "http://localhost" in WEBAPP_URL or "http://127.0.0.1" in WEBAPP_URL:
        logger.warning("Использование localhost URL не поддерживается Telegram. Данные не будут сохранены в API.")
        return False
    
    try:
        # Очищаем URL от кавычек, если они есть
        clean_url = WEBAPP_URL.strip('"\'')
        
        # Сначала проверяем доступность API
        health_url = f"{clean_url}/health"
        logger.info(f"Проверка доступности API: {health_url}")
        
        # Устанавливаем таймаут для проверки
        timeout = aiohttp.ClientTimeout(total=5.0)
        
        # Попытка связаться с API
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.get(health_url) as health_response:
                        if health_response.status != 200:
                            logger.error(f"API недоступен, код ответа: {health_response.status}")
                            if health_response.status == 503:
                                logger.warning("Сервер API вернул 503 Service Unavailable. Возможно, сервер перегружен или не запущен.")
                            return False
                        
                        # Проверяем ответ
                        try:
                            health_data = await health_response.json()
                            if health_data.get("status") != "ok":
                                logger.error(f"API вернул некорректный статус: {health_data}")
                                return False
                            logger.info("API доступен, продолжаем с сохранением данных")
                        except Exception as json_err:
                            logger.error(f"Не удалось прочитать JSON ответа: {json_err}")
                            return False
                except aiohttp.ClientConnectorError as conn_err:
                    logger.error(f"Не удалось подключиться к API: {conn_err}")
                    return False
                except aiohttp.ClientError as client_err:
                    logger.error(f"Ошибка HTTP клиента: {client_err}")
                    return False
        except asyncio.TimeoutError:
            logger.error(f"Таймаут при проверке доступности API: {health_url}")
            return False
        
        # Если прошли проверку доступности, сохраняем данные
        api_url = f"{clean_url}/api/receipt/{message_id}"
        logger.info(f"Сохранение данных чека в API: {api_url}")
        
        # Преобразуем Decimal в строки для корректной сериализации в JSON
        serializable_data = {}
        for key, value in data.items():
            if key == "items":
                serializable_data[key] = []
                for item in value:
                    serializable_item = {}
                    for item_key, item_value in item.items():
                        if isinstance(item_value, Decimal):
                            serializable_item[item_key] = float(item_value)
                        else:
                            serializable_item[item_key] = item_value
                    serializable_data[key].append(serializable_item)
            elif isinstance(value, Decimal):
                serializable_data[key] = float(value)
            else:
                serializable_data[key] = value
        
        logger.debug(f"Сериализуемые данные для API: {json.dumps(serializable_data)[:500]}...")
        
        # Попытка отправки данных на API
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.post(api_url, json=serializable_data) as response:
                        if response.status == 200:
                            logger.info(f"Данные чека успешно сохранены в API для message_id: {message_id}")
                            return True
                        else:
                            error_text = await response.text()
                            logger.error(f"Ошибка при сохранении данных в API: {response.status}, {error_text}")
                            return False
                except aiohttp.ClientConnectorError as conn_err:
                    logger.error(f"Не удалось подключиться к API при отправке данных: {conn_err}")
                    return False
                except aiohttp.ClientError as client_err:
                    logger.error(f"Ошибка HTTP клиента при отправке данных: {client_err}")
                    return False
        except asyncio.TimeoutError:
            logger.error(f"Таймаут при отправке данных в API: {api_url}")
            return False
        except Exception as e:
            logger.error(f"Общая ошибка при сохранении данных в API: {e}", exc_info=True)
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в API: {e}", exc_info=True)
        return False

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
        
        # Сохраняем данные в глобальный словарь message_states
        receipt_data = {
            "items": items,
            "user_selections": {},  # Пустой словарь для выборов пользователей
            "service_charge_percent": service_charge,
            "total_check_amount": total_check_amount,
            "total_discount_percent": total_discount_percent,
            "total_discount_amount": total_discount_amount,
            "actual_discount_percent": actual_discount_percent,
        }
        
        # Сохраняем данные в API для веб-приложения
        message_id = processing_message.message_id
        api_saved = await save_receipt_data_to_api(message_id, receipt_data)
        
        # Проверяем WEBAPP_URL перед созданием клавиатуры
        webapp_enabled = False
        if WEBAPP_URL and not ("http://localhost" in WEBAPP_URL or "http://127.0.0.1" in WEBAPP_URL):
            # Пробуем сохранить данные в API и проверяем доступность
            api_saved = await save_receipt_data_to_api(message_id, receipt_data)
            # Только если API доступен, включаем WebApp
            webapp_enabled = api_saved
        else:
            api_saved = False
        
        # Создаем клавиатуру и отправляем сообщение, обрабатывая возможные ошибки
        try:
            # Создаем клавиатуру в зависимости от доступности WebApp
            if webapp_enabled:
                logger.info("Создаем клавиатуру с WebApp кнопкой")
                keyboard = create_items_keyboard_with_counters(items, empty_user_counts, message_id=message_id, chat_type=message.chat.type)
                webapp_info = "\n\n<i>💻 Доступно в веб-приложении</i>"
            else:
                logger.info("Создаем клавиатуру без WebApp кнопки")
                keyboard = create_items_keyboard_with_counters(items, empty_user_counts, chat_type=message.chat.type)
                webapp_info = "\n\n<i>⚠️ Веб-приложение временно недоступно, используйте кнопки ниже</i>" if WEBAPP_URL else ""
            
            # Отправляем сообщение с информацией о чеке и клавиатурой
            result_message = await processing_message.edit_text(
                response_msg_text + webapp_info,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Сохраняем данные в глобальный словарь message_states
            message_states[result_message.message_id] = receipt_data
            
            # Устанавливаем состояние ожидания выбора товаров
            await state.set_state(ReceiptStates.waiting_for_items_selection)
            logger.info("Состояние установлено: waiting_for_items_selection")
            
        except Exception as keyboard_error:
            logger.error(f"Ошибка при создании клавиатуры или отправке сообщения: {keyboard_error}", exc_info=True)
            
            # Пробуем создать простую клавиатуру без WebApp и отправить ее
            try:
                # Создаем простую клавиатуру только с кнопкой подтверждения
                simple_keyboard = InlineKeyboardBuilder()
                for idx, item in enumerate(items):
                    description = item.get("description", "N/A")[:25]
                    simple_keyboard.row(InlineKeyboardButton(text=f"{description}", callback_data=f"increment_item:{idx}"))
                
                simple_keyboard.row(InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="confirm_selection"))
                
                # Повторно отправляем сообщение с простой клавиатурой
                logger.info("Пробуем отправить сообщение с простой клавиатурой после ошибки")
                result_message = await processing_message.edit_text(
                    response_msg_text + "\n\n<i>⚠️ Упрощенный режим из-за ограничений чата</i>",
                    reply_markup=simple_keyboard.as_markup(),
                    parse_mode="HTML"
                )
                
                # Сохраняем данные в глобальный словарь message_states
                message_states[result_message.message_id] = receipt_data
                
                # Устанавливаем состояние ожидания выбора товаров
                await state.set_state(ReceiptStates.waiting_for_items_selection)
                logger.info("Состояние установлено в упрощенном режиме: waiting_for_items_selection")
                
            except Exception as simple_error:
                logger.error(f"Критическая ошибка при создании простой клавиатуры: {simple_error}", exc_info=True)
                await processing_message.edit_text(
                    "❌ Возникла ошибка при создании интерфейса. Пожалуйста, используйте личный чат с ботом @Splitix_bot"
                )
                await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}", exc_info=True)
        # Проверяем тип ошибки и улучшаем сообщение
        if "Web App URL" in str(e) and "invalid" in str(e):
            await message.answer("❌ Ошибка при создании веб-интерфейса. Пожалуйста, обратитесь к администратору бота.")
        elif "aiogram.exceptions" in str(e.__class__):
            await message.answer("❌ Ошибка в Telegram API. Пожалуйста, попробуйте еще раз позже.")
        else:
            await message.answer("❌ Произошла ошибка при обработке чека. Пожалуйста, попробуйте еще раз.")
        
        # Логируем детальную информацию о чате для отладки
        chat_id = message.chat.id
        chat_type = message.chat.type
        logger.error(f"Контекст ошибки: chat_id={chat_id}, chat_type={chat_type}")
        
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
            # В групповых чатах отправляем подсказку вместо игнорирования
            await message.answer(
                "Чтобы я обработал фото чека в группе, сначала используйте команду /split\n"
                "Это нужно, чтобы я не реагировал на все фотографии в группе."
            ) 