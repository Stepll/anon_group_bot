from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.db import repo


class DbSessionMiddleware(BaseMiddleware):
    """Opens one DB session per update, resolves/creates the acting User,
    and attaches `session`, `user`, `settings` to the handler's data dict.

    Registered as an outer middleware on both `message` and `callback_query`
    so every handler can just declare these as extra function parameters.
    """

    def __init__(self, session_factory: async_sessionmaker) -> None:
        super().__init__()
        self.session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_factory() as session:
            data["session"] = session

            from_user = data.get("event_from_user")
            if from_user is not None:
                user, _ = await repo.get_or_create_user(session, from_user.id)
                data["user"] = user
                data["settings"] = await repo.get_settings(session)

            result = await handler(event, data)
            await session.commit()
            return result
