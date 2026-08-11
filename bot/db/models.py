from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    """A chat participant, keyed by their Telegram user_id (== their private chat_id)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pseudonym_number: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_in_room: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BroadcastMessage(Base):
    """One record per incoming message that gets fanned out to the chat."""

    __tablename__ = "broadcast_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MessageCopy(Base):
    """Maps a copy delivered to a specific chat back to the broadcast it came from.

    This is what lets an admin Reply to a message they see and have the bot
    resolve who actually sent it, without anyone else ever seeing that link.
    """

    __tablename__ = "message_copies"
    __table_args__ = (
        UniqueConstraint("recipient_chat_id", "telegram_message_id", name="uq_recipient_message"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broadcast_id: Mapped[int] = mapped_column(Integer, ForeignKey("broadcast_messages.id"))
    recipient_chat_id: Mapped[int] = mapped_column(BigInteger)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger)
    # False only for the small "🕶 label" header sent ahead of content types that
    # have no caption slot (stickers, video notes, ...). Used to pick which of a
    # recipient's messages a reply-to should point at.
    is_content: Mapped[bool] = mapped_column(Boolean, default=True)


class Room(Base):
    """An active or past private admin<->participant room."""

    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger)
    participant_id: Mapped[int] = mapped_column(BigInteger)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Settings(Base):
    """Single-row table (id=1) holding global chat settings."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    pseudonym_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    rate_limit_seconds: Mapped[float] = mapped_column(Float, default=1.0)
