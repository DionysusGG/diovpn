import asyncio
import sys
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from bot.handlers import register_handlers
from bot.callbacks import register_callbacks

# Настройка базового логирования
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)

async def shutdown(dp: Dispatcher = None, bot: Bot = None):
    """Корректное завершение работы бота"""
    logging.info("Shutting down...")
    
    try:
        # Закрываем хранилище если оно есть
        if dp and dp.storage:
            try:
                if hasattr(dp.storage, 'close'):
                    await dp.storage.close()
                    logging.info("Storage closed successfully")
            except Exception as e:
                logging.error(f"Error closing storage: {e}")
        
        # Закрываем сессию бота если она есть
        if bot and hasattr(bot, 'session'):
            try:
                await bot.session.close()
                logging.info("Bot session closed successfully")
            except Exception as e:
                logging.error(f"Error closing bot session: {e}")
    except Exception as e:
        logging.error(f"Error during shutdown: {e}")
    
    logging.info("Bot stopped!")


async def main():
    try:
        # Настройка расширенного логирования
        file_handler = logging.FileHandler('bot.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logging.getLogger().addHandler(file_handler)
        logging.getLogger().setLevel(logging.INFO)
        
        logging.info("Starting bot...")
        
        # Инициализация базы данных
        try:
            from database.models import init_db
            init_db()
            logging.info("Database initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize database: {e}")
            raise
        
        # Создаем бота с указанными параметрами
        session = AiohttpSession()
        bot = Bot(
            token=BOT_TOKEN,
            session=session,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                link_preview_is_disabled=True
            )
        )
        # Создаем диспетчер
        dp = Dispatcher(storage=MemoryStorage())

        # Регистрация хендлеров и колбэков
        register_handlers(dp)
        register_callbacks(dp)
        
        # Настраиваем очистку ключей
        from core.xray import setup_cleanup_task
        await setup_cleanup_task(dp)
        
        # Запускаем бота
        logging.info("Bot started!")
        
        # Запускаем поллинг
        try:
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                close_bot_session=True
            )
        except Exception as e:
            logging.error(f"Polling error: {e}")
            raise
        
    except Exception as e:
        logging.error(f"Critical error: {e}")
        raise
    finally:
        logging.info("Bot stopped")
        await shutdown(dp, bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
    finally:
        sys.exit(0)
