from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Settings, User
from bot.services import room_service

router = Router(name="room")


@router.message(Command("leaveroom"))
async def cmd_leaveroom(message: Message, session: AsyncSession, user: User, settings: Settings) -> None:
    # Open to admin and participant alike -- whoever is in an active room can leave it.
    room = await room_service.end_room_for_user(session, message.bot, user, settings)
    if room is None:
        await message.answer("У вас немає активної кімнати.")
