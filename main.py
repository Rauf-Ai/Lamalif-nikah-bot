"""
main.py — точка входа бота ЛямАлиф Никях
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
import database as db
from handlers import registration, browse, misc
from handlers import payment, referral

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


async def premium_expiry_task():
    """Каждый час снимаем истёкший премиум."""
    while True:
        try:
            await db.revoke_expired_premiums()
        except Exception as e:
            logger.error(f"premium_expiry_task error: {e}")
        await asyncio.sleep(3600)


async def main():
    await db.init_db()
    logger.info("База данных инициализирована.")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Роутеры (порядок важен — payment должен быть раньше misc)
    dp.include_router(registration.router)
    dp.include_router(payment.router)
    dp.include_router(referral.router)
    dp.include_router(browse.router)
    dp.include_router(misc.router)

    # Фоновая задача снятия истёкшего премиума
    asyncio.create_task(premium_expiry_task())

    logger.info("Бот запущен. Polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
    
