import json
import logging
import uuid
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from utils.state import message_state
from utils.calculations import calculate_total_with_charges
from utils.formatters import format_user_summary

logger = logging.getLogger(__name__)
# Устанавливаем уровень логирования для этого модуля на DEBUG
logger.setLevel(logging.DEBUG)
router = Router()

# Будет установлено из main.py
message_states = {}

# Убираем или сильно упрощаем handle_all_messages, т.к. основной фокус на F.web_app_data
@router.message()
async def handle_other_messages_in_webapp_router(message: Message, state: FSMContext):
    logger.debug(f"[webapp.py] Получено сообщение НЕ web_app_data в webapp.router: {message.content_type}")
    # Здесь можно добавить логику для сообщений, которые случайно попали в этот роутер,
    # но не являются web_app_data. Либо оставить пустым, если таких быть не должно.
    pass

@router.message(F.web_app_data)
async def handle_webapp_data(message: Message, state: FSMContext):
    logger.info('=== [webapp.py] Вызван handle_webapp_data (через F.web_app_data) ===')
    data = None # Инициализируем data
    try:
        logger.info(f"[webapp.py] Получены данные от WebApp: {getattr(message.web_app_data, 'data', None)} | message_id_in_message_obj: {message.message_id}")
        
        try:
            data = json.loads(message.web_app_data.data)
            logger.info(f"[webapp.py] Распарсенные данные: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"[webapp.py] Ошибка при парсинге JSON: {e}")
            # Пытаемся ответить WebApp даже при ошибке парсинга, если query_id как-то можно извлечь или он не нужен для базового ответа
            # Но скорее всего, если JSON битый, query_id мы не получим. 
            # Этот блок можно улучшить, если предполагаются сценарии с битым JSON, но валидным query_id.
            await message.answer("❌ Ошибка при обработке данных WebApp (невалидный JSON). Пожалуйста, попробуйте еще раз.")
            return
        
        message_id_from_data = data.get('message_id') # ID сообщения из данных WebApp
        selected_items = data.get('selected_items', {})
        query_id = data.get('query_id')

        logger.info(f"[webapp.py] Извлечено из данных: message_id: {message_id_from_data}, query_id: {query_id}, selected_items: {selected_items}")

        if not message_id_from_data or not query_id:
            logger.error(f"[webapp.py] Отсутствуют обязательные поля: message_id_from_data={message_id_from_data}, query_id={query_id}")
            if query_id: # Если query_id все же есть, пытаемся ответить WebApp
                try:
                    await message.bot.answer_web_app_query(
                        web_app_query_id=query_id,
                        result=InlineQueryResultArticle(
                            id=str(uuid.uuid4()),
                            title="Ошибка: Неполные данные",
                            input_message_content=InputTextMessageContent(
                                message_text="❌ Ошибка: WebApp передал неполные данные (отсутствует ID сообщения или query_id)."
                            )
                        )
                    )
                    logger.info(f"[webapp.py] Отправлен ответ WebApp (ошибка неполных данных) для query_id: {query_id}")
                except Exception as e_ans:
                    logger.error(f"[webapp.py] Ошибка при отправке ответа WebApp (ошибка неполных данных): {e_ans}")
            await message.answer("❌ Ошибка: WebApp передал неполные данные. Пожалуйста, попробуйте еще раз.")
            return

        # TODO: Реализовать логику сохранения selected_items (например, в базу данных)
        # services.save_user_selection(user_id=message.from_user.id, original_message_id=message_id_from_data, selection=selected_items)
        logger.info(f"[webapp.py] Пользователь {message.from_user.id} выбрал: {selected_items} для message_id_from_data: {message_id_from_data}")

        # Отправляем подтверждение в WebApp через answer_web_app_query
        try:
            await message.bot.answer_web_app_query(
                web_app_query_id=query_id,
                result=InlineQueryResultArticle(
                    id=str(uuid.uuid4()), 
                    title="Выбор сохранен!",
                    input_message_content=InputTextMessageContent( 
                        message_text=f"Ваш выбор для чека (ID сообщения: {message_id_from_data}) был успешно обработан."
                    )
                )
            )
            logger.info(f"[webapp.py] Успешно отправлен ответ WebApp (answer_web_app_query) для query_id: {query_id}")
        except Exception as e_ans_query:
            logger.error(f"[webapp.py] Ошибка при вызове answer_web_app_query: {e_ans_query}", exc_info=True)
            # Если не удалось ответить WebApp, это критично для фронтенда.
            # Можно попробовать отправить обычное сообщение в чат, но WebApp останется в ожидании.
            await message.answer(f"⚠️ Не удалось подтвердить операцию в WebApp для query_id: {query_id}, но ваши данные могли быть обработаны. Проверьте, пожалуйста.")
            return # Прерываем, так как основное взаимодействие с WebApp не удалось

        # Формируем и отправляем сообщение в чат пользователю
        # TODO: Нужна функция для получения деталей товаров (имя, цена) по их индексам из selected_items
        # и данным чека, которые нужно где-то хранить или получать по message_id_from_data.
        items_text_list = []
        for item_idx, count in selected_items.items():
            items_text_list.append(f"Товар с индексом {item_idx}: {count} шт.") # Заглушка
        items_text = "\n".join(items_text_list)
        calculated_total_str = "не рассчитана" # Заглушка

        await message.answer(
            f"✅ Ваш выбор для чека (ID сообщения: {message_id_from_data}) сохранен ботом!\n\n"
            f"Выбранные позиции:\n{items_text}\n\n"
            f"Итого (заглушка): {calculated_total_str}",
        )
        logger.info(f"[webapp.py] Сообщение с подтверждением выбора отправлено в чат для пользователя {message.from_user.id}")

    except Exception as e_global:
        logger.error(f"[webapp.py] Глобальная ошибка в handle_webapp_data: {e_global}", exc_info=True)
        # Попытка ответить WebApp с сообщением об ошибке, если есть query_id
        if data and data.get('query_id'): # Проверяем, что data было определено и содержит query_id
            fallback_query_id = data.get('query_id')
            try:
                await message.bot.answer_web_app_query(
                    web_app_query_id=fallback_query_id,
                    result=InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title="Ошибка сервера",
                        input_message_content=InputTextMessageContent(
                            message_text="❌ Произошла внутренняя ошибка на сервере при обработке вашего выбора."
                        )
                    )
                )
                logger.info(f"[webapp.py] Отправлен ответ WebApp (глобальная ошибка) для query_id: {fallback_query_id}")
            except Exception as e_ans_fallback:
                logger.error(f"[webapp.py] Ошибка при отправке ответа WebApp (глобальная ошибка -> fallback): {e_ans_fallback}")
        await message.answer("❌ Произошла серьезная внутренняя ошибка при обработке вашего выбора. Пожалуйста, попробуйте еще раз.") 