import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.calculations import calculate_total_with_charges
from utils.formatters import format_user_summary, format_final_summary
from utils.state import message_state
from handlers.commands import HELP_TEXT

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "confirm_selection", FSMContext)
async def handle_confirm_selection(callback: CallbackQuery, state: FSMContext):
    """Обработчик подтверждения выбора товаров из мини-приложения."""
    try:
        message_id = callback.message.message_id
        user_id = callback.from_user.id
        
        # Получаем состояние
        state_data = message_state.get_state(message_id)
        if not state_data:
            await callback.answer("Состояние для этого списка не найдено. Возможно, он устарел.", show_alert=True)
            return
        
        # Получаем выбор пользователя
        user_counts = message_state.get_user_selection(message_id, user_id)
        if not user_counts or not any(user_counts.values()):
            await callback.answer("❌ Выберите хотя бы один товар")
            return
        
        # Рассчитываем итоги
        total_sum, summary = calculate_total_with_charges(
            items=state_data.get("items", []),
            user_counts=user_counts,
            service_charge_percent=state_data.get("service_charge_percent"),
            actual_discount_percent=state_data.get("actual_discount_percent"),
            total_discount_amount=state_data.get("total_discount_amount")
        )
        
        # Форматируем сообщение
        username = callback.from_user.username or callback.from_user.first_name
        formatted_summary = format_user_summary(username, state_data["items"], user_counts, total_sum, summary)
        
        # Сохраняем результат
        if "user_results" not in state_data:
            state_data["user_results"] = {}
        
        state_data["user_results"][user_id] = {
            "summary": formatted_summary,
            "total_sum": float(total_sum),
            "selected_items": {str(idx): count for idx, count in user_counts.items() if count > 0}
        }
        
        # Отправляем сообщения
        await callback.message.answer(formatted_summary, parse_mode="HTML")
        
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(
            text="👥 Посмотреть итоги всех участников",
            callback_data="show_all_results"
        ))
        
        await callback.message.answer(
            "✅ Ваш выбор подтвержден и сохранен! Теперь каждый участник может сделать свой выбор независимо.",
            reply_markup=keyboard.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке confirm_selection: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.")

@router.callback_query(F.data == "show_all_results")
async def handle_show_all_results(callback: CallbackQuery):
    """Обработчик показа результатов всех участников."""
    try:
        message_id = callback.message.message_id
        state_data = message_state.get_state(message_id)
        
        if not state_data or "user_results" not in state_data:
            await callback.answer("Нет данных о результатах участников.")
            return
        
        # Собираем имена пользователей
        usernames = {}
        for user_id in state_data["user_results"].keys():
            user = await callback.bot.get_chat_member(callback.message.chat.id, user_id)
            usernames[user_id] = user.user.username or user.user.first_name
        
        # Форматируем итоговый результат
        summary = format_final_summary(state_data["user_results"], usernames)
        
        # Отправляем результат
        await callback.message.answer(summary, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при показе результатов: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка при отображении результатов.")

@router.callback_query(F.data == "show_instructions")
async def handle_instructions(callback: CallbackQuery):
    """Показывает инструкцию по использованию бота (тот же текст, что и /help)."""
    await callback.message.answer(HELP_TEXT)
    await callback.answer()

@router.callback_query(F.data == "webapp_info")
async def handle_webapp_info(callback: CallbackQuery):
    """Показывает информацию о WebApp."""
    info_text = (
        "ℹ️ **О WebApp тестировании:**\n\n"
        "🧪 **Тестовый WebApp** позволяет:\n"
        "• Отправлять простые текстовые данные\n"
        "• Отправлять JSON-структуры\n"
        "• Проверять работу обеих типов кнопок\n\n"
        "📱 **Источники запуска:**\n"
        "• **Inline-кнопка** - кнопка в сообщении\n"
        "• **Reply-кнопка** - кнопка в нижней клавиатуре\n\n"
        "🎯 **Что тестируется:**\n"
        "• Получение данных ботом\n"
        "• Определение источника кнопки\n"
        "• Обработка различных форматов\n\n"
        "💡 **Попробуйте отправить** в WebApp:\n"
        "• Простое сообщение: `Привет`\n"
        "• JSON-данные с различными полями"
    )
    
    await callback.message.answer(info_text, parse_mode="Markdown")
    await callback.answer("ℹ️ Информация о WebApp")

@router.callback_query(F.data == "webapp_error")
async def handle_webapp_error(callback: CallbackQuery):
    """Обрабатывает ошибку создания WebApp кнопки."""
    error_text = (
        "❌ **Ошибка создания WebApp кнопки**\n\n"
        "🔧 **Возможные причины:**\n"
        "• URL веб-приложения не настроен\n"
        "• Некорректный формат URL\n"
        "• Проблемы с конфигурацией\n\n"
        "🛠️ **Решение:**\n"
        "• Проверьте переменную WEBAPP_URL\n"
        "• Убедитесь, что Flask-сервер запущен\n"
        "• Попробуйте команду `/webhook` для диагностики\n\n"
        "📞 **Поддержка:**\n"
        "Обратитесь к администратору для настройки"
    )
    
    await callback.message.answer(error_text, parse_mode="Markdown")
    await callback.answer("❌ Ошибка WebApp", show_alert=True) 