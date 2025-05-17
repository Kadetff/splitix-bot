import logging
from aiogram import Router, F
from aiogram.types import Message, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from handlers.photo import ReceiptStates
from config.settings import WEBAPP_URL

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    # Проверяем наличие параметров в команде start
    command_parts = message.text.split()
    if len(command_parts) > 1 and command_parts[1].startswith("webapp_"):
        # Извлекаем message_id из параметра
        try:
            receipt_message_id = int(command_parts[1].replace("webapp_", ""))
            logger.info(f"Получен запрос на открытие WebApp с message_id={receipt_message_id}")
            
            # Проверяем, что URL веб-приложения установлен и не локальный
            if not WEBAPP_URL or "http://localhost" in WEBAPP_URL or "http://127.0.0.1" in WEBAPP_URL:
                await message.answer(
                    "⚠️ Веб-приложение временно недоступно.\n\n"
                    "Пожалуйста, попробуйте позже или используйте основной функционал бота через отправку фото чека."
                )
                return
                
            # Создаем ReplyKeyboardMarkup с WebApp кнопкой
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [
                        KeyboardButton(
                            text="🌐 Открыть мини-приложение SplitCheck", 
                            web_app=WebAppInfo(url=f"{WEBAPP_URL}/{receipt_message_id}")
                        )
                    ]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await message.answer(
                "🌐 Нажмите на кнопку ниже, чтобы открыть мини-приложение SplitCheck с данными распознанного чека:",
                reply_markup=keyboard
            )
            return
            
        except (ValueError, Exception) as e:
            logger.error(f"Ошибка при обработке параметра webapp: {e}", exc_info=True)
    
    # Стандартное приветствие, если нет специальных параметров
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
    """Команда для открытия веб-приложения"""
    try:
        # Проверяем, что URL веб-приложения установлен и не локальный
        if not WEBAPP_URL or "http://localhost" in WEBAPP_URL or "http://127.0.0.1" in WEBAPP_URL:
            await message.answer(
                "⚠️ Веб-приложение временно недоступно.\n\n"
                "Пожалуйста, попробуйте позже или используйте основной функционал бота через отправку фото чека."
            )
            return
        
        # Проверяем тип чата - WebApp кнопки можно использовать только в личных чатах
        if message.chat.type == ChatType.PRIVATE:
            # Создаем клавиатуру с WebApp кнопкой
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [
                        KeyboardButton(
                            text="🌐 Открыть мини-приложение SplitCheck", 
                            web_app=WebAppInfo(url=WEBAPP_URL)
                        )
                    ]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await message.answer(
                "Нажмите на кнопку ниже, чтобы открыть мини-приложение SplitCheck прямо в Telegram:",
                reply_markup=keyboard
            )
        else:
            # Для групповых чатов отправляем инструкцию
            bot_username = (await message.bot.get_me()).username
            
            await message.answer(
                f"⚠️ К сожалению, Telegram не позволяет открывать мини-приложения из групповых чатов.\n\n"
                f"Для использования мини-приложения, пожалуйста, выполните одно из следующих действий:\n\n"
                f"1️⃣ Перейдите в личный чат с ботом: @{bot_username}\n"
                f"2️⃣ Или используйте команду /split прямо здесь для распознавания чека\n\n"
                f"Ограничение связано с API Telegram и не может быть обойдено."
            )
        
    except Exception as e:
        logger.error(f"Ошибка при создании WebApp кнопки: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при создании интерфейса мини-приложения.\n\n"
            "Пожалуйста, попробуйте использовать основной функционал через отправку фото чека."
        ) 