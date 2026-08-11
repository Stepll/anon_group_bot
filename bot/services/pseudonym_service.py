from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import repo
from bot.db.models import Settings, User


async def get_display_name(session: AsyncSession, user: User, settings: Settings) -> str:
    if not settings.pseudonym_mode:
        return "Anonymous"
    number = await repo.assign_pseudonym_number(session, user)
    return f"Анонім №{number}"
