"""
handlers/browse.py — просмотр анкет, лайки, дизлайки
"""

import re
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import database as db
from states import BrowseStates
from keyboards import browse_keyboard, main_menu, like_message_type_keyboard, mutual_like_keyboard
from utils import send_profile_card
from config import FEMALE_FREE_DAILY_LIKES, MALE_FREE_WEEKLY_LIKES, ADMIN_USERNAME

router = Router()

BTN_LIKE      = "♥️"
BTN_LIKE_MSG  = "💌"
BTN_DISLIKE   = "👎"
BTN_SKIP      = "💤"
BTN_BACK_MENU = "🔙 В главное меню"

async def _check_like_limit(user):
    tg_id = user["tg_id"]
    if user["is_premium"]:
        return True, ""
    if user["gender"] == "female":
        count = await db.get_today_likes(tg_id)
        if count >= FEMALE_FREE_DAILY_LIKES:
            return False, f"❗ Лимит {FEMALE_FREE_DAILY_LIKES} лайков/день исчерпан.\n\nОформите Премиум для безлимита. ⭐"
    else:
        count = await db.get_week_likes(tg_id)
        if count >= MALE_FREE_WEEKLY_LIKES:
            return False, f"❗ Лимит {MALE_FREE_WEEKLY_LIKES} лайков/неделю исчерпан.\n\nПремиум (700₽/мес) у @{ADMIN_USERNAME} ⭐"
    return True, ""

async def _inc_like_counter(user):
    if user["is_premium"]:
        return
    if user["gender"] == "female":
        await db.increment_today_likes(user["tg_id"])
    else:
        await db.increment_week_likes(user["tg_id"])

async def _show_next(bot, chat_id, user, state):
    profile = await db.get_next_profile(user["tg_id"], user["gender"])
    if not profile:
        await db.reset_viewed(user["tg_id"])
        profile = await db.get_next_profile(user["tg_id"], user["gender"])
    if not profile:
        await bot.send_message(chat_id, "😔 Анкеты закончились. Загляните позже! 🌙",
                               reply_markup=main_menu(user["gender"], True))
        await state.clear()
        return
    photos = await db.get_photos(profile["tg_id"])
    is_premium = bool(user["is_premium"])
    if not is_premium:
        if user["gender"] == "female":
            used = await db.get_today_likes(user["tg_id"])
            extra = f"♥️ {used}/{FEMALE_FREE_DAILY_LIKES} сегодня"
        else:
            used = await db.get_week_likes(user["tg_id"])
            extra = f"♥️ {used}/{MALE_FREE_WEEKLY_LIKES} на этой неделе"
    else:
        extra = "♥️ Безлимит ⭐"
    await state.update_data(current_profile_id=profile["tg_id"])
    await db.mark_viewed(user["tg_id"], profile["tg_id"])
    await state.set_state(BrowseStates.browsing)
    await send_profile_card(bot, chat_id, profile, photos,
                            reply_markup=browse_keyboard(is_premium),
                            extra_text=extra)

@router.message(F.text == "👀 Смотреть анкеты")
async def start_browsing(message: Message, state: FSMContext, bot: Bot):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start"); return
    if not await db.get_profile(message.from_user.id):
        await message.answer("Сначала заполните анкету."); return
    await _show_next(bot, message.chat.id, user, state)

@router.message(BrowseStates.browsing, F.text == BTN_BACK_MENU)
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer("Главное меню 🌙", reply_markup=main_menu(user["gender"], True))

@router.message(BrowseStates.browsing, F.text == BTN_LIKE)
async def do_like(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_id = data.get("current_profile_id")
    if not target_id: return
    user = await db.get_user(message.from_user.id)
    ok, err = await _check_like_limit(user)
    if not ok:
        await message.answer(err); return
    await db.add_like(message.from_user.id, target_id, 1)
    await _inc_like_counter(user)
    if await db.is_mutual_like(message.from_user.id, target_id):
        await _notify_mutual(bot, message.from_user.id, target_id)
    await _show_next(bot, message.chat.id, user, state)

@router.message(BrowseStates.browsing, F.text == BTN_DISLIKE)
async def do_dislike(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_id = data.get("current_profile_id")
    if target_id:
        await db.add_like(message.from_user.id, target_id, -1)
    user = await db.get_user(message.from_user.id)
    await _show_next(bot, message.chat.id, user, state)

@router.message(BrowseStates.browsing, F.text == BTN_SKIP)
async def do_skip(message: Message, state: FSMContext, bot: Bot):
    user = await db.get_user(message.from_user.id)
    await _show_next(bot, message.chat.id, user, state)

@router.message(BrowseStates.browsing, F.text == BTN_LIKE_MSG)
async def like_with_message_start(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user["is_premium"]:
        await message.answer(f"⭐ Только для Премиум. Оформить: @{ADMIN_USERNAME}"); return
    await message.answer("Выберите тип сообщения:", reply_markup=like_message_type_keyboard())
    await state.set_state(BrowseStates.like_message)

@router.callback_query(BrowseStates.like_message, F.data.startswith("likemsg_"))
async def like_message_type_cb(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    action = call.data.split("_", 1)[1]
    if action == "cancel":
        await state.set_state(BrowseStates.browsing)
        user = await db.get_user(call.from_user.id)
        await call.message.answer("Отменено.", reply_markup=browse_keyboard(True)); return
    await state.update_data(like_msg_type=action)
    prompts = {"text": "✍️ Напишите текст:", "audio": "🎤 Голосовое:", "video_note": "🎥 Видеокружок:"}
    await call.message.answer(prompts[action])

@router.message(BrowseStates.like_message)
async def receive_like_message(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    msg_type = data.get("like_msg_type")
    target_id = data.get("current_profile_id")
    if not msg_type: return
    msg_text = msg_file = None
    if msg_type == "text":
        if not message.text: await message.answer("Отправьте текст:"); return
        if re.search(r"@\w+|https?://|t\.me/", message.text, re.I):
            await message.answer("⛔ Без ссылок."); return
        msg_text = message.text.strip()
    elif msg_type == "audio":
        if not message.voice: await message.answer("Отправьте голосовое:"); return
        msg_file = message.voice.file_id
    elif msg_type == "video_note":
        if not message.video_note: await message.answer("Отправьте видеокружок:"); return
        msg_file = message.video_note.file_id
    user = await db.get_user(message.from_user.id)
    ok, err = await _check_like_limit(user)
    if not ok:
        await message.answer(err); await state.set_state(BrowseStates.browsing); return
    await db.add_like(message.from_user.id, target_id, 1,
                      msg_text=msg_text, msg_file=msg_file, msg_type=msg_type)
    await _inc_like_counter(user)
    await message.answer("❤️ Лайк с сообщением отправлен!")
    if await db.is_mutual_like(message.from_user.id, target_id):
        await _notify_mutual(bot, message.from_user.id, target_id)
    await state.set_state(BrowseStates.browsing)
    await _show_next(bot, message.chat.id, user, state)

async def _notify_mutual(bot, user_a, user_b):
    profile_a = await db.get_profile(user_a)
    profile_b = await db.get_profile(user_b)
    ua = await db.get_user(user_a)
    ub = await db.get_user(user_b)
    if ub.get("username"):
        try:
            await bot.send_message(user_a,
                f"🎉 Взаимная симпатия!\n<b>{profile_b['name']}</b> тоже лайкнул(а) вас!\n\nОбщайтесь через махрама 🤝",
                parse_mode="HTML", reply_markup=mutual_like_keyboard(ub["username"]))
        except: pass
    if ua.get("username"):
        try:
            await bot.send_message(user_b,
                f"🎉 Взаимная симпатия!\n<b>{profile_a['name']}</b> тоже лайкнул(а) вас!\n\nОбщайтесь через махрама 🤝",
                parse_mode="HTML", reply_markup=mutual_like_keyboard(ua["username"]))
        except: pass
