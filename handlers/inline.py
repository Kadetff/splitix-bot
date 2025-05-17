import logging
from aiogram import Router, F
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from uuid import uuid4
from config.settings import WEBAPP_URL

logger = logging.getLogger(__name__)
router = Router()

@router.inline_query()
async def process_inline_query(query: InlineQuery):
    """Обработчик инлайн-запросов."""
    logger.info(f"Inline запрос от {query.from_user.id}: {query.query}")
    
    # Создаем уникальные ID для результатов
    split_id = str(uuid4())
    webapp_id = str(uuid4())
    help_id = str(uuid4())
    about_id = str(uuid4())
    
    # Создаем кнопку с URL для открытия веб-приложения в браузере
    webapp_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть приложение в браузере", 
                    url=WEBAPP_URL
                )
            ]
        ]
    )
    
    # Создаем результаты для отображения
    results = [
        InlineQueryResultArticle(
            id=split_id,
            title="📷 Разделить чек",
            description="Отправить команду для начала сканирования чека",
            input_message_content=InputTextMessageContent(
                message_text="/split"
            ),
            thumbnail_url="https://img.icons8.com/color/48/000000/split-files.png"
        ),
        InlineQueryResultArticle(
            id=webapp_id,
            title="🌐 Открыть веб-приложение",
            description="Запустите веб-приложение для разделения чека",
            input_message_content=InputTextMessageContent(
                message_text="*СплитЧек* - Нажмите на кнопку ниже, чтобы открыть веб-приложение в браузере:",
                parse_mode="Markdown"
            ),
            reply_markup=webapp_keyboard,
            thumbnail_url="https://img.icons8.com/color/48/000000/web.png"
        ),
        InlineQueryResultArticle(
            id=help_id,
            title="❓ Помощь",
            description="Отправить справку по использованию бота",
            input_message_content=InputTextMessageContent(
                message_text="/help"
            ),
            thumbnail_url="https://img.icons8.com/color/48/000000/help.png"
        ),
        InlineQueryResultArticle(
            id=about_id,
            title="ℹ️ О боте",
            description="Информация о боте для разделения чеков",
            input_message_content=InputTextMessageContent(
                message_text="*Бот для разделения чеков*\n\n"
                "Отправьте фото чека, и я помогу разделить его между участниками. "
                "Я могу распознавать товары, цены, количества, и рассчитывать доли каждого участника.\n\n"
                "Для начала используйте команду /split и отправьте фото чека.",
                parse_mode="Markdown"
            ),
            thumbnail_url="https://img.icons8.com/color/48/000000/info.png"
        )
    ]
    
    # Добавляем специальный вариант для личных чатов
    private_chat_id = str(uuid4())
    results.append(
        InlineQueryResultArticle(
            id=private_chat_id,
            title="👤 Открыть личный чат с ботом",
            description="Для полной функциональности лучше использовать личный чат",
            input_message_content=InputTextMessageContent(
                message_text="Для полной работы с чеками, включая WebApp, откройте личный чат с ботом:"
            ),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Открыть личный чат с ботом", 
                            url=f"https://t.me/{(await query.bot.get_me()).username}"
                        )
                    ]
                ]
            ),
            thumbnail_url="https://img.icons8.com/color/48/000000/chat.png"
        )
    )
    
    # Если пользователь ввел какой-то запрос, добавляем результат поиска
    if query.query:
        search_id = str(uuid4())
        results.append(
            InlineQueryResultArticle(
                id=search_id,
                title=f"🔍 Поиск: {query.query}",
                description="Создать сообщение с этим текстом",
                input_message_content=InputTextMessageContent(
                    message_text=f"*Разделить чек*: {query.query}",
                    parse_mode="Markdown"
                )
            )
        )
    
    # Отправляем результаты
    try:
        await query.answer(results, cache_time=300)  # Кэшируем на 5 минут
    except Exception as e:
        logger.error(f"Ошибка при отправке inline результатов: {e}", exc_info=True)
        # В случае ошибки отправляем только базовые результаты без веб-приложения
        basic_results = [
            InlineQueryResultArticle(
                id=split_id,
                title="📷 Разделить чек",
                description="Отправить команду для начала сканирования чека",
                input_message_content=InputTextMessageContent(
                    message_text="/split"
                )
            ),
            InlineQueryResultArticle(
                id=help_id,
                title="❓ Помощь",
                description="Отправить справку по использованию бота",
                input_message_content=InputTextMessageContent(
                    message_text="/help"
                )
            )
        ]
        await query.answer(basic_results, cache_time=300) 