"""
handlers/admin.py — удобная админ-панель через кнопки
Вызов: /admin
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from config import ADMIN_ID

router = Router()


# ─── FSM ──────────────────────────────────────────────────
class AdminStates(StatesGroup):
    waiting_user_search   = State()   # поиск пользователя
    waiting_premium_days  = State()   # кол-во дней премиума
    waiting_broadcast_msg = State()   # текст рассылки
    waiting_message_text  = State()   # сообщение конкретному юзеру
    user_selected         = State()   # пользователь выбран, ждём действие


# ─── Проверка админа ──────────────────────────────────────
def is_admin(user_id: int) -> bool:
    result = user_id == ADMIN_ID
    print(f"🔍 Проверка админа: user_id={user_id}, ADMIN_ID={ADMIN_ID}, result={result}")
    return result


# ─── Главная панель ───────────────────────────────────────
def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Найти пользователя", callback_data="adm_find_user")],
        [InlineKeyboardButton(text="📊 Общая статистика",   callback_data="adm_stats")],
        [InlineKeyboardButton(text="📢 Рассылка всем",      callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="⭐ Все премиум-юзеры",  callback_data="adm_list_premium")],
        [InlineKeyboardButton(text="🚫 Все забаненные",     callback_data="adm_list_banned")],
        [InlineKeyboardButton(text="🆕 Новые за сегодня",   callback_data="adm_new_today")],
        [InlineKeyboardButton(text="❌ Закрыть",            callback_data="adm_close")],
    ])


def user_actions_keyboard(tg_id: int, is_banned: bool, is_premium: bool) -> InlineKeyboardMarkup:
    ban_btn = (
        InlineKeyboardButton(text="✅ Разбанить", callback_data=f"adm_unban_{tg_id}")
        if is_banned else
        InlineKeyboardButton(text="🚫 Забанить",  callback_data=f"adm_ban_{tg_id}")
    )
    prem_btn = (
        InlineKeyboardButton(text="❌ Снять Премиум", callback_data=f"adm_revoke_prem_{tg_id}")
        if is_premium else
        InlineKeyboardButton(text="⭐ Дать Премиум",  callback_data=f"adm_give_prem_{tg_id}")
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [ban_btn],
        [prem_btn],
        [InlineKeyboardButton(text="💬 Написать сообщение", callback_data=f"adm_msg_{tg_id}")],
        [InlineKeyboardButton(text="🗑 Удалить анкету",     callback_data=f"adm_del_profile_{tg_id}")],
        [InlineKeyboardButton(text="🔙 Назад",              callback_data="adm_back")],
    ])


def premium_days_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    days_options = [2, 7, 30, 90, 180, 365]
    rows = []
    row = []
    for d in days_options:
        row.append(InlineKeyboardButton(text=f"{d} дн.", callback_data=f"adm_prem_days_{tg_id}_{d}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✏️ Своё кол-во дней", callback_data=f"adm_prem_custom_{tg_id}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"adm_user_back_{tg_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── /admin ───────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    print(f"🔥 Команда /admin получена от {message.from_user.id}")
    print(f"ADMIN_ID из config: {ADMIN_ID}")
    
    if not is_admin(message.from_user.id):
        print(f"❌ Доступ запрещён: {message.from_user.id} != {ADMIN_ID}")
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    
    await state.clear()
    await message.answer(
        "🛠 <b>Админ-панель ЛямАлиф Никях</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard()
    )


@router.callback_query(F.data == "adm_close")
async def adm_close(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await state.clear()
    await call.message.delete()


@router.callback_query(F.data == "adm_back")
async def adm_back(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text(
        "🛠 <b>Админ-панель ЛямАлиф Никях</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard()
    )


# ─── Общая статистика ─────────────────────────────────────
@router.callback_query(F.data == "adm_stats")
async def adm_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await call.answer()
    import aiosqlite
    from database import DB_PATH
    from datetime import date
    today = date.today().isoformat()

    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("SELECT COUNT(*) FROM users") as c:
            total = (await c.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=0") as c:
            active = (await c.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM profiles") as c:
            profiles = (await c.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM users WHERE is_premium=1") as c:
            premium = (await c.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM users WHERE gender='male' AND is_banned=0") as c:
            males = (await c.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM users WHERE gender='female' AND is_banned=0") as c:
            females = (await c.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=1") as c:
            banned = (await c.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM likes WHERE value=1") as c:
            total_likes = (await c.fetchone())[0]
        async with conn.execute(
            "SELECT COUNT(*) FROM users WHERE DATE(created_at)=?", (today,)
        ) as c:
            new_today = (await c.fetchone())[0]
        async with conn.execute(
            "SELECT COUNT(*) FROM likes WHERE DATE(created_at)=? AND value=1", (today,)
        ) as c:
            likes_today = (await c.fetchone())[0]

    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total}</b>\n"
        f"✅ Активных: <b>{active}</b>\n"
        f"🚫 Забанено: <b>{banned}</b>\n"
        f"📝 Заполнили анкету: <b>{profiles}</b>\n"
        f"⭐ Премиум: <b>{premium}</b>\n\n"
        f"👨 Мужчин: <b>{males}</b>\n"
        f"👩 Женщин: <b>{females}</b>\n\n"
        f"❤️ Лайков всего: <b>{total_likes}</b>\n"
        f"❤️ Лайков сегодня: <b>{likes_today}</b>\n"
        f"🆕 Новых сегодня: <b>{new_today}</b>"
    )
    await call.message.edit_text(text, parse_mode="HTML",
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                      InlineKeyboardButton(text="🔙 Назад", callback_data="adm_back")
                                  ]]))


# ─── Новые за сегодня ─────────────────────────────────────
@router.callback_query(F.data == "adm_new_today")
async def adm_new_today(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await call.answer()
    import aiosqlite
    from database import DB_PATH
    from datetime import date
    today = date.today().isoformat()

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("""
            SELECT u.tg_id, u.username, u.gender, p.name, p.age, p.city
            FROM users u LEFT JOIN profiles p ON p.tg_id=u.tg_id
            WHERE DATE(u.created_at)=?
            ORDER BY u.created_at DESC LIMIT 20
        """, (today,)) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    if not rows:
        text = "🆕 Сегодня новых пользователей нет."
    else:
        lines = [f"🆕 <b>Новые за сегодня ({len(rows)}):</b>\n"]
        for r in rows:
            gender_icon = "👨" if r["gender"] == "male" else "👩"
            name = r["name"] or "—"
            uname = f"@{r['username']}" if r["username"] else f"ID:{r['tg_id']}"
            age = r["age"] or "?"
            city = r["city"] or "?"
            lines.append(f"{gender_icon} {name}, {age} лет, {city} — {uname}")
        text = "\n".join(lines)

    await call.message.edit_text(text, parse_mode="HTML",
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                      InlineKeyboardButton(text="🔙 Назад", callback_data="adm_back")
                                  ]]))


# ─── Список премиум-пользователей ─────────────────────────
@router.callback_query(F.data == "adm_list_premium")
async def adm_list_premium(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await call.answer()
    import aiosqlite
    from database import DB_PATH

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("""
            SELECT u.tg_id, u.username, u.premium_until, p.name, p.age
            FROM users u LEFT JOIN profiles p ON p.tg_id=u.tg_id
            WHERE u.is_premium=1
            ORDER BY u.premium_until ASC
        """) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    if not rows:
        text = "⭐ Нет активных премиум-пользователей."
    else:
        lines = [f"⭐ <b>Премиум-пользователи ({len(rows)}):</b>\n"]
        for r in rows:
            uname = f"@{r['username']}" if r["username"] else f"ID:{r['tg_id']}"
            name = r["name"] or "—"
            until = r["premium_until"] or "?"
            lines.append(f"• {name} {uname} — до {until}")
        text = "\n".join(lines)

    await call.message.edit_text(text, parse_mode="HTML",
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                      InlineKeyboardButton(text="🔙 Назад", callback_data="adm_back")
                                  ]]))


# ─── Список забаненных ────────────────────────────────────
@router.callback_query(F.data == "adm_list_banned")
async def adm_list_banned(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await call.answer()
    import aiosqlite
    from database import DB_PATH

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("""
            SELECT u.tg_id, u.username, p.name
            FROM users u LEFT JOIN profiles p ON p.tg_id=u.tg_id
            WHERE u.is_banned=1
        """) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    if not rows:
        text = "✅ Забаненных пользователей нет."
    else:
        lines = [f"🚫 <b>Забаненные ({len(rows)}):</b>\n"]
        for r in rows:
            uname = f"@{r['username']}" if r["username"] else f"ID:{r['tg_id']}"
            name = r["name"] or "—"
            lines.append(f"• {name} — {uname}")
        text = "\n".join(lines)

    await call.message.edit_text(text, parse_mode="HTML",
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                      InlineKeyboardButton(text="🔙 Назад", callback_data="adm_back")
                                  ]]))


# ─── Поиск пользователя ───────────────────────────────────
@router.callback_query(F.data == "adm_find_user")
async def adm_find_user_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await call.answer()
    await call.message.edit_text(
        "👤 Введите <b>@username</b> или <b>числовой ID</b> пользователя:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data="adm_back")
        ]])
    )
    await state.set_state(AdminStates.waiting_user_search)


@router.message(AdminStates.waiting_user_search)
async def adm_user_search(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён")
        return

    query = message.text.strip().lstrip("@")
    user = None

    import aiosqlite
    from database import DB_PATH

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        # Поиск по username
        async with conn.execute(
            "SELECT * FROM users WHERE LOWER(username)=LOWER(?)", (query,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                user = dict(row)

        # Поиск по ID если не нашли
        if not user and query.isdigit():
            async with conn.execute(
                "SELECT * FROM users WHERE tg_id=?", (int(query),)
            ) as cur:
                row = await cur.fetchone()
                if row:
                    user = dict(row)

    if not user:
        await message.answer(
            "❌ Пользователь не найден. Попробуйте ещё раз или /admin для отмены."
        )
        return

    await state.clear()
    await _show_user_card(message, bot, user)


async def _show_user_card(message_or_call, bot: Bot, user: dict, edit: bool = False):
    import aiosqlite
    from database import DB_PATH

    tg_id = user["tg_id"]
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM profiles WHERE tg_id=?", (tg_id,)
        ) as cur:
            profile = await cur.fetchone()
            profile = dict(profile) if profile else {}

        async with conn.execute(
            "SELECT COUNT(*) FROM likes WHERE from_id=? AND value=1", (tg_id,)
        ) as cur:
            likes_given = (await cur.fetchone())[0]

        async with conn.execute(
            "SELECT COUNT(*) FROM likes WHERE to_id=? AND value=1", (tg_id,)
        ) as cur:
            likes_received = (await cur.fetchone())[0]

        async with conn.execute(
            "SELECT COUNT(*) FROM referrals WHERE referred_by=?", (tg_id,)
        ) as cur:
            ref_count = (await cur.fetchone())[0]

    gender_icon = "👨" if user["gender"] == "male" else "👩"
    uname = f"@{user['username']}" if user["username"] else "нет username"
    name = profile.get("name", "—")
    age = profile.get("age", "—")
    city = profile.get("city", "—")
    banned = "🚫 Да" if user["is_banned"] else "✅ Нет"
    premium = f"⭐ до {user['premium_until']}" if user["is_premium"] else "❌ Нет"
    joined = user.get("created_at", "?")[:10]

    text = (
        f"{gender_icon} <b>{name}</b>, {age} лет\n"
        f"📍 {city}\n"
        f"🔗 {uname}\n"
        f"🆔 <code>{tg_id}</code>\n\n"
        f"📅 Регистрация: {joined}\n"
        f"🚫 Бан: {banned}\n"
        f"⭐ Премиум: {premium}\n\n"
        f"❤️ Поставил лайков: {likes_given}\n"
        f"💌 Получил лайков: {likes_received}\n"
        f"👥 Рефералов: {ref_count}"
    )
    kb = user_actions_keyboard(tg_id, bool(user["is_banned"]), bool(user["is_premium"]))

    if isinstance(message_or_call, Message):
        await message_or_call.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message_or_call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


# ─── Бан / разбан ────────────────────────────────────────
@router.callback_query(F.data.startswith("adm_ban_"))
async def adm_ban(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await call.answer()
    tg_id = int(call.data.split("_")[-1])
    await db.ban_user(tg_id)
    try:
        await bot.send_message(tg_id, "🚫 Ваш аккаунт заблокирован за нарушение правил.")
    except Exception:
        pass
    user = await db.get_user(tg_id)
    await call.answer("✅ Пользователь забанен", show_alert=True)
    await _show_user_card(call, bot, user, edit=True)


@router.callback_query(F.data.startswith("adm_unban_"))
async def adm_unban(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await call.answer()
    tg_id = int(call.data.split("_")[-1])
    await db.unban_user(tg_id)
    try:
        await bot.send_message(tg_id, "✅ Ваш аккаунт разблокирован.")
    except Exception:
        pass
    user = await db.get_user(tg_id)
    await call.answer("✅ Пользователь разбанен", show_alert=True)
    await _show_user_card(call, bot, user, edit=True)


# ─── Премиум ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("adm_give_prem_"))
async def adm_give_prem(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await call.answer()
    tg_id = int(call.data.split("_")[-1])
    await call.message.edit_text(
        f"⭐ Выберите срок Премиума для пользователя <code>{tg_id}</code>:",
        parse_mode="HTML",
        reply_markup=premium_days_keyboard(tg_id)
    )


@router.callback_query(F.data.startswith("adm_prem_days_"))
async def adm_prem_days(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await call.answer()
    # adm_prem_days_{tg_id}_{days}
    parts = call.data.split("_")
    tg_id = int(parts[-2])
    days = int(parts[-1])

    from datetime import date, timedelta
    user = await db.get_user(tg_id)
    if user and user.get("is_premium") and user.get("premium_until"):
        try:
            base = date.fromisoformat(user["premium_until"])
            if base < date.today():
                base = date.today()
        except ValueError:
            base = date.today()
    else:
        base = date.today()

    until = (base + timedelta(days=days)).isoformat()
    await db.set_premium(tg_id, until)

    try:
        await bot.send_message(
            tg_id,
            f"🎉 Вам выдан <b>Premium на {days} дней</b>!\n"
            f"Действует до: <b>{until}</b>\n\n"
            "Теперь ваша анкета в топе! ⭐",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await call.answer(f"✅ Premium на {days} дн. выдан", show_alert=True)
    user = await db.get_user(tg_id)
    await _show_user_card(call, bot, user, edit=True)


@router.callback_query(F.data.startswith("adm_prem_custom_"))
async def adm_prem_custom(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await call.answer()
    tg_id = int(call.data.split("_")[-1])
    await state.update_data(premium_target_id=tg_id)
    await call.message.edit_text(
        f"✏️ Введите количество дней Премиума для <code>{tg_id}</code>:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"adm_user_back_{tg_id}")
            ]
