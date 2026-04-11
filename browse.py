"""
handlers/browse.py
💤 = выход в меню (убрана кнопка "В главное меню")
При лайке — уведомление получателю
При взаимном лайке — кнопка с черновиком сообщения
Если анкет нет — сообщение с рефералкой
"""
import re
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

import database as db
from states import BrowseStates
from keyboards import browse_keyboard, main_menu, like_message_type_keyboard
from utils import send_profile_card
from config import FEMALE_FREE_DAILY_LIKES, MALE_FREE_WEEKLY_LIKES, ADMIN_USERNAME

router = Router()

BTN_LIKE     = "♥️"
BTN_LIKE_MSG = "💌"
BTN_DISLIKE  = "👎"
BTN_SLEEP    = "💤"   # выход в меню


# ─── Кнопка "написать" с черновиком ──────────────────────
def write_keyboard(username: str) -> InlineKeyboardMarkup:
    text = "Ассаляму алейкум. Я с ЛямАлиф Никах бота ✨"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"💬 Написать @{username}",
            url=f"https://t.me/{username}?text={text}"
        )
    ]])


# ─── Лимит лайков ────────────────────────────────────────
async def _check_like_limit(user):
    if user["is_premium"]:
        return True, ""
    if user["gender"] == "female":
        count = await db.get_today_likes(user["tg_id"])
        if count >= FEMALE_FREE_DAILY_LIKES:
            return False, (
                f"❗ Лимит {FEMALE_FREE_DAILY_LIKES} лайков/день исчерпан.\n\n"
                "Оформите Премиум для безлимита. ⭐"
            )
    else:
        count = await db.get_week_likes(user["tg_id"])
        if count >= MALE_FREE_WEEKLY_LIKES:
            return False, (
                f"❗ Лимит {MALE_FREE_WEEKLY_LIKES} лайков/неделю исчерпан.\n\n"
                f"Оформите Премиум у @{ADMIN_USERNAME} ⭐"
            )
    return True, ""


async def _inc_like_counter(user):
    if user["is_premium"]:
        return
    if user["gender"] == "female":
        await db.increment_today_likes(user["tg_id"])
    else:
        await db.increment_week_likes(user["tg_id"])


# ─── Показать анкету ─────────────────────────────────────
async def _show_next(bot: Bot, chat_id: int, user: dict, state: FSMContext):
    profile = await db.get_next_profile(user["tg_id"], user["gender"])
    if not profile:
        await db.reset_viewed(user["tg_id"])
        profile = await db.get_next_profile(user["tg_id"], user["gender"])

    if not profile:
        bot_info = await bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user['tg_id']}"
        await bot.send_message(
            chat_id,
            "😔 Анкеты закончились!\n\n"
            "Приглашайте друзей по реферальной ссылке и зарабатывайте:\n\n"
            f"🔗 <code>{ref_link}</code>\n\n"
            "За каждого приглашённого — <b>30% с их оплат</b> вам! 💰\n\n"
            "بِإِذْنِ اللَّهِ — всё в своё время 🌙",
            parse_mode="HTML",
            reply_markup=main_menu(user["gender"], True)
        )
        await state.clear()
        return

    photos     = await db.get_photos(profile["tg_id"])
    is_premium = bool(user["is_premium"])

    if not is_premium:
        if user["gender"] == "female":
            used  = await db.get_today_likes(user["tg_id"])
            extra = f"♥️ {used}/{FEMALE_FREE_DAILY_LIKES} сегодня"
        else:
            used  = await db.get_week_likes(user["tg_id"])
            extra = f"♥️ {used}/{MALE_FREE_WEEKLY_LIKES} на этой неделе"
    else:
        extra = "♥️ Безлимит ⭐"

    await state.update_data(current_profile_id=profile["tg_id"])
    await db.mark_viewed(user["tg_id"], profile["tg_id"])
    await state.set_state(BrowseStates.browsing)
    await send_profile_card(
        bot, chat_id, profile, photos,
        reply_markup=browse_keyboard(is_premium),
        extra_text=extra
    )


# ─── Уведомление о лайке получателю ─────────────────────
async def _notify_liked(bot: Bot, liker_id: int, target_id: int):
    """Сообщить target_id что его лайкнули — показать анкету лайкера."""
    try:
        liker_profile = await db.get_profile(liker_id)
        if not liker_profile:
            return
        liker_photos  = await db.get_photos(liker_id)
        liker_user    = await db.get_user(liker_id)

        # Уведомление
        await bot.send_message(
            target_id,
            "💌 <b>Ваша анкета кому-то понравилась!</b>\n\n"
            "Посмотрите кто это — может это ваша половинка? 🌙",
            parse_mode="HTML"
        )

        # Показываем анкету лайкера
        is_premium = bool(liker_user.get("is_premium"))
        await send_profile_card(
            bot, target_id, liker_profile, liker_photos,
            reply_markup=like_response_keyboard(liker_id)
        )
        await db.mark_like_notified(liker_id, target_id)
    except Exception:
        pass


def like_response_keyboard(liker_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="♥️ Лайк", callback_data=f"resp_like_{liker_id}"),
            InlineKeyboardButton(text="👎 Пропустить", callback_data=f"resp_skip_{liker_id}"),
        ]
    ])


# ─── Ответ на уведомление о лайке ────────────────────────
@router.callback_query(F.data.startswith("resp_like_"))
async def resp_like(call: CallbackQuery, bot: Bot):
    await call.answer()
    liker_id  = int(call.data.split("_")[-1])
    target_id = call.from_user.id

    await db.add_like(target_id, liker_id, 1)

    if await db.is_mutual_like(target_id, liker_id):
        await _notify_mutual(bot, target_id, liker_id)
    else:
        await call.message.answer("❤️ Лайк отправлен!")


@router.callback_query(F.data.startswith("resp_skip_"))
async def resp_skip(call: CallbackQuery):
    await call.answer("Пропущено")


# ─── Взаимный лайк ───────────────────────────────────────
async def _notify_mutual(bot: Bot, user_a: int, user_b: int):
    profile_a = await db.get_profile(user_a)
    profile_b = await db.get_profile(user_b)
    ua = await db.get_user(user_a)
    ub = await db.get_user(user_b)

    if ub.get("username"):
        try:
            await bot.send_message(
                user_a,
                f"🎉 <b>Взаимная симпатия!</b>\n\n"
                f"<b>{profile_b['name']}</b> тоже поставил(а) вам лайк!\n\n"
                "Общайтесь только через махрама 🤝",
                parse_mode="HTML",
                reply_markup=write_keyboard(ub["username"])
            )
        except Exception:
            pass

    if ua.get("username"):
        try:
            await bot.send_message(
                user_b,
                f"🎉 <b>Взаимная симпатия!</b>\n\n"
                f"<b>{profile_a['name']}</b> тоже поставил(а) вам лайк!\n\n"
                "Общайтесь только через махрама 🤝",
                parse_mode="HTML",
                reply_markup=write_keyboard(ua["username"])
            )
        except Exception:
            pass


# ─── Старт просмотра ─────────────────────────────────────
@router.message(F.text == "👀 Смотреть анкеты")
async def start_browsing(message: Message, state: FSMContext, bot: Bot):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start")
        return
    if not await db.get_profile(message.from_user.id):
        await message.answer("Сначала заполните анкету.")
        return
    await _show_next(bot, message.chat.id, user, state)


# ─── 💤 Выход в меню (вместо кнопки "Назад") ─────────────
@router.message(BrowseStates.browsing, F.text == BTN_SLEEP)
async def do_sleep(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer("Главное меню 🌙", reply_markup=main_menu(user["gender"], True))


# ─── ♥️ Лайк ─────────────────────────────────────────────
@router.message(BrowseStates.browsing, F.text == BTN_LIKE)
async def do_like(message: Message, state: FSMContext, bot: Bot):
    data      = await state.get_data()
    target_id = data.get("current_profile_id")
    if not target_id:
        return
    user = await db.get_user(message.from_user.id)
    ok, err = await _check_like_limit(user)
    if not ok:
        await message.answer(err)
        return

    await db.add_like(message.from_user.id, target_id, 1)
    await _inc_like_counter(user)

    if await db.is_mutual_like(message.from_user.id, target_id):
        await _notify_mutual(bot, message.from_user.id, target_id)
    else:
        # Уведомляем получателя о лайке
        await _notify_liked(bot, message.from_user.id, target_id)

    await _show_next(bot, message.chat.id, user, state)


# ─── 👎 Дизлайк ──────────────────────────────────────────
@router.message(BrowseStates.browsing, F.text == BTN_DISLIKE)
async def do_dislike(message: Message, state: FSMContext, bot: Bot):
    data      = await state.get_data()
    target_id = data.get("current_profile_id")
    if target_id:
        await db.add_like(message.from_user.id, target_id, -1)
    user = await db.get_user(message.from_user.id)
    await _show_next(bot, message.chat.id, user, state)


# ─── 💌 Лайк с сообщением (Премиум) ─────────────────────
@router.message(BrowseStates.browsing, F.text == BTN_LIKE_MSG)
async def like_with_message_start(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user["is_premium"]:
        await message.answer(f"⭐ Только для Премиум. Оформить: @{ADMIN_USERNAME}")
        return
    await message.answer("Выберите тип сообщения:", reply_markup=like_message_type_keyboard())
    await state.set_state(BrowseStates.like_message)


@router.callback_query(BrowseStates.like_message, F.data.startswith("likemsg_"))
async def like_message_type_cb(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    action = call.data.split("_", 1)[1]
    if action == "cancel":
        await state.set_state(BrowseStates.browsing)
        user = await db.get_user(call.from_user.id)
        await call.message.answer("Отменено.", reply_markup=browse_keyboard(True))
        return
    await state.update_data(like_msg_type=action)
    prompts = {
        "text":       "✍️ Напишите текст:",
        "audio":      "🎤 Отправьте голосовое:",
        "video_note": "🎥 Отправьте видеокружок:",
    }
    await call.message.answer(prompts[action])


@router.message(BrowseStates.like_message)
async def receive_like_message(message: Message, state: FSMContext, bot: Bot):
    data      = await state.get_data()
    msg_type  = data.get("like_msg_type")
    target_id = data.get("current_profile_id")
    if not msg_type:
        return

    msg_text = msg_file = None
    if msg_type == "text":
        if not message.text:
            await message.answer("Отправьте текст:")
            return
        if re.search(r"@\w+|https?://|t\.me/", message.text, re.I):
            await message.answer("⛔ Без ссылок.")
            return
        msg_text = message.text.strip()
    elif msg_type == "audio":
        if not message.voice:
            await message.answer("Отправьте голосовое:")
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

    await db.add_like(message.from_user.id, target_id, 1,
                      msg_text=msg_text, msg_file=msg_file, msg_type=msg_type)
    await _inc_like_counter(user)
    await message.answer("❤️ Лайк с сообщением отправлен!")

    if await db.is_mutual_like(message.from_user.id, target_id):
        await _notify_mutual(bot, message.from_user.id, target_id)
    else:
        await _notify_liked(bot, message.from_user.id, target_id)

    await state.set_state(BrowseStates.browsing)
    await _show_next(bot, message.chat.id, user, state)
    
