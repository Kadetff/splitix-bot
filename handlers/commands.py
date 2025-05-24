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