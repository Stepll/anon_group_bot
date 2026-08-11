import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot import config
from bot.db.engine import init_models, session_factory
from bot.handlers import admin_commands, broadcast, join, room
from bot.middlewares.access import DbSessionMiddleware


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_models()

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    db_middleware = DbSessionMiddleware(session_factory)
    dp.message.middleware(db_middleware)
    dp.callback_query.middleware(db_middleware)

    # Order matters: command routers first, generic catch-all broadcast handler last.
    dp.include_router(admin_commands.router)
    dp.include_router(room.router)
    dp.include_router(join.router)
    dp.include_router(broadcast.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
