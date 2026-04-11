"""
handlers/misc.py
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from keyboards import (
    main_menu, profile_menu, likes_menu_keyboard,
    premium_plans_keyboard, mutual_like_keyboard,
    support_ticket_keyboard, remove_kb, edit_field_keyboard
)
from utils import send_profile_card
from config import ADMIN_ID, ADMIN_USERNAME
from states import EditStates

router = Router()

class SupportStates(StatesGroup):
    waiting_question = State()
    waiting_reply    = State()

@router.message(F.text == "👤 Профиль")
async def profile_section(message: Message):
    profile = await db.get_profile(message.from_user.id)
    if not profile:
        await message.answer("У вас нет анкеты. Нажмите /start.")
        return
    is_hidden = bool(profile.get("is_hidden", 0))
    status = "🔴 Скрыта" if is_hidden else "🟢 Активна"
    await message.answer(
        f"👤 <b>Профиль</b>\n\nСтатус анкеты: {status}",
        parse_mode="HTML",
        reply_markup=profile_menu(is_hidden)
    )

@router.callback_query(F.data == "prof_close")
async def prof_close(call: CallbackQuery):
    await call.answer()
    await call.message.delete()

@router.callback_query(F.data == "prof_back")
async def prof_back(call: CallbackQuery):
    await call.answer()
    profile = await db.get_profile(call.from_user.id)
    is_hidden = bool(profile.get("is_hidden", 0)) if profile else False
    status = "🔴 Скрыта" if is_hidden else "🟢 Активна"
    await call.message.edit_text(
        f"👤 <b>Профиль</b>\n\nСтатус анкеты: {status}",
        parse_mode="HTML",
        reply_markup=profile_menu(is_hidden)
    )

@router.callback_query(F.data == "prof_view")
async def prof_view(call: CallbackQuery, bot: Bot):
    await call.answer()
    profile = await db.get_profile(call.from_user.id)
    if not profile:
        await call.message.answer("Анкеты нет.")
        return
    photos = await db.get_photos(call.from_user.id)
    is_hidden = bool(profile.get("is_hidden", 0))
    status = "🔴 Скрыта" if is_hidden else "🟢 Активна"
    await send_profile_card(bot, call.message.chat.id, profile, photos, show_username=True, extra_text=f"Статус: {status}")

@router.callback_query(F.data == "prof_edit")
async def prof_edit(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("Что хотите изменить?", reply_markup=edit_field_keyboard())
    await state.set_state(EditStates.choose_field)

@router.callback_query(F.data == "prof_toggle_hide")
async def prof_toggle_hide(call: CallbackQuery):
    await call.answer()
    profile = await db.get_profile(call.from_user.id)
    if not profile:
        await call.message.answer("Анкеты нет.")
        return
    new_hidden = not bool(profile.get("is_hidden", 0))
    await db.set_profile_hidden(call.from_user.id, new_hidden)
    status = "🔴 Скрыта" if new_hidden else "🟢 Активна"
    msg = "🔴 Анкета скрыта. Вас не видят в ленте." if new_hidden else "🟢 Анкета снова активна! 🌙"
    await call.answer(msg, show_alert=True)
    await call.message.edit_text(
        f"👤 <b>Профиль</b>\n\nСтатус анкеты: {status}",
        parse_mode="HTML",
        reply_markup=profile_menu(new_hidden)
    )

@router.callback_query(F.data == "prof_likes")
async def prof_likes(call: CallbackQuery):
    await call.answer()
    user = await db.get_user(call.from_user.id)
    await call.message.edit_text(
        "❤️ <b>Мои симпатии</b>",
        parse_mode="HTML",
        reply_markup=likes_menu_keyboard(user["gender"], bool(user["is_premium"]))
    )

@router.callback_query(F.data == "likes_mutual")
async def show_mutual_likes(call: CallbackQuery, bot: Bot):
    await call.answer()
    mutuals = await db.get_mutual_likes(call.from_user.id)
    if not mutuals:
        await call.message.answer("Пока нет взаимных симпатий 🌙")
        return
    await call.message.answer(f"🔁 Взаимных: {len(mutuals)}")
    for m in mutuals:
        text = f"<b>{m['name']}</b>, {m['age']} лет\n📍 {m['city']}"
        kb = mutual_like_keyboard(m["username"]) if m.get("username") else None
        await call.message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "likes_incoming")
async def show_incoming_likes(call: CallbackQuery, bot: Bot):
    await call.answer()
    user = await db.get_user(call.from_user.id)
    if user["gender"] == "male" and not user["is_premium"]:
        await call.answer("⭐ Только с Премиум.", show_alert=True)
        return
    incoming = await db.get_incoming_likes(call.from_user.id)
    if not incoming:
        await call.message.answer("Пока никто не лайкнул 🌙")
        return
    await call.message.answer(f"💌 Вас лайкнули: {len(incoming)} чел.")
    for like in incoming:
        text = f"<b>{like['name']}</b>, {like['age']} лет, {like['city']}"
        if like.get("message_text"):
            text += f"\n\n💬 «{like['message_text']}»"
        kb = mutual_like_keyboard(like["username"]) if like.get("username") else None
        await call.message.answer(text, parse_mode="HTML", reply_markup=kb)
        if like.get("message_file_id"):
            if like.get("message_type") == "audio":
                await bot.send_voice(call.message.chat.id, like["message_file_id"])
            elif like.get("message_type") == "video_note":
                await bot.send_video_note(call.message.chat.id, like["message_file_id"])

@router.callback_query(F.data == "likes_need_premium")
async def likes_need_premium(call: CallbackQuery):
    await call.answer("⭐ Только с Премиум.", show_alert=True)

@router.callback_query(F.data == "prof_ref")
async def prof_ref(call: CallbackQuery, bot: Bot):
    await call.answer()
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{call.from_user.id}"
    stats = await db.get_referral_stats(call.from_user.id)
    earnings = await db.get_ref_earnings(call.from_user.id)
    total_stars = sum(e["amount"] for e in earnings)
    recent = ""
    if earnings:
        recent = "\n\n<b>Последние начисления:</b>\n"
        for e in reversed(earnings[-5:]):
            pct = "30%" if e["level"] == 1 else "10%"
            recent += f"• {e['amount']} ⭐ ({pct})\n"
    await call.message.answer(
        f"🔗 <b>Реферальная программа</b>\n\n"
        f"Ваша ссылка:\n<code>{ref_link}</code>\n\n"
        f"👥 Приглашено: <b>{stats['lvl1_count']}</b>\n"
        f"👥 Их рефералы: <b>{stats['lvl2_count']}</b>\n"
        f"💰 Заработано: <b>{total_stars} ⭐</b>\n\n"
        f"• 30% с оплат ваших рефералов\n"
        f"• 10% с оплат их рефералов"
        f"{recent}",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "prof_support")
async def prof_support(call: CallbackQuery, state: FSMContext):
    await call.answer()
    tickets = await db.get_user_tickets(call.from_user.id)
    history = ""
    if tickets:
        history = "\n\n<b>Ваши обращения:</b>\n"
        for t in tickets[:3]:
            st = "✅" if t["status"] == "closed" else "⏳"
            short = t["message"][:50] + ("..." if len(t["message"]) > 50 else "")
            history += f"{st} {t['created_at'][:10]}: {short}\n"
            if t.get("reply"):
                history += f"   💬 {t['reply'][:60]}\n"
    await call.message.answer(
        f"🆘 <b>Поддержка</b>{history}\n\nНапишите ваш вопрос:",
        parse_mode="HTML",
        reply_markup=remove_kb()
    )
    await state.set_state(SupportStates.waiting_question)

@router.message(SupportStates.waiting_question)
async def support_receive(message: Message, state: FSMContext, bot: Bot):
    if not message.text:
        await message.answer("Пожалуйста, текстовое сообщение.")
        return
    ticket_id = await db.create_ticket(message.from_user.id, message.text)
    await message.answer(
        f"✅ Вопрос отправлен! Обращение <b>#{ticket_id}</b>\n\nОтветим в ближайшее время 🌙",
        parse_mode="HTML"
    )
    user = await db.get_user(message.from_user.id)
    profile = await db.get_profile(message.from_user.id)
    name = profile["name"] if profile else "—"
    uname = f"@{user['username']}" if user and user.get("username") else f"ID:{message.from_user.id}"
    try:
        from admin import user_actions_keyboard
        await bot.send_message(
            ADMIN_ID,
            f"🆘 <b>Обращение #{ticket_id}</b>\n\n"
            f"👤 {name} {uname}\n🆔 <code>{message.from_user.id}</code>\n\n"
            f"📝 {message.text}",
            parse_mode="HTML",
            reply_markup=support_ticket_keyboard(ticket_id)
        )
        await bot.send_message(
            ADMIN_ID,
            f"Управление {uname}:",
            reply_markup=user_actions_keyboard(
                message.from_user.id,
                bool(user.get("is_banned")),
                bool(user.get("is_premium"))
            )
        )
    except Exception:
        pass
    await state.clear()
    u = await db.get_user(message.from_user.id)
    await message.answer("Главное меню:", reply_markup=main_menu(u["gender"] if u else "male", True))

@router.callback_query(F.data.startswith("support_reply_"))
async def support_reply_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.answer()
    ticket_id = int(call.data.split("_")[-1])
    await state.update_data(reply_ticket_id=ticket_id)
    await call.message.answer(f"✏️ Ответ на обращение <b>#{ticket_id}</b>:", parse_mode="HTML")
    await state.set_state(SupportStates.waiting_reply)

@router.message(SupportStates.waiting_reply)
async def support_send_reply(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    ticket_id = data.get("reply_ticket_id")
    if not ticket_id: await state.clear(); return
    ticket = await db.get_ticket(ticket_id)
    if not ticket: await message.answer("Тикет не найден."); await state.clear(); return
    await db.reply_ticket(ticket_id, message.text)
    try:
        await bot.send_message(
            ticket["user_id"],
            f"💬 <b>Ответ поддержки #{ticket_id}:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await message.answer(f"✅ Ответ отправлен (#{ticket_id})")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()

@router.message(F.text == "⭐ Премиум")
async def premium_info(message: Message):
    user = await db.get_user(message.from_user.id)
    if user and user["is_premium"]:
        until = user.get("premium_until", "—")
        await message.answer(f"✅ Премиум активен до <b>{until}</b>", parse_mode="HTML", reply_markup=premium_plans_keyboard())
        return
    await message.answer(
        "✨ <b>Premium — будь в топе</b>\n\n"
        "📈 Больше показов · 🚀 Безлимит лайков\n"
        "👀 Видишь кто лайкнул · ⭐ Анкета выше\n"
        "💌 Лайк с сообщением\n\n<b>Выбери срок:</b>",
        parse_mode="HTML",
        reply_markup=premium_plans_keyboard()
    )

@router.message(F.text == "ℹ️ Помощь")
async def help_cmd(message: Message):
    await message.answer(
        "🌙 <b>ЛямАлиф Никях</b>\n\n"
        "👀 Смотреть анкеты — ставьте лайки\n"
        "👤 Профиль — анкета, симпатии, рефералы, поддержка\n"
        "⭐ Премиум — расширенные возможности\n\n"
        "بَارَكَ اللَّهُ فِيكُم 🤲",
        parse_mode="HTML"
    )
    
