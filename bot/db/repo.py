from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot import config
from bot.db.models import BroadcastMessage, MessageCopy, Room, Settings, User


async def get_or_create_user(session: AsyncSession, user_id: int) -> tuple[User, bool]:
    user = await session.get(User, user_id)
    if user is not None:
        return user, False
    user = User(id=user_id)
    session.add(user)
    await session.flush()
    return user, True


async def get_settings(session: AsyncSession) -> Settings:
    settings = await session.get(Settings, 1)
    if settings is None:
        settings = Settings(id=1, rate_limit_seconds=config.DEFAULT_RATE_LIMIT_SECONDS)
        session.add(settings)
        await session.flush()
    return settings


async def set_pseudonym_mode(session: AsyncSession, enabled: bool) -> Settings:
    settings = await get_settings(session)
    settings.pseudonym_mode = enabled
    await session.flush()
    return settings


async def set_rate_limit(session: AsyncSession, seconds: float) -> Settings:
    settings = await get_settings(session)
    settings.rate_limit_seconds = seconds
    await session.flush()
    return settings


async def assign_pseudonym_number(session: AsyncSession, user: User) -> int:
    if user.pseudonym_number is not None:
        return user.pseudonym_number
    max_number = await session.scalar(select(func.max(User.pseudonym_number)))
    user.pseudonym_number = (max_number or 0) + 1
    await session.flush()
    return user.pseudonym_number


async def ban_user(session: AsyncSession, user: User) -> None:
    user.is_banned = True
    user.banned_at = datetime.now(timezone.utc)
    await session.flush()


async def unban_user(session: AsyncSession, user: User) -> None:
    user.is_banned = False
    user.banned_at = None
    await session.flush()


async def list_banned(session: AsyncSession) -> list[User]:
    result = await session.scalars(select(User).where(User.is_banned.is_(True)))
    return list(result)


async def get_active_recipients(session: AsyncSession, exclude_id: int) -> list[User]:
    result = await session.scalars(
        select(User).where(
            User.id != exclude_id,
            User.is_banned.is_(False),
            User.is_in_room.is_(False),
        )
    )
    return list(result)


async def get_notifiable_users(session: AsyncSession, exclude_ids: set[int]) -> list[User]:
    result = await session.scalars(
        select(User).where(
            User.id.not_in(exclude_ids),
            User.is_banned.is_(False),
            User.is_in_room.is_(False),
        )
    )
    return list(result)


async def create_broadcast_message(session: AsyncSession, sender_id: int) -> BroadcastMessage:
    broadcast = BroadcastMessage(sender_id=sender_id)
    session.add(broadcast)
    await session.flush()
    return broadcast


async def add_message_copy(
    session: AsyncSession, broadcast_id: int, recipient_chat_id: int, telegram_message_id: int
) -> None:
    session.add(
        MessageCopy(
            broadcast_id=broadcast_id,
            recipient_chat_id=recipient_chat_id,
            telegram_message_id=telegram_message_id,
        )
    )
    await session.flush()


async def resolve_sender(session: AsyncSession, chat_id: int, telegram_message_id: int) -> User | None:
    copy = await session.scalar(
        select(MessageCopy).where(
            MessageCopy.recipient_chat_id == chat_id,
            MessageCopy.telegram_message_id == telegram_message_id,
        )
    )
    if copy is None:
        return None
    broadcast = await session.get(BroadcastMessage, copy.broadcast_id)
    if broadcast is None:
        return None
    return await session.get(User, broadcast.sender_id)


async def count_active_users(session: AsyncSession) -> int:
    result = await session.scalar(select(func.count()).select_from(User).where(User.is_banned.is_(False)))
    return result or 0


async def count_banned_users(session: AsyncSession) -> int:
    result = await session.scalar(select(func.count()).select_from(User).where(User.is_banned.is_(True)))
    return result or 0


async def count_messages_since(session: AsyncSession, since: datetime) -> int:
    result = await session.scalar(
        select(func.count()).select_from(BroadcastMessage).where(BroadcastMessage.sent_at >= since)
    )
    return result or 0


async def set_in_room(session: AsyncSession, user: User, value: bool) -> None:
    user.is_in_room = value
    await session.flush()


async def create_room(session: AsyncSession, admin_id: int, participant_id: int) -> Room:
    room = Room(admin_id=admin_id, participant_id=participant_id)
    session.add(room)
    await session.flush()
    return room


async def get_active_room_for_user(session: AsyncSession, user_id: int) -> Room | None:
    return await session.scalar(
        select(Room).where(
            Room.is_active.is_(True),
            (Room.admin_id == user_id) | (Room.participant_id == user_id),
        )
    )


async def end_room(session: AsyncSession, room: Room) -> None:
    room.is_active = False
    room.ended_at = datetime.now(timezone.utc)
    await session.flush()
