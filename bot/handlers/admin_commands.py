from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot import config
from bot.db import repo
from bot.db.models import Settings, User
from bot.services import moderation_service, room_service

router = Router(name="admin")
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))


HELP_TEXT = (
    "🛠 Адмін-команди:\n"
    "/ban — у відповідь на повідомлення забанити автора\n"
    "/unban — список забанених для розбану\n"
    "/pseudonym on|off — увімкнути/вимкнути псевдо-номери учасників\n"
    "/setlimit <секунди> — анти-флуд ліміт\n"
    "/stats — статистика чату\n"
    "/room — у відповідь на повідомлення почати приватну кімнату з автором\n"
    "/leaveroom — завершити активну приватну кімнату"
)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("ban"))
async def cmd_ban(message: Message, session: AsyncSession) -> None:
    if not message.reply_to_message:
        await message.answer("Зробіть Reply на повідомлення учасника, якого треба забанити.")
        return

    target = await moderation_service.resolve_sender_from_reply(
        session, message.chat.id, message.reply_to_message.message_id
    )
    if target is None:
        await message.answer("Не вдалося визначити автора цього повідомлення.")
        return
    if target.id in config.ADMIN_IDS:
        await message.answer("Неможливо забанити адміністратора.")
        return

    await moderation_service.ban(session, target)
    await message.answer("✅ Учасника забанено.")


@router.message(Command("unban"))
async def cmd_unban(message: Message, session: AsyncSession) -> None:
    banned = await moderation_service.list_banned(session)
    if not banned:
        await message.answer("Забанених немає.")
        return

    buttons = [
        [
            InlineKeyboardButton(
                text=f"Розбанити {_label(u)}",
                callback_data=f"unban:{u.id}",
            )
        ]
        for u in banned
    ]
    await message.answer("Оберіть кого розбанити:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("unban:"))
async def cb_unban(callback: CallbackQuery, session: AsyncSession) -> None:
    user_id = int(callback.data.split(":", 1)[1])
    target = await session.get(User, user_id)
    if target is None or not target.is_banned:
        await callback.answer("Вже неактуально.", show_alert=True)
        return

    await moderation_service.unban(session, target)
    if callback.message is not None:
        await callback.message.edit_text("✅ Розбанено.")
    await callback.answer()


@router.message(Command("pseudonym"))
async def cmd_pseudonym(message: Message, command: CommandObject, session: AsyncSession) -> None:
    arg = (command.args or "").strip().lower()
    if arg not in ("on", "off"):
        await message.answer("Використання: /pseudonym on|off")
        return

    await repo.set_pseudonym_mode(session, arg == "on")
    await message.answer(f"✅ Режим псевдонімів: {'увімкнено' if arg == 'on' else 'вимкнено'}.")


@router.message(Command("setlimit"))
async def cmd_setlimit(message: Message, command: CommandObject, session: AsyncSession) -> None:
    raw = (command.args or "").strip()
    try:
        value = float(raw)
        if value < 0:
            raise ValueError
    except ValueError:
        await message.answer("Використання: /setlimit <секунди>, напр. /setlimit 1.5")
        return

    await repo.set_rate_limit(session, value)
    await message.answer(f"✅ Ліміт: 1 повідомлення на {value} сек.")


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    active = await repo.count_active_users(session)
    banned = await repo.count_banned_users(session)
    since_hour = datetime.now(timezone.utc) - timedelta(hours=1)
    since_day = datetime.now(timezone.utc) - timedelta(days=1)
    msgs_hour = await repo.count_messages_since(session, since_hour)
    msgs_day = await repo.count_messages_since(session, since_day)
    settings = await repo.get_settings(session)

    text = (
        "📊 Статистика:\n"
        f"Активних учасників: {active}\n"
        f"Забанених: {banned}\n"
        f"Повідомлень за годину: {msgs_hour}\n"
        f"Повідомлень за добу: {msgs_day}\n"
        f"Режим псевдонімів: {'увімкнено' if settings.pseudonym_mode else 'вимкнено'}\n"
        f"Анти-флуд: 1 повідомлення на {settings.rate_limit_seconds} сек."
    )
    await message.answer(text)


@router.message(Command("room"))
async def cmd_room(message: Message, session: AsyncSession, user: User, settings: Settings) -> None:
    if not message.reply_to_message:
        await message.answer("Зробіть Reply на повідомлення учасника, з яким хочете почати приватну кімнату.")
        return

    if await repo.get_active_room_for_user(session, user.id):
        await message.answer("У вас уже є активна кімната. Спершу завершіть її командою /leaveroom.")
        return

    participant = await moderation_service.resolve_sender_from_reply(
        session, message.chat.id, message.reply_to_message.message_id
    )
    if participant is None:
        await message.answer("Не вдалося визначити автора цього повідомлення.")
        return
    if participant.id in config.ADMIN_IDS:
        await message.answer("Не можна відкрити кімнату з іншим адміністратором.")
        return
    if participant.is_banned:
        await message.answer("Цей учасник забанений.")
        return
    if participant.is_in_room:
        await message.answer("Цей учасник уже в кімнаті.")
        return

    await room_service.start_room(session, message.bot, user, participant, settings)


def _label(user: User) -> str:
    if user.pseudonym_number is not None:
        return f"Анонім №{user.pseudonym_number}"
    return f"#{str(user.id)[-4:]}"
