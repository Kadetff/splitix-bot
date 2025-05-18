import logging
from datetime import datetime, UTC
from aiogram import Router, F
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.enums import ChatType
from uuid import uuid4
from config.settings import BOT_USERNAME
from utils.logging import log_event

logger = logging.getLogger(__name__)
router = Router()

@router.inline_query()
async def process_inline_query(query: InlineQuery):
    """Обработчик инлайн-запросов."""
    start_time = datetime.now(UTC)
    
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
            )
        ]
        
        # Отправляем результаты
        await query.answer(results, cache_time=300)  # Кэшируем на 5 минут
        
        # Логируем успешное выполнение
        elapsed_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
        log_event(
            event_type="inline_query",
            user_id=query.from_user.id,
            chat_type=query.chat_type if query.chat_type else "private",
            query=query.query,
            elapsed_ms=elapsed_ms
        )
        
    except Exception as e:
        # Логируем ошибку
        elapsed_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
        log_event(
            event_type="inline_query_error",
            user_id=query.from_user.id,
            chat_type=query.chat_type if query.chat_type else "private",
            query=query.query,
            error=str(e),
            elapsed_ms=elapsed_ms,
            level="error"
        ) 