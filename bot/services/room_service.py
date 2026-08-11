from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import repo
from bot.db.models import Room, Settings, User
from bot.services import pseudonym_service


async def start_room(session: AsyncSession, bot: Bot, admin: User, participant: User, settings: Settings) -> Room:
    room = await repo.create_room(session, admin.id, participant.id)
    await repo.set_in_room(session, admin, True)
    await repo.set_in_room(session, participant, True)

    # The admin is never assigned/shown a pseudonym number -- other participants
    # must never be able to tell who among them is an admin.
    participant_label = await pseudonym_service.get_display_name(session, participant, settings)
    notice = f"🚪 Адміністратор та {participant_label} зайшли в кімнату — вони вас не чують."
    await _notify_others(session, bot, notice, exclude_ids={admin.id, participant.id})

    for user_id in (admin.id, participant.id):
        await _safe_send(bot, user_id, "🚪 Ви в приватній кімнаті. Ваші повідомлення бачить лише співрозмовник.")

    return room


async def end_room_for_user(session: AsyncSession, bot: Bot, user: User, settings: Settings) -> Room | None:
    room = await repo.get_active_room_for_user(session, user.id)
    if room is None:
        return None

    admin = await session.get(User, room.admin_id)
    participant = await session.get(User, room.participant_id)

    await repo.end_room(session, room)
    if admin is not None:
        await repo.set_in_room(session, admin, False)
    if participant is not None:
        await repo.set_in_room(session, participant, False)

    participant_label = (
        await pseudonym_service.get_display_name(session, participant, settings) if participant else "учасник"
    )
    notice = f"🚪 Адміністратор та {participant_label} вийшли з кімнати — знову бачите загальний чат."
    await _notify_others(session, bot, notice, exclude_ids={room.admin_id, room.participant_id})

    for user_id in (room.admin_id, room.participant_id):
        await _safe_send(bot, user_id, "🚪 Кімнату закрито. Ви знову в загальному чаті.")

    return room


async def route_message(bot: Bot, session: AsyncSession, user: User, message: Message) -> None:
    room = await repo.get_active_room_for_user(session, user.id)
    if room is None:
        return
    target_id = room.participant_id if user.id == room.admin_id else room.admin_id
    try:
        await bot.copy_message(target_id, user.id, message.message_id)
    except (TelegramForbiddenError, TelegramBadRequest):
        pass


async def _notify_others(session: AsyncSession, bot: Bot, text: str, exclude_ids: set[int]) -> None:
    recipients = await repo.get_notifiable_users(session, exclude_ids)
    for recipient in recipients:
        await _safe_send(bot, recipient.id, text)


async def _safe_send(bot: Bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except (TelegramForbiddenError, TelegramBadRequest):
        pass
