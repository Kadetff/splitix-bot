import logging
import os
from aiogram import Router
from aiogram.types import Message, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from handlers.photo import ReceiptStates
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config.settings import WEBAPP_URL, TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)
router = Router()

HELP_TEXT = (
    "📚 Как пользоваться ботом:\n\n"
    "1. 📸 Отправь фото чека\n"
    "2. 🔍 Я распознаю товары и цены\n"
    "3. ✅ Выбери товары, которые ты хочешь добавить в свой счет\n"
    "4. 💰 Я посчитаю твою часть\n\n"
    "💡 Советы:\n"
    "• Убедись, что фото чека четкое и хорошо освещенное\n"
    "• Чек должен быть полностью виден на фото\n"
    "• Если распознавание не удалось, попробуй отправить фото еще раз\n\n"
    "❓ Если у тебя есть вопросы, используй команду /start для начала работы"
)

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start с поддержкой параметра webapp"""
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("webapp_"):
        message_id = args[1].replace("webapp_", "")
        webapp_url = f"{WEBAPP_URL}/{message_id}"
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(
                text="🌐 Открыть мини-приложение",
                web_app=WebAppInfo(url=webapp_url)
            )
        )
        await message.answer(
            "Нажмите кнопку ниже, чтобы открыть мини-приложение:",
            reply_markup=keyboard.as_markup()
        )
        return
    await message.answer(
        "👋 Привет! Я бот для разделения чеков.\n\n"
        "📸 Отправь мне фото чека, и я помогу разделить его между участниками.\n\n"
        "🔍 Я могу распознавать:\n"
        "• Названия товаров\n"
        "• Цены\n"
        "• Количество\n"
        "• Скидки\n"
        "• Плату за обслуживание\n\n"
        "💡 Просто отправь мне фото чека, и я помогу тебе разделить его!"
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    await message.answer(HELP_TEXT)

@router.message(Command("split"))
async def cmd_split(message: Message, state: FSMContext):
    """Обработчик команды /split"""
    await state.set_state(ReceiptStates.waiting_for_photo)
    await message.answer("📸 Пожалуйста, пришлите фото чека.")

@router.message(Command("testwebapp"))
async def cmd_test_webapp(message: Message):
    """Отправляет кнопку для открытия тестового WebApp."""
    logger.critical(f"!!!! КОМАНДА /testwebapp ПОЛУЧЕНА !!!! WEBAPP_URL: {WEBAPP_URL}")
    
    if not WEBAPP_URL:
        await message.answer("❌ Ошибка: URL веб-приложения не настроен в конфигурации.")
        logger.error("WEBAPP_URL не настроен, не могу открыть тестовый WebApp.")
        return

    # URL для тестового WebApp будет WEBAPP_URL + '/test_webapp'
    # Важно: WEBAPP_URL должен быть базовым URL (например, https://yourdomain.com)
    # без завершающего слеша, если вы его так используете, или с ним, если ваш Flask настроен ожидать его.
    # В текущей реализации server.py (маршрут /test_webapp) он ожидает, что WEBAPP_URL не имеет слеша на конце.
    test_webapp_url = f"{WEBAPP_URL}/test_webapp"
    
    logger.info(f"Формирую кнопку для тестового WebApp: {test_webapp_url}")

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(
            text="🧪 Открыть тестовый WebApp",
            web_app=WebAppInfo(url=test_webapp_url)
        )
    )
    await message.answer(
        "Нажмите кнопку ниже, чтобы открыть тестовое веб-приложение для отладки.",
        reply_markup=keyboard.as_markup()
    )

@router.message(Command("webhook"))
async def cmd_webhook_info(message: Message):
    """Проверяет статус webhook."""
    try:
        webhook_info = await message.bot.get_webhook_info()
        logger.critical(f"!!!! WEBHOOK INFO !!!! {webhook_info}")
        
        status = "✅ Активен" if webhook_info.url else "❌ Не настроен"
        
        response = f"🔗 **Статус Webhook**: {status}\n"
        response += f"📡 **URL**: `{webhook_info.url or 'Не установлен'}`\n"
        response += f"🔢 **Pending updates**: {webhook_info.pending_update_count}\n"
        response += f"📅 **Последняя ошибка**: {webhook_info.last_error_date or 'Нет'}\n"
        response += f"🔧 **Allowed updates**: {webhook_info.allowed_updates}\n"
        
        if webhook_info.last_error_message:
            response += f"⚠️ **Сообщение об ошибке**: {webhook_info.last_error_message}\n"
            
        await message.answer(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о webhook: {e}")
        await message.answer(f"❌ Ошибка при получении информации о webhook: {e}")

@router.message(Command("fixwebhook"))
async def cmd_fix_webhook(message: Message):
    """Принудительно обновляет настройки webhook с поддержкой web_app_data."""
    try:
        # Сначала получаем текущий URL webhook чтобы использовать точно такой же
        current_webhook = await message.bot.get_webhook_info()
        if current_webhook.url:
            WEBHOOK_URL = current_webhook.url
            logger.critical(f"!!!! ИСПОЛЬЗУЕМ ТЕКУЩИЙ WEBHOOK URL: {WEBHOOK_URL} !!!!")
        else:
            # Fallback: определяем webhook URL как в main.py
            APP_NAME = os.getenv('HEROKU_APP_NAME') or os.getenv('APP_NAME') or 'splitix-bot-69642ff6c071'
            WEBHOOK_HOST = f"https://{APP_NAME}.herokuapp.com"
            WEBHOOK_PATH = f"/bot/{TELEGRAM_BOT_TOKEN}"
            WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
            logger.critical(f"!!!! WEBHOOK НЕ УСТАНОВЛЕН, СОЗДАЕМ НОВЫЙ: {WEBHOOK_URL} !!!!")
        
        await message.answer("🔧 Обновляю настройки webhook...")
        logger.critical(f"!!!! ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ WEBHOOK: {WEBHOOK_URL} !!!!")
        
        # Принудительно устанавливаем webhook с правильными настройками
        await message.bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=["message", "callback_query", "inline_query", "chosen_inline_result", "web_app_data"]
        )
        
        logger.critical("!!!! WEBHOOK ОБНОВЛЕН ПРИНУДИТЕЛЬНО !!!!")
        
        # Проверяем результат
        webhook_info = await message.bot.get_webhook_info()
        logger.critical(f"!!!! НОВЫЕ НАСТРОЙКИ WEBHOOK !!!! {webhook_info}")
        
        response = "✅ **Webhook обновлен!**\n\n"
        response += f"📡 **URL**: `{webhook_info.url}`\n"
        response += f"🔧 **Allowed updates**: {webhook_info.allowed_updates}\n"
        
        # Проверяем наличие web_app_data
        if 'web_app_data' in webhook_info.allowed_updates:
            response += "\n🎉 **web_app_data включен!** Теперь WebApp должен работать."
        else:
            response += "\n❌ **web_app_data все еще отсутствует!** Возможна проблема с настройками."
            
        await message.answer(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении webhook: {e}")
        await message.answer(f"❌ Ошибка при обновлении webhook: {e}")

@router.message(Command("resetwebhook"))
async def cmd_reset_webhook(message: Message):
    """Полный сброс webhook: удаление + повторная установка с web_app_data."""
    try:
        await message.answer("🔥 Выполняю полный сброс webhook...")
        
        # Шаг 1: Удаляем существующий webhook
        logger.critical("!!!! ШАГ 1: УДАЛЕНИЕ WEBHOOK !!!!")
        await message.bot.delete_webhook()
        await message.answer("✅ Webhook удален")
        
        # Шаг 2: Ждем немного
        import asyncio
        await asyncio.sleep(1)
        
        # Шаг 3: Получаем правильный URL
        # Попробуем разные варианты URL
        possible_urls = [
            "https://splitix-bot-69642ff6c071.herokuapp.com",
            "https://splitix-bot.herokuapp.com"
        ]
        
        for base_url in possible_urls:
            try:
                WEBHOOK_URL = f"{base_url}/bot/{TELEGRAM_BOT_TOKEN}"
                logger.critical(f"!!!! ПРОБУЕМ УСТАНОВИТЬ WEBHOOK: {WEBHOOK_URL} !!!!")
                
                # Устанавливаем webhook с web_app_data
                result = await message.bot.set_webhook(
                    url=WEBHOOK_URL,
                    allowed_updates=["message", "callback_query", "inline_query", "chosen_inline_result", "web_app_data"]
                )
                
                logger.critical(f"!!!! РЕЗУЛЬТАТ set_webhook: {result} !!!!")
                
                # Проверяем результат
                webhook_info = await message.bot.get_webhook_info()
                logger.critical(f"!!!! ПРОВЕРКА ПОСЛЕ УСТАНОВКИ: {webhook_info} !!!!")
                
                if webhook_info.url == WEBHOOK_URL:
                    # Успешно установлен на этот URL
                    response = f"✅ **Webhook переустановлен!**\n\n"
                    response += f"📡 **URL**: `{webhook_info.url}`\n"
                    response += f"🔧 **Allowed updates**: {webhook_info.allowed_updates}\n"
                    
                    if 'web_app_data' in webhook_info.allowed_updates:
                        response += "\n🎉 **УСПЕХ! web_app_data включен!**"
                    else:
                        response += "\n❌ **web_app_data все еще отсутствует...**"
                        
                    await message.answer(response, parse_mode="Markdown")
                    return
                    
            except Exception as url_error:
                logger.error(f"Ошибка с URL {base_url}: {url_error}")
                continue
        
        # Если ни один URL не сработал
        await message.answer("❌ Не удалось установить webhook ни на один из URL")
        
    except Exception as e:
        logger.error(f"Ошибка при сбросе webhook: {e}")
        await message.answer(f"❌ Ошибка при сбросе webhook: {e}")

@router.message(Command("diagwebhook"))
async def cmd_diag_webhook(message: Message):
    """Детальная диагностика webhook и попытка понять почему web_app_data не работает."""
    try:
        await message.answer("🔍 Запускаю детальную диагностику...")
        
        # Получаем информацию о боте
        me = await message.bot.get_me()
        logger.critical(f"!!!! BOT INFO: {me} !!!!")
        
        # Проверяем текущий webhook
        webhook_info = await message.bot.get_webhook_info()
        logger.critical(f"!!!! CURRENT WEBHOOK: {webhook_info} !!!!")
        
        # Пробуем установить webhook ТОЛЬКО с web_app_data для теста
        test_url = webhook_info.url if webhook_info.url else f"https://splitix-bot-69642ff6c071.herokuapp.com/bot/{TELEGRAM_BOT_TOKEN}"
        
        logger.critical(f"!!!! ТЕСТ: УСТАНОВКА WEBHOOK ТОЛЬКО С web_app_data !!!!")
        try:
            result = await message.bot.set_webhook(
                url=test_url,
                allowed_updates=["web_app_data"]  # ТОЛЬКО web_app_data
            )
            logger.critical(f"!!!! РЕЗУЛЬТАТ ТЕСТА: {result} !!!!")
            
            # Проверяем что получилось
            test_webhook = await message.bot.get_webhook_info()
            logger.critical(f"!!!! ТЕСТОВЫЙ WEBHOOK: {test_webhook} !!!!")
            
            response = "🧪 **Тест с only web_app_data:**\n"
            response += f"Результат: `{result}`\n"
            response += f"Allowed updates: `{test_webhook.allowed_updates}`\n\n"
            
            # Возвращаем обратно полный набор
            await message.bot.set_webhook(
                url=test_url,
                allowed_updates=["message", "callback_query", "inline_query", "chosen_inline_result", "web_app_data"]
            )
            
            final_webhook = await message.bot.get_webhook_info()
            response += f"🔄 **После возврата полного набора:**\n"
            response += f"Allowed updates: `{final_webhook.allowed_updates}`\n"
            
            await message.answer(response, parse_mode="Markdown")
            
        except Exception as test_error:
            logger.error(f"Ошибка в тесте: {test_error}")
            await message.answer(f"❌ Ошибка в тесте: {test_error}")
        
    except Exception as e:
        logger.error(f"Ошибка в диагностике: {e}")
        await message.answer(f"❌ Ошибка в диагностике: {e}")

@router.message(Command("safewebhook"))
async def cmd_safe_webhook(message: Message):
    """Осторожная установка webhook с учетом rate limiting."""
    try:
        # Сначала проверяем текущий статус
        webhook_info = await message.bot.get_webhook_info()
        
        response = "🔍 **Текущий статус:**\n"
        response += f"URL: `{webhook_info.url}`\n"
        response += f"Allowed updates: `{webhook_info.allowed_updates}`\n\n"
        
        # Если web_app_data уже есть - не трогаем
        if 'web_app_data' in webhook_info.allowed_updates:
            response += "✅ **web_app_data уже включен!** Ничего менять не нужно."
            await message.answer(response, parse_mode="Markdown")
            return
        
        response += "⚠️ **web_app_data отсутствует**\n\n"
        response += "🎯 **ОДИН** осторожный запрос на изменение webhook...\n"
        
        await message.answer(response, parse_mode="Markdown")
        
        # ОДИН запрос с правильными настройками
        logger.critical("!!!! ОСТОРОЖНАЯ УСТАНОВКА WEBHOOK !!!!")
        
        try:
            result = await message.bot.set_webhook(
                url=webhook_info.url,  # Используем существующий URL
                allowed_updates=["message", "callback_query", "inline_query", "chosen_inline_result", "web_app_data"]
            )
            logger.critical(f"!!!! РЕЗУЛЬТАТ ОСТОРОЖНОЙ УСТАНОВКИ: {result} !!!!")
            
            # Проверяем результат
            import asyncio
            await asyncio.sleep(2)  # Ждем 2 секунды
            
            new_webhook = await message.bot.get_webhook_info()
            logger.critical(f"!!!! НОВЫЙ WEBHOOK ПОСЛЕ ОСТОРОЖНОЙ УСТАНОВКИ: {new_webhook} !!!!")
            
            final_response = "✅ **Результат осторожной установки:**\n"
            final_response += f"Allowed updates: `{new_webhook.allowed_updates}`\n\n"
            
            if 'web_app_data' in new_webhook.allowed_updates:
                final_response += "🎉 **УСПЕХ! web_app_data включен!**\n\n"
                final_response += "Теперь можно тестировать WebApp!"
            else:
                final_response += "❌ **web_app_data все еще отсутствует**\n\n"
                final_response += "Возможно, есть другие ограничения Telegram API."
            
            await message.answer(final_response, parse_mode="Markdown")
            
        except Exception as webhook_error:
            error_message = str(webhook_error)
            logger.error(f"Ошибка при установке webhook: {error_message}")
            
            if "flood control" in error_message.lower() or "too many requests" in error_message.lower():
                await message.answer(
                    "🚫 **Flood control активен**\n\n"
                    "Telegram временно заблокировал изменения webhook.\n"
                    "Подождите 10-15 минут и попробуйте снова.\n\n"
                    "❗ НЕ запускайте команды изменения webhook повторно!"
                )
            else:
                await message.answer(f"❌ Ошибка: {error_message}")
        
    except Exception as e:
        logger.error(f"Ошибка в осторожной установке: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("testwebappdata"))
async def cmd_test_web_app_data(message: Message):
    """Расширенная диагностика проблемы с web_app_data."""
    try:
        await message.answer("🔬 **Проведение точной диагностики web_app_data...**")
        
        # Получаем текущий webhook
        webhook_info = await message.bot.get_webhook_info()
        logger.critical(f"!!!! ТОЧНАЯ ДИАГНОСТИКА: {webhook_info} !!!!")
        
        # Проверяем разные варианты написания
        possible_names = [
            "web_app_data",
            "webapp_data", 
            "webAppData",
            "web-app-data"
        ]
        
        response = "🔍 **Диагностика web_app_data:**\n\n"
        response += f"📡 URL: `{webhook_info.url}`\n"
        
        # Безопасная проверка allowed_updates
        allowed_updates = webhook_info.allowed_updates or []
        response += f"🔧 Allowed updates: `{allowed_updates}`\n"
        
        if webhook_info.allowed_updates is None:
            response += "⚠️ **ВАЖНО: allowed_updates = None** (получаем все типы обновлений по умолчанию)\n\n"
        else:
            response += f"📊 Количество типов обновлений: {len(allowed_updates)}\n\n"
        
        # Проверяем каждый вариант
        found_variants = []
        for variant in possible_names:
            if variant in allowed_updates:
                found_variants.append(variant)
        
        if found_variants:
            response += f"✅ **Найдены варианты:** `{found_variants}`\n\n"
        else:
            response += "❌ **Не найдено ни одного варианта web_app_data**\n\n"
        
        # Пробуем разные стратегии установки
        response += "🧪 **Тестирование разных стратегий:**\n\n"
        
        try:
            # Стратегия 1: Только web_app_data
            logger.critical("!!!! ТЕСТ 1: ТОЛЬКО web_app_data !!!!")
            result1 = await message.bot.set_webhook(
                url=webhook_info.url,
                allowed_updates=["web_app_data"]
            )
            
            # Проверяем результат
            import asyncio
            await asyncio.sleep(1)
            test1_webhook = await message.bot.get_webhook_info()
            test1_updates = test1_webhook.allowed_updates or []
            
            if 'web_app_data' in test1_updates:
                response += "✅ **Тест 1 (только web_app_data): УСПЕХ**\n"
            else:
                response += f"❌ **Тест 1: НЕУСПЕХ** - получили: `{test1_updates}`\n"
            
            # Стратегия 2: Полный список с web_app_data в разных позициях
            logger.critical("!!!! ТЕСТ 2: web_app_data В НАЧАЛЕ !!!!")
            result2 = await message.bot.set_webhook(
                url=webhook_info.url,
                allowed_updates=["web_app_data", "message", "callback_query", "inline_query", "chosen_inline_result"]
            )
            
            await asyncio.sleep(1)
            test2_webhook = await message.bot.get_webhook_info()
            test2_updates = test2_webhook.allowed_updates or []
            
            if 'web_app_data' in test2_updates:
                response += "✅ **Тест 2 (web_app_data первым): УСПЕХ**\n"
            else:
                response += f"❌ **Тест 2: НЕУСПЕХ** - получили: `{test2_updates}`\n"
            
            # Стратегия 3: Попробуем None (по умолчанию все типы)
            logger.critical("!!!! ТЕСТ 3: allowed_updates=None (все типы) !!!!")
            result3 = await message.bot.set_webhook(
                url=webhook_info.url,
                allowed_updates=None  # Все типы обновлений
            )
            
            await asyncio.sleep(1)
            test3_webhook = await message.bot.get_webhook_info()
            test3_updates = test3_webhook.allowed_updates or []
            
            if test3_webhook.allowed_updates is None:
                response += "✅ **Тест 3 (allowed_updates=None): УСПЕХ** - получаем все типы\n"
            else:
                response += f"❌ **Тест 3: НЕУСПЕХ** - получили: `{test3_updates}`\n"
            
            # Стратегия 4: Возвращаем стандартную конфигурацию
            logger.critical("!!!! ВОЗВРАТ К СТАНДАРТНОЙ КОНФИГУРАЦИИ !!!!")
            await message.bot.set_webhook(
                url=webhook_info.url,
                allowed_updates=["message", "callback_query", "inline_query", "chosen_inline_result", "web_app_data"]
            )
            
            await asyncio.sleep(1)
            final_webhook = await message.bot.get_webhook_info()
            final_updates = final_webhook.allowed_updates or []
            
            response += f"\n🔄 **Финальная конфигурация:** `{final_updates}`\n\n"
            
            if final_webhook.allowed_updates is None:
                response += "🎉 **ИТОГ: allowed_updates=None (ВСЕ типы включены)!**\n\n"
                response += "Это означает, что web_app_data должен работать!"
            elif 'web_app_data' in final_updates:
                response += "🎉 **ИТОГ: web_app_data ВКЛЮЧЕН!**\n\n"
                response += "Теперь попробуйте отправить данные из WebApp."
            else:
                response += "❌ **ИТОГ: web_app_data НЕ ВКЛЮЧЕН**\n\n"
                response += "Возможно, есть ограничения Telegram API или проблемы с конфигурацией."
            
            await message.answer(response, parse_mode="Markdown")
            
        except Exception as test_error:
            error_msg = str(test_error)
            logger.error(f"Ошибка в тестах: {error_msg}")
            await message.answer(f"❌ **Ошибка в тестах:** `{error_msg}`", parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Ошибка в диагностике: {e}")
        await message.answer(f"❌ Ошибка в диагностике: {e}")

@router.message(Command("setallwebhook"))
async def cmd_set_all_webhook(message: Message):
    """Устанавливает webhook с allowed_updates=None (все типы обновлений)."""
    try:
        # Получаем текущий webhook
        webhook_info = await message.bot.get_webhook_info()
        
        if not webhook_info.url:
            await message.answer("❌ **Ошибка:** Webhook URL не настроен. Сначала установите webhook.")
            return
        
        await message.answer("🌐 **Установка webhook с получением ВСЕХ типов обновлений...**")
        
        logger.critical("!!!! УСТАНОВКА WEBHOOK С allowed_updates=None !!!!")
        
        # Устанавливаем webhook с allowed_updates=None
        result = await message.bot.set_webhook(
            url=webhook_info.url,
            allowed_updates=None  # Получаем ВСЕ типы обновлений
        )
        
        logger.critical(f"!!!! РЕЗУЛЬТАТ установки с None: {result} !!!!")
        
        # Проверяем результат
        import asyncio
        await asyncio.sleep(2)
        
        new_webhook = await message.bot.get_webhook_info()
        logger.critical(f"!!!! НОВЫЙ WEBHOOK с None: {new_webhook} !!!!")
        
        response = "✅ **Webhook установлен с получением всех типов обновлений!**\n\n"
        response += f"📡 **URL**: `{new_webhook.url}`\n"
        
        if new_webhook.allowed_updates is None:
            response += "🔧 **Allowed updates**: `None` (все типы)\n\n"
            response += "🎉 **УСПЕХ!** Теперь бот получает все типы обновлений, включая web_app_data!\n\n"
            response += "Попробуйте отправить данные из WebApp командой `/testwebapp`"
        else:
            response += f"🔧 **Allowed updates**: `{new_webhook.allowed_updates}`\n\n"
            response += "⚠️ Telegram API вернул конкретный список вместо None."
        
        await message.answer(response, parse_mode="Markdown")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при установке webhook с None: {error_msg}")
        await message.answer(f"❌ **Ошибка**: `{error_msg}`", parse_mode="Markdown") 