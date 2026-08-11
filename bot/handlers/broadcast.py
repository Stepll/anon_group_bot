from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Settings, User
from bot.services import broadcast_service, room_service

router = Router(name="broadcast")


@router.message(F.text.startswith("/"))
async def ignore_unknown_command(message: Message) -> None:
    # Swallow unrecognized/unauthorized commands rather than broadcasting the raw text
    # (e.g. a non-admin typing /ban shouldn't leak that attempt into the chat).
    return


@router.message()
async def handle_message(message: Message, session: AsyncSession, user: User, settings: Settings) -> None:
    if user.is_banned:
        await message.answer("🚫 Ви заблоковані в цьому чаті.")
        return

    if user.is_in_room:
        await room_service.route_message(message.bot, session, user, message)
        return

    await broadcast_service.broadcast_message(message.bot, session, user, message, settings)
