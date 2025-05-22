import logging
from aiogram import Router
from aiogram.types import Message, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from handlers.photo import ReceiptStates
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config.settings import WEBAPP_URL

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