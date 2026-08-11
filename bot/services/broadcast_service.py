import logging

from aiogram import Bot
from aiogram.enums import ContentType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import repo
from bot.db.models import Settings, User
from bot.services import antiflood, pseudonym_service

logger = logging.getLogger(__name__)

# Content types where Telegram's Bot API accepts a `caption`, so the pseudonym
# label can ride along inside the same message instead of a separate one.
CAPTIONABLE_TYPES = {
    ContentType.PHOTO,
    ContentType.VIDEO,
    ContentType.DOCUMENT,
    ContentType.AUDIO,
    ContentType.VOICE,
    ContentType.ANIMATION,
}


async def broadcast_message(bot: Bot, session: AsyncSession, sender: User, message: Message, settings: Settings) -> None:
    if not antiflood.allow(sender.id, settings.rate_limit_seconds):
        return

    recipients = await repo.get_active_recipients(session, exclude_id=sender.id)
    if not recipients:
        return

    # In full-anonymity mode everyone is the same "Anonymous" -- a label would
    # carry zero information, so skip it entirely and just relay the message.
    label = None
    if settings.pseudonym_mode:
        label = await pseudonym_service.get_display_name(session, sender, settings)

    broadcast = await repo.create_broadcast_message(session, sender.id)

    for recipient in recipients:
        try:
            message_ids = await _deliver(bot, recipient.id, sender.id, message, label)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            logger.info("Could not deliver broadcast to %s: %s", recipient.id, exc)
            continue

        # Store every message id delivered so a reply to any of them resolves
        # back to the real sender for /ban and /room.
        for message_id in message_ids:
            await repo.add_message_copy(session, broadcast.id, recipient.id, message_id)


async def _deliver(bot: Bot, chat_id: int, from_chat_id: int, message: Message, label: str | None) -> list[int]:
    if label is None:
        sent = await bot.copy_message(chat_id, from_chat_id, message.message_id)
        return [sent.message_id]

    if message.content_type == ContentType.TEXT:
        sent = await bot.send_message(chat_id, f"<b>{label}</b>\n{message.html_text}")
        return [sent.message_id]

    if message.content_type in CAPTIONABLE_TYPES:
        caption = f"<b>{label}</b>" + (f"\n{message.html_text}" if message.html_text else "")
        sent = await bot.copy_message(chat_id, from_chat_id, message.message_id, caption=caption)
        return [sent.message_id]

    # Stickers, video notes, locations, polls, etc. have no caption slot in the
    # Bot API -- a separate header message is unavoidable for these.
    header = await bot.send_message(chat_id, f"🕶 {label}")
    content = await bot.copy_message(chat_id, from_chat_id, message.message_id)
    return [header.message_id, content.message_id]
