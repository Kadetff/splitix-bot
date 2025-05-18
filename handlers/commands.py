import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from handlers.photo import ReceiptStates

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
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
    await message.answer(
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

@router.message(Command("split"))
async def cmd_split(message: Message, state: FSMContext):
    """Обработчик команды /split"""
    await state.set_state(ReceiptStates.waiting_for_photo)
    await message.answer("📸 Пожалуйста, пришлите фото чека.") 