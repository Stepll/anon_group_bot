import logging

from aiogram import Bot
from aiogram.enums import ContentType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message, ReplyParameters
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

    # If this message is a Reply (to someone else's message, or to the sender's
    # own earlier message), resolve which broadcast it's replying to, so every
    # recipient can be shown a real Telegram reply pointing at *their own* copy
    # of that original message.
    reply_broadcast_id = None
    if message.reply_to_message is not None:
        reply_broadcast_id = await repo.get_broadcast_id_for_message(
            session, sender.id, message.reply_to_message.message_id
        )

    broadcast = await repo.create_broadcast_message(session, sender.id)

    # Record the sender's own copy too (keyed by their own chat + message id),
    # so a later reply to this very message -- by the sender or anyone else --
    # can be resolved the same way.
    await repo.add_message_copy(session, broadcast.id, sender.id, message.message_id, is_content=True)

    for recipient in recipients:
        reply_to_message_id = None
        if reply_broadcast_id is not None:
            reply_to_message_id = await repo.get_content_copy_message_id(
                session, reply_broadcast_id, recipient.id
            )
            # If this recipient never actually received that message (joined
            # later, was banned back then, etc.) we just send without a reply
            # marker instead of failing the whole delivery.

        try:
            message_ids = await _deliver(bot, recipient.id, sender.id, message, label, reply_to_message_id)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            logger.info("Could not deliver broadcast to %s: %s", recipient.id, exc)
            continue

        # Store every message id delivered so a reply to any of them resolves
        # back to the real sender for /ban and /room.
        for message_id, is_content in message_ids:
            await repo.add_message_copy(session, broadcast.id, recipient.id, message_id, is_content=is_content)


async def _deliver(
    bot: Bot,
    chat_id: int,
    from_chat_id: int,
    message: Message,
    label: str | None,
    reply_to_message_id: int | None,
) -> list[tuple[int, bool]]:
    reply_parameters = None
    if reply_to_message_id is not None:
        reply_parameters = ReplyParameters(message_id=reply_to_message_id, allow_sending_without_reply=True)

    if label is None:
        sent = await bot.copy_message(chat_id, from_chat_id, message.message_id, reply_parameters=reply_parameters)
        return [(sent.message_id, True)]

    if message.content_type == ContentType.TEXT:
        sent = await bot.send_message(
            chat_id, f"<b>{label}</b>\n{message.html_text}", reply_parameters=reply_parameters
        )
        return [(sent.message_id, True)]

    if message.content_type in CAPTIONABLE_TYPES:
        caption = f"<b>{label}</b>" + (f"\n{message.html_text}" if message.html_text else "")
        sent = await bot.copy_message(
            chat_id, from_chat_id, message.message_id, caption=caption, reply_parameters=reply_parameters
        )
        return [(sent.message_id, True)]

    # Stickers, video notes, locations, polls, etc. have no caption slot in the
    # Bot API -- a separate header message is unavoidable for these. The reply
    # marker goes on the header, since that's what appears first.
    header = await bot.send_message(chat_id, f"🕶 {label}", reply_parameters=reply_parameters)
    content = await bot.copy_message(chat_id, from_chat_id, message.message_id)
    return [(header.message_id, False), (content.message_id, True)]
