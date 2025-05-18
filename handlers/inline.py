import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatType
from uuid import uuid4
from config.settings import WEBAPP_URL, BOT_USERNAME
from utils.logging import log_event

logger = logging.getLogger(__name__)
router = Router()

@router.inline_query()
async def process_inline_query(query: InlineQuery):
    """Обработчик инлайн-запросов."""
    start_time = datetime.utcnow()
    
    try:
        # Получаем имя бота
        bot_username = BOT_USERNAME
        if not bot_username:
            bot_info = await query.bot.get_me()
            bot_username = bot_info.username
            if not bot_username:
                raise ValueError("Не удалось получить имя бота")
        
        # Создаем уникальные ID для результатов
        split_id = str(uuid4())
        webapp_id = str(uuid4())
        help_id = str(uuid4())
        about_id = str(uuid4())
        
        # Определяем тип чата для корректного отображения инструкций
        is_private = query.chat_type == ChatType.PRIVATE
        
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
        await query.answer(results, cache_time=300)  # Кэшируем на 5 минут
        
        # Логируем успешное выполнение
        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_event(
            event_type="inline_query",
            user_id=query.from_user.id,
            chat_type=query.chat_type if query.chat_type else "private",
            query=query.query,
            elapsed_ms=elapsed_ms
        )
        
    except Exception as e:
        # Логируем ошибку
        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_event(
            event_type="inline_query_error",
            user_id=query.from_user.id,
            chat_type=query.chat_type if query.chat_type else "private",
            query=query.query,
            error=str(e),
            elapsed_ms=elapsed_ms,
            level="error"
        )
        
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
            log_event(
                event_type="inline_query_critical_error",
                user_id=query.from_user.id,
                chat_type=query.chat_type if query.chat_type else "private",
                query=query.query,
                error=f"Критическая ошибка при отправке базовых результатов: {str(e2)}",
                elapsed_ms=elapsed_ms,
                level="critical"
            ) 