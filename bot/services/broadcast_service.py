import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import repo
from bot.db.models import Settings, User
from bot.services import antiflood, pseudonym_service

logger = logging.getLogger(__name__)


async def broadcast_message(bot: Bot, session: AsyncSession, sender: User, message: Message, settings: Settings) -> None:
    if not antiflood.allow(sender.id, settings.rate_limit_seconds):
        return

    label = await pseudonym_service.get_display_name(session, sender, settings)
    recipients = await repo.get_active_recipients(session, exclude_id=sender.id)
    if not recipients:
        return

    broadcast = await repo.create_broadcast_message(session, sender.id)

    # Sent as a separate header line (rather than a merged caption) so every
    # content type -- text, photo, sticker, voice, etc. -- is handled uniformly.
    for recipient in recipients:
        try:
            header = await bot.send_message(recipient.id, f"🕶 {label}")
            copy = await bot.copy_message(recipient.id, sender.id, message.message_id)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            logger.info("Could not deliver broadcast to %s: %s", recipient.id, exc)
            continue

        # Store both message ids so a reply to either the header or the
        # content resolves back to the real sender for /ban and /room.
        await repo.add_message_copy(session, broadcast.id, recipient.id, header.message_id)
        await repo.add_message_copy(session, broadcast.id, recipient.id, copy.message_id)
