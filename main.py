from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from bot.handlers import setup_handlers
from bot.config import BOT_TOKEN

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

setup_handlers(dp)

if __name__ == "__main__":
    import asyncio
    from bot.database import create_db

    async def main():
        await create_db()
        await dp.start_polling(bot)

    asyncio.run(main())
