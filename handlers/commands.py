import logging
import os
from aiogram import Router
from aiogram.types import Message, InlineKeyboardButton, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from handlers.photo import ReceiptStates
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config.settings import WEBAPP_URL, TELEGRAM_BOT_TOKEN, ENABLE_TEST_COMMANDS
from utils.keyboards import create_test_webapp_inline_keyboard, create_test_webapp_reply_keyboard

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
    """Обработчик команды /start"""
    # Проверяем, есть ли параметр receipt_id
    command_args = message.text.split()
    if len(command_args) > 1 and command_args[1].startswith("receipt_"):
        # Извлекаем message_id из параметра
        try:
            receipt_param = command_args[1]  # receipt_123
            message_id = int(receipt_param.split("_")[1])
            
            # Импортируем message_states для проверки существования чека
            from handlers.photo import message_states
            
            if message_id in message_states:
                # Создаем кнопку Mini App для конкретного чека
                clean_url = WEBAPP_URL.strip('"\'')
                webapp_url = f"{clean_url}/app/{message_id}"
                
                builder = InlineKeyboardBuilder()
                webapp_button = InlineKeyboardButton(
                    text="🚀 Открыть Mini App",
                    web_app=WebAppInfo(url=webapp_url)
                )
                builder.row(webapp_button)
                
                await message.answer(
                    "📋 Открываю чек для выбора позиций.\n\n"
                    "👆 Нажмите кнопку выше, чтобы открыть Mini App и выбрать свои позиции из чека.",
                    reply_markup=builder.as_markup()
                )
                return
            else:
                await message.answer(
                    "❌ Чек не найден или устарел.\n\n"
                    "Возможно, данные чека были удалены или ссылка неактуальна."
                )
                return
                
        except (ValueError, IndexError) as e:
            logger.error(f"Ошибка парсинга параметра receipt: {e}")
            # Продолжаем с обычным приветствием
    
    # Обычное приветствие без параметров
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

# Тестовые команды (доступны только в dev/staging окружениях)
if ENABLE_TEST_COMMANDS:
    @router.message(Command("testbothwebapp"))
    async def cmd_test_both_webapp(message: Message):
        """Тестирует WebApp с обеими типами клавиатур: Inline и Reply."""
        logger.info("Команда /testbothwebapp получена")
        
        if not WEBAPP_URL:
            await message.answer("❌ Ошибка: URL веб-приложения не настроен в конфигурации.")
            logger.error("WEBAPP_URL не настроен")
            return

        # URL для тестового WebApp
        test_webapp_url = f"{WEBAPP_URL}/test_webapp"
        
        logger.info(f"Тестируем оба типа клавиатур для WebApp: {test_webapp_url}")

        # Отправляем сообщение с Inline-клавиатурой
        await message.answer(
            "🧪 **Тест #1: Inline-клавиатура с WebApp**\n\n"
            "Нажмите кнопку ниже, чтобы открыть WebApp через Inline-кнопку:",
            reply_markup=create_test_webapp_inline_keyboard(test_webapp_url),
            parse_mode="Markdown"
        )
        
        # Отправляем сообщение с Reply-клавиатурой
        await message.answer(
            "🧪 **Тест #2: Reply-клавиатура с WebApp**\n\n"
            "Используйте кнопку в нижней части экрана для открытия WebApp:",
            reply_markup=create_test_webapp_reply_keyboard(test_webapp_url),
            parse_mode="Markdown"
        )
        
        # Информационное сообщение
        info_message = (
            "📋 **Инструкция по тестированию:**\n\n"
            "1. 🔵 **Inline-кнопка** - кнопка в сообщении выше\n"
            "2. 🟢 **Reply-кнопка** - кнопка в нижней клавиатуре\n\n"
            "🎯 **Что тестируем:**\n"
            "• Отправку данных из обеих типов WebApp\n"
            "• Определение источника кнопки (Inline/Reply)\n"
            "• Обработку различных форматов данных\n\n"
            "💡 В WebApp попробуйте отправить простое сообщение 'Привет' или JSON-данные"
        )
        
        await message.answer(info_message, parse_mode="Markdown")

@router.message(lambda message: message.text == "🔙 Убрать клавиатуру")
async def remove_keyboard(message: Message):
    """Убирает Reply-клавиатуру."""
    await message.answer(
        "✅ Клавиатура убрана.",
        reply_markup=ReplyKeyboardRemove()
    ) 