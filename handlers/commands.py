import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from handlers.photo import ReceiptStates

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
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
    # Определяем тип чата
    is_private_chat = message.chat.type == ChatType.PRIVATE
    
    await state.set_state(ReceiptStates.waiting_for_photo)
    
    if is_private_chat:
        await message.answer("Пожалуйста, пришлите фото чека.")
    else:
        # Для групповых чатов даем более подробную инструкцию и запрашиваем права
        await message.answer(
            "✅ Бот настроен на прием фото чека в этой группе.\n\n"
            "📸 Отправьте фото чека следующим сообщением.\n\n"
            "⚠️ Для корректной работы в группе убедитесь, что:\n"
            "1. Бот имеет права администратора\n"
            "2. Включено право на отправку ссылок\n"
            "3. Бот может использовать веб-приложения\n\n"
            "💡 Совет: для полной функциональности лучше использовать личный чат с ботом @Splitix_bot"
        )

@router.message(Command("webapp"))
async def cmd_webapp(message: Message):
    """Информация о веб-приложении"""
    await message.answer(
        "🌐 Веб-приложение для разделения чеков\n\n"
        "Вы можете использовать веб-интерфейс для более удобного выбора позиций из чека.\n\n"
        "После распознавания чека, нажмите на кнопку '🌐 Открыть в веб-интерфейсе' под списком товаров.\n\n"
        "В веб-интерфейсе вы сможете:\n"
        "• Быстро выбирать товары с помощью кнопок + и -\n"
        "• Видеть итоговую сумму в реальном времени\n"
        "• Подтвердить свой выбор\n\n"
        "После подтверждения выбора в веб-интерфейсе, результат будет отправлен в чат."
    ) 