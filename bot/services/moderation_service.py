from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import repo
from bot.db.models import User


async def resolve_sender_from_reply(session: AsyncSession, chat_id: int, replied_message_id: int) -> User | None:
    return await repo.resolve_sender(session, chat_id, replied_message_id)


async def ban(session: AsyncSession, user: User) -> None:
    await repo.ban_user(session, user)


async def unban(session: AsyncSession, user: User) -> None:
    await repo.unban_user(session, user)


async def list_banned(session: AsyncSession) -> list[User]:
    return await repo.list_banned(session)
