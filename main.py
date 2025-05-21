import asyncio
import logging
from typing import Any
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from config.settings import TELEGRAM_BOT_TOKEN, LOG_LEVEL
from handlers import photo, callbacks, commands, webapp, inline

# Настраиваем логирование
logging.basicConfig(
    level=logging.DEBUG if LOG_LEVEL == "DEBUG" else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Словарь для хранения состояния (items и их счетчики) для каждого сообщения с клавиатурой
message_states: dict[int, dict[str, Any]] = {}

# Экспорт message_states для использования в обработчиках
callbacks.message_states = message_states
photo.message_states = message_states
# webapp.message_states = message_states # Временно комментируем для отладки

async def main():
    logger.info(f"Бот запускается с OpenAI GPT Vision и подтверждением выбора...")
    logger.info(f"Уровень логирования: {LOG_LEVEL}")
    
    # Инициализируем бота и диспетчер
    storage = MemoryStorage()
    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=storage)
    
    # Регистрируем команды бота
    await register_commands(bot)
    
    # Регистрируем обработчики
    dp.include_router(photo.router)
    dp.include_router(webapp.router)
    dp.include_router(callbacks.router)
    dp.include_router(commands.router)
    dp.include_router(inline.router)
    
    await dp.start_polling(bot)

async def register_commands(bot: Bot):
    """Регистрирует команды бота для отображения в меню."""
    commands = [
        BotCommand(command="start", description="👋 Начать работу с ботом"),
        BotCommand(command="help", description="❓ Помощь по использованию бота"),
        BotCommand(command="split", description="📇 Разделить чек (в группе)")
    ]
    await bot.set_my_commands(commands)
    logger.info("Команды бота зарегистрированы")

if __name__ == "__main__":
    asyncio.run(main()) 