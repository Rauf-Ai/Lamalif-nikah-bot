"""
handlers/browse.py — просмотр анкет, лайки, дизлайки
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
from states import BrowseStates
from keyboards import (
    browse_keyboard, main_menu, like_message_type_keyboard
)
from utils import send_profile_card
from config import (
    FEMALE_FREE_DAILY_LIKES, MALE_FREE_WEEKLY_LIKES, ADMIN_USERNAME
)

router = Router()


async def _check_like_limit(user: dict) -> tuple[bool, str]:
    """Проверяет лимит лайков. Возвращает (ok, error_message)."""
    tg_id = user["tg_id"]
    gender = user["gender"]
    is_premium = user["is_premium"]

    if is_premium:
        return True, ""

    if gender == "female":
        count = await db.get_today_likes(tg_id)
        if count >= FEMALE_FREE_DAILY_LIKES:
            return False, (
                f"❗ Дневной лимит лайков исчерпан ({FEMALE_FREE_DAILY_LIKES}/день).\n"
                "Ждите следующего дня или оформите Премиум для безлимита."
            )
    else:  # male
        count = await db.get_week_likes(tg_id)
        if count >= MALE_FREE_WEEKLY_LIKES:
            return False, (
                f"❗ Недельный лимит лайков исчерпан ({MALE_FREE_WEEKLY_LIKES}/неделю).\n"
                f"Оформите Премиум (700₽/мес) у @{ADMIN_USERNAME} для безлимита."
            )
    return True, ""


async def _show_next(bot: Bot, chat_id: int, user: dict, state: FSMContext):
    """Показать следующую анкету."""
    profile = await db.get_next_profile(user["tg_id"], user["gender"])

    if not profile:
        # Все анкеты просмотрены — сброс и повтор
        await db.reset_viewed(user["tg_id"])
        profile = await db.get_next_profile(user["tg_id"], user["gender"])

    if not profile:
        await bot.send_message(
            chat_id,
            "😔 Пока нет анкет для просмотра. Загляните позже — "
            "новые пользователи регистрируются каждый день!\n\n"
            "بِإِذْنِ اللَّهِ — всё в своё время 🌙"
        )
        await state.clear()
        return

    photos = await db.get_photos(profile["tg_id"])
    is_premium = bool(user["is_premium"])

    await state.update_data(current_profile_id=profile["tg_id"])
    await db.mark_viewed(user["tg_id"], profile["tg_id"])
    await state.set_state(BrowseStates.browsing)

    await send_profile_card(
        bot, chat_id, profile, photos,
        reply_markup=browse_keyboard(is_premium, user["gender"])
    )


# ─── Вход в режим просмотра ───────────────────────────────

@router.message(F.text == "👀 Смотреть анкеты")
async def start_browsing(message: Message, state: FSMContext, bot: Bot):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start")
        return

    profile = await db.get_profile(message.from_user.id)
    if not profile:
        await message.answer("Сначала заполните анкету.")
        return

    await _show_next(bot, message.chat.id, user, state)


# ─── Лайк ─────────────────────────────────────────────────

@router.callback_query(BrowseStates.browsing, F.data == "browse_like")
async def do_like(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer("❤️")
    data = await state.get_data()
    target_id = data.get("current_profile_id")
    if not target_id:
        return

    user = await db.get_user(call.from_user.id)
    ok, err = await _check_like_limit(user)
    if not ok:
        await call.message.answer(err)
        return

    await db.add_like(call.from_user.id, target_id, 1)

    # Зачёт лимита
    if user["gender"] == "female":
        await db.increment_today_likes(call.from_user.id)
    else:
        await db.increment_week_likes(call.from_user.id)

    # Взаимный лайк?
    if await db.is_mutual_like(call.from_user.id, target_id):
        await _notify_mutual(bot, call.from_user.id, target_id)

    await _show_next(bot, call.message.chat.id, user, state)


# ─── Дизлайк ──────────────────────────────────────────────

@router.callback_query(BrowseStates.browsing, F.data == "browse_dislike")
async def do_dislike(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer("👎")
    data = await state.get_data()
    target_id = data.get("current_profile_id")
    if target_id:
        await db.add_like(call.from_user.id, target_id, -1)

    user = await db.get_user(call.from_user.id)
    await _show_next(bot, call.message.chat.id, user, state)


# ─── Вернуться назад (Премиум) ────────────────────────────

@router.callback_query(BrowseStates.browsing, F.data == "browse_back")
async def do_back(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    user = await db.get_user(call.from_user.id)
    if not user["is_premium"]:
        await call.answer("⭐ Эта функция доступна только с Премиум.", show_alert=True)
        return

    data = await state.get_data()
    # Ищем предпоследний просмотренный
    last_id = await db.get_last_viewed(call.from_user.id)
    if not last_id:
        await call.answer("Нет предыдущей анкеты.", show_alert=True)
        return

    await db.unview_last(call.from_user.id, last_id)
    await state.update_data(current_profile_id=None)
    await _show_next(bot, call.message.chat.id, user, state)


# ─── Лайк с сообщением (Премиум) ─────────────────────────

@router.callback_query(BrowseStates.browsing, F.data == "browse_like_msg")
async def like_with_message_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    user = await db.get_user(call.from_user.id)
    if not user["is_premium"]:
        await call.answer("⭐ Только для Премиум-пользователей.", show_alert=True)
        return

    await call.message.answer(
        "Выберите тип сообщения к лайку:",
        reply_markup=like_message_type_keyboard()
    )
    await state.set_state(BrowseStates.like_message)


@router.callback_query(BrowseStates.like_message, F.data.startswith("likemsg_"))
async def like_message_type(call: CallbackQuery, state: FSMContext):
    await call.answer()
    action = call.data.split("_", 1)[1]

    if action == "cancel":
        await state.set_state(BrowseStates.browsing)
        await call.message.answer("Отменено. Продолжайте просматривать анкеты.")
        return

    await state.update_data(like_msg_type=action)
    prompts = {
        "text": "✍️ Напишите текстовое сообщение к лайку:",
        "audio": "🎤 Отправьте голосовое сообщение:",
        "video_note": "🎥 Отправьте видеокружок:",
    }
    await call.message.answer(prompts[action])


@router.message(BrowseStates.like_message)
async def receive_like_message(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    msg_type = data.get("like_msg_type")
    target_id = data.get("current_profile_id")

    msg_text = None
    msg_file = None

    if msg_type == "text":
        if not message.text:
            await message.answer("Отправьте текст:")
            return
        if contains_links_or_mentions(message.text):
            await message.answer("⛔ Сообщение не должно содержать ссылки.")
            return
        msg_text = message.text.strip()
    elif msg_type == "audio":
        if not message.voice:
            await message.answer("Отправьте голосовое сообщение:")
            return
        msg_file = message.voice.file_id
    elif msg_type == "video_note":
        if not message.video_note:
            await message.answer("Отправьте видеокружок:")
            return
        msg_file = message.video_note.file_id

    user = await db.get_user(message.from_user.id)
    ok, err = await _check_like_limit(user)
    if not ok:
        await message.answer(err)
        await state.set_state(BrowseStates.browsing)
        return

    await db.add_like(
        message.from_user.id, target_id, 1,
        msg_text=msg_text, msg_file=msg_file, msg_type=msg_type
    )

    if user["gender"] == "female":
        await db.increment_today_likes(message.from_user.id)
    else:
        await db.increment_week_likes(message.from_user.id)

    await message.answer("❤️ Лайк с сообщением отправлен!")

    if await db.is_mutual_like(message.from_user.id, target_id):
        await _notify_mutual(bot, message.from_user.id, target_id)

    await state.set_state(BrowseStates.browsing)
    await _show_next(bot, message.chat.id, user, state)


# ─── Уведомление о взаимном лайке ────────────────────────

async def _notify_mutual(bot: Bot, user_a: int, user_b: int):
    from keyboards import mutual_like_keyboard

    profile_a = await db.get_profile(user_a)
    profile_b = await db.get_profile(user_b)
    user_a_rec = await db.get_user(user_a)
    user_b_rec = await db.get_user(user_b)

    # Уведомление user_a
    if user_b_rec.get("username"):
        try:
            await bot.send_message(
                user_a,
                f"🎉 Взаимная симпатия!\n"
                f"<b>{profile_b['name']}</b> тоже поставил(а) вам лайк!\n\n"
                "Общайтесь только через махрама 🤝",
                parse_mode="HTML",
                reply_markup=mutual_like_keyboard(user_b_rec["username"])
            )
        except Exception:
            pass

    # Уведомление user_b
    if user_a_rec.get("username"):
        try:
            await bot.send_message(
                user_b,
                f"🎉 Взаимная симпатия!\n"
                f"<b>{profile_a['name']}</b> тоже поставил(а) вам лайк!\n\n"
                "Общайтесь только через махрама 🤝",
                parse_mode="HTML",
                reply_markup=mutual_like_keyboard(user_a_rec["username"])
            )
        except Exception:
            pass


def contains_links_or_mentions(text: str) -> bool:
    import re
    patterns = [r"@\w+", r"https?://", r"t\.me/"]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)
