"""
handlers/misc.py — симпатии, моя анкета, премиум, помощь, админ-команды
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import database as db
from keyboards import (
    main_menu, likes_menu_keyboard, premium_keyboard,
    mutual_like_keyboard
)
from utils import send_profile_card, format_profile
from config import ADMIN_ID, ADMIN_USERNAME, PREMIUM_PRICE_RUB

router = Router()


# ─── Моя анкета ───────────────────────────────────────────

@router.message(F.text == "👤 Моя анкета")
async def my_profile(message: Message, bot: Bot):
    profile = await db.get_profile(message.from_user.id)
    if not profile:
        await message.answer("У вас нет анкеты. Нажмите /start.")
        return
    photos = await db.get_photos(message.from_user.id)
    await send_profile_card(
        bot, message.chat.id, profile, photos,
        show_username=True,
        extra_text="☝️ Так видят вашу анкету другие"
    )


# ─── Симпатии ─────────────────────────────────────────────

@router.message(F.text == "❤️ Мои симпатии")
async def my_likes(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    await message.answer(
        "💌 Ваши симпатии:",
        reply_markup=likes_menu_keyboard(user["gender"], bool(user["is_premium"]))
    )


@router.callback_query(F.data == "likes_mutual")
async def show_mutual_likes(call: CallbackQuery, bot: Bot):
    await call.answer()
    mutuals = await db.get_mutual_likes(call.from_user.id)

    if not mutuals:
        await call.message.answer("Пока нет взаимных симпатий. Продолжайте смотреть анкеты! 🌙")
        return

    await call.message.answer(f"🔁 Взаимных симпатий: {len(mutuals)}\n")
    for m in mutuals:
        text = (
            f"<b>{m['name']}</b>, {m['age']} лет\n"
            f"📍 {m['city']}"
        )
        kb = mutual_like_keyboard(m["username"]) if m.get("username") else None
        await call.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "likes_incoming")
async def show_incoming_likes(call: CallbackQuery, bot: Bot):
    await call.answer()
    user = await db.get_user(call.from_user.id)

    # Парень без премиума не видит входящие
    if user["gender"] == "male" and not user["is_premium"]:
        await call.answer("⭐ Доступно только с Премиум.", show_alert=True)
        return

    incoming = await db.get_incoming_likes(call.from_user.id)
    if not incoming:
        await call.message.answer("Пока никто не поставил вам лайк. Не сдавайтесь! 🌙")
        return

    await call.message.answer(f"💌 Вас лайкнули: {len(incoming)} чел.\n")
    for like in incoming:
        text = f"<b>{like['name']}</b>, {like['age']} лет, {like['city']}"
        if like.get("message_text"):
            text += f"\n\n💬 «{like['message_text']}»"
        kb = mutual_like_keyboard(like["username"]) if like.get("username") else None
        await call.message.answer(text, parse_mode="HTML", reply_markup=kb)

        # Аудио или видеокружок к лайку
        if like.get("message_file_id"):
            if like.get("message_type") == "audio":
                await bot.send_voice(call.message.chat.id, like["message_file_id"])
            elif like.get("message_type") == "video_note":
                await bot.send_video_note(call.message.chat.id, like["message_file_id"])


@router.callback_query(F.data == "likes_need_premium")
async def likes_need_premium(call: CallbackQuery):
    await call.answer(
        "⭐ Просмотр входящих лайков доступен только с Премиум-подпиской.",
        show_alert=True
    )


# ─── Премиум ──────────────────────────────────────────────

@router.message(F.text == "⭐ Премиум")
async def premium_info(message: Message):
    user = await db.get_user(message.from_user.id)
    if user and user["is_premium"]:
        until = user.get("premium_until", "—")
        await message.answer(
            f"✅ У вас активна Премиум-подписка!\n"
            f"Действует до: <b>{until}</b>",
            parse_mode="HTML"
        )
        return

    gender = user["gender"] if user else "male"

    if gender == "female":
        text = (
            "⭐ <b>Премиум для девушек — 700₽/мес</b>\n\n"
            "✅ Безлимитные лайки (вместо 15/день)\n"
            "✅ Ваша анкета показывается чаще\n"
            "✅ Вернуться к предыдущей анкете\n"
            "✅ Лайк с текстом, аудио или видеокружком\n"
            "✅ Значок «Премиум ✅» в анкете"
        )
    else:
        text = (
            "⭐ <b>Премиум для мужчин — 700₽/мес</b>\n\n"
            "✅ Безлимитные лайки (вместо 30/неделю)\n"
            "✅ Просмотр кто вас лайкнул\n"
            "✅ Просмотр взаимных симпатий с контактами\n"
            "✅ Вернуться к предыдущей анкете\n"
            "✅ Лайк с текстом, аудио или видеокружком\n"
            "✅ Значок «Премиум ✅» в анкете\n\n"
            f"Для оплаты — напишите @{ADMIN_USERNAME}"
        )

    await message.answer(text, parse_mode="HTML", reply_markup=premium_keyboard())


# ─── Помощь ───────────────────────────────────────────────

@router.message(F.text == "ℹ️ Помощь")
async def help_cmd(message: Message):
    await message.answer(
        "🌙 <b>ЛямАлиф Никях — помощь</b>\n\n"
        "👀 <b>Смотреть анкеты</b> — просматривайте анкеты и ставьте лайки\n"
        "❤️ <b>Мои симпатии</b> — взаимные симпатии и входящие лайки\n"
        "👤 <b>Моя анкета</b> — посмотреть как выглядит ваша анкета\n"
        "✏️ <b>Изменить анкету</b> — редактировать информацию\n"
        "⭐ <b>Премиум</b> — расширенные возможности\n\n"
        "По всем вопросам: @rau_ff\n\n"
        "بَارَكَ اللَّهُ فِيكُم 🤲",
        parse_mode="HTML"
    )


# ─── ADMIN КОМАНДЫ ────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


@router.message(Command("ban"))
async def admin_ban(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /ban <user_id>")
        return
    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("Некорректный ID.")
        return
    await db.ban_user(target_id)
    await message.answer(f"✅ Пользователь {target_id} заблокирован.")


@router.message(Command("unban"))
async def admin_unban(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /unban <user_id>")
        return
    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("Некорректный ID.")
        return
    await db.unban_user(target_id)
    await message.answer(f"✅ Пользователь {target_id} разблокирован.")


@router.message(Command("premium"))
async def admin_give_premium(message: Message):
    """
    /premium <user_id> <YYYY-MM-DD>
    Пример: /premium 123456789 2025-06-01
    """
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Использование: /premium <user_id> <YYYY-MM-DD>")
        return
    try:
        target_id = int(args[1])
        until_date = args[2]
    except (ValueError, IndexError):
        await message.answer("Некорректные аргументы.")
        return
    await db.set_premium(target_id, until_date)
    await message.answer(f"✅ Премиум до {until_date} выдан пользователю {target_id}.")


@router.message(Command("stats"))
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db_conn:
        async with db_conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=0") as c:
            total = (await c.fetchone())[0]
        async with db_conn.execute("SELECT COUNT(*) FROM profiles") as c:
            profiles = (await c.fetchone())[0]
        async with db_conn.execute("SELECT COUNT(*) FROM users WHERE is_premium=1") as c:
            premium = (await c.fetchone())[0]
        async with db_conn.execute("SELECT COUNT(*) FROM users WHERE gender='male'") as c:
            males = (await c.fetchone())[0]
        async with db_conn.execute("SELECT COUNT(*) FROM users WHERE gender='female'") as c:
            females = (await c.fetchone())[0]
        async with db_conn.execute("SELECT COUNT(*) FROM likes WHERE value=1") as c:
            total_likes = (await c.fetchone())[0]

    await message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {total}\n"
        f"📝 Заполнили анкету: {profiles}\n"
        f"⭐ Премиум: {premium}\n"
        f"👨 Мужчин: {males}\n"
        f"👩 Женщин: {females}\n"
        f"❤️ Всего лайков: {total_likes}",
        parse_mode="HTML"
    )


@router.message(Command("broadcast"))
async def admin_broadcast(message: Message, bot: Bot):
    """
    /broadcast <текст> — рассылка всем активным пользователям
    """
    if not is_admin(message.from_user.id):
        return
    text = message.text.partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /broadcast <текст>")
        return

    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db_conn:
        async with db_conn.execute(
            "SELECT tg_id FROM users WHERE is_banned=0"
        ) as cur:
            rows = await cur.fetchall()

    sent = 0
    failed = 0
    for (uid,) in rows:
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await message.answer(f"✅ Рассылка завершена: {sent} доставлено, {failed} ошибок.")
