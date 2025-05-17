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
    
    # Получаем имя бота
    try:
        bot_info = await query.bot.get_me()
        bot_username = bot_info.username
    except Exception as e:
        logger.error(f"Не удалось получить имя бота: {e}")
        bot_username = "Splitix_bot"  # Fallback на известное имя бота
    
    # Создаем уникальные ID для результатов
    split_id = str(uuid4())
    webapp_id = str(uuid4())
    help_id = str(uuid4())
    about_id = str(uuid4())
    
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
            title="🌐 Открыть мини-приложение",
            description="Инструкции по доступу к мини-приложению Telegram",
            input_message_content=InputTextMessageContent(
                message_text=f"*СплитЧек* - Для открытия мини-приложения перейдите в [личный чат с ботом](https://t.me/{bot_username}) и введите команду /webapp\n\n" +
                "⚠️ Из-за ограничений Telegram мини-приложения работают только в личных чатах.",
                parse_mode="Markdown"
            ),
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
                "Отправьте фото чека, и я помогу разделить его между участниками.\n\n"
                "Для начала используйте команду /split и отправьте фото чека.",
                parse_mode="Markdown"
            ),
            thumbnail_url="https://img.icons8.com/color/48/000000/info.png"
        )
    ]
    
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
        # В случае ошибки отправляем только базовые результаты
        basic_results = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="📷 Разделить чек",
                description="Отправить команду для начала сканирования чека",
                input_message_content=InputTextMessageContent(
                    message_text="/split"
                )
            )
        ]
        try:
            await query.answer(basic_results, cache_time=5)
        except Exception as e2:
            logger.critical(f"Критическая ошибка при отправке базовых результатов: {e2}", exc_info=True) 