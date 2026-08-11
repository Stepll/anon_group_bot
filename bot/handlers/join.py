from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.db.models import User

router = Router(name="join")


@router.message(CommandStart())
async def cmd_start(message: Message, user: User) -> None:
    if user.is_banned:
        await message.answer("🚫 Ви заблоковані в цьому чаті.")
        return

    text = (
        "👋 Вітаємо в анонімному чаті!\n\n"
        "Усе, що ви напишете сюди, буде переслано іншим учасникам анонімно — "
        "ваше ім'я ніхто не побачить.\n"
        "Будьте ввічливі одне до одного 🙂"
    )
    await message.answer(text)
