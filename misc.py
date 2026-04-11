"""
handlers/misc.py — симпатии, профиль, премиум, скрытие анкеты, поддержка
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from keyboards import (
    main_menu, likes_menu_keyboard, premium_plans_keyboard,
    mutual_like_keyboard, support_ticket_keyboard, remove_kb
)
from utils import send_profile_card, format_profile
from config import ADMIN_ID, ADMIN_USERNAME

router = Router()


class SupportStates(StatesGroup):
    waiting_question = State()
    waiting_reply    = State()


# ─── Моя анкета ───────────────────────────────────────────
@router.message(F.text == "👤 Моя анкета")
async def my_profile(message: Message, bot: Bot):
    profile = await db.get_profile(message.from_user.id)
    if not profile:
        await message.answer("У вас нет анкеты. Нажмите /start.")
        return
    photos = await db.get_photos(message.from_user.id)
    hidden = profile.get("is_hidden", 0)
    status = "🔴 Скрыта" if hidden else "🟢 Активна"
    await send_profile_card(
        bot, message.chat.id, profile, photos,
        show_username=True,
        extra_text=f"Статус анкеты: {status}"
    )


# ─── Скрыть/показать анкету ───────────────────────────────
@router.message(F.text == "👁 Скрыть/показать анкету")
async def toggle_profile_visibility(message: Message):
    profile = await db.get_profile(message.from_user.id)
    if not profile:
        await message.answer("У вас нет анкеты.")
        return
    hidden = profile.get("is_hidden", 0)
    new_hidden = not hidden
    await db.set_profile_hidden(message.from_user.id, new_hidden)
    user = await db.get_user(message.from_user.id)
    if new_hidden:
        await message.answer(
            "🔴 Ваша анкета скрыта.\n\n"
            "Вас не будут видеть при просмотре анкет.\n"
            "Чтобы снова показать — нажмите «👁 Скрыть/показать анкету».",
            reply_markup=main_menu(user["gender"], True)
        )
    else:
        await message.answer(
            "🟢 Ваша анкета снова активна!\n\n"
            "Вас снова видят другие пользователи. 🌙",
            reply_markup=main_menu(user["gender"], True)
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
        text = f"<b>{m['name']}</b>, {m['age']} лет\n📍 {m['city']}"
        kb = mutual_like_keyboard(m["username"]) if m.get("username") else None
        await call.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "likes_incoming")
async def show_incoming_likes(call: CallbackQuery, bot: Bot):
    await call.answer()
    user = await db.get_user(call.from_user.id)
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
        if like.get("message_file_id"):
            if like.get("message_type") == "audio":
                await bot.send_voice(call.message.chat.id, like["message_file_id"])
            elif like.get("message_type") == "video_note":
                await bot.send_video_note(call.message.chat.id, like["message_file_id"])


@router.callback_query(F.data == "likes_need_premium")
async def likes_need_premium(call: CallbackQuery):
    await call.answer(
        "⭐ Просмотр входящих лайков доступен только с Премиум.",
        show_alert=True
    )


# ─── Премиум ──────────────────────────────────────────────
@router.message(F.text == "⭐ Премиум")
async def premium_info(message: Message):
    user = await db.get_user(message.from_user.id)
    if user and user["is_premium"]:
        until = user.get("premium_until", "—")
        await message.answer(
            f"✅ У вас активен Премиум до <b>{until}</b>",
            parse_mode="HTML",
            reply_markup=premium_plans_keyboard()
        )
        return

    gender = user["gender"] if user else "male"
    if gender == "female":
        perks = (
            "📈 Больше показов анкеты\n"
            "🚀 Безлимитные лайки (вместо 15/день)\n"
            "👀 Твои лайки видят первыми\n"
            "⭐️ Анкета выше остальных\n"
            "💌 Лайк с сообщением\n"
        )
    else:
        perks = (
            "📈 Больше показов анкеты\n"
            "🚀 Безлимитные лайки (вместо 30/неделю)\n"
            "👀 Кто тебя лайкнул — видишь сразу\n"
            "⭐️ Анкета выше остальных\n"
            "💌 Лайк с сообщением\n"
        )

    await message.answer(
        "✨ <b>Активируй Premium и будь в топе</b>\n\n"
        "Выделяйся среди других:\n"
        f"{perks}\n"
        "Больше внимания. Больше взаимностей. Больше знакомств 💫\n\n"
        "<b>Выбери срок:</b>",
        parse_mode="HTML",
        reply_markup=premium_plans_keyboard()
    )


# ─── ПОДДЕРЖКА ────────────────────────────────────────────

@router.message(F.text == "🆘 Поддержка")
async def support_start(message: Message, state: FSMContext):
    # Показать историю обращений
    tickets = await db.get_user_tickets(message.from_user.id)

    history = ""
    if tickets:
        history = "\n\n<b>Ваши предыдущие обращения:</b>\n"
        for t in tickets[:3]:
            status = "✅" if t["status"] == "closed" else "⏳"
            date_str = t["created_at"][:10]
            short_msg = t["message"][:50] + ("..." if len(t["message"]) > 50 else "")
            history += f"{status} {date_str}: {short_msg}\n"
            if t.get("reply"):
                history += f"   💬 Ответ: {t['reply'][:60]}\n"

    await message.answer(
        f"🆘 <b>Поддержка ЛямАлиф Никях</b>{history}\n\n"
        "Напишите ваш вопрос — и мы ответим в ближайшее время:",
        parse_mode="HTML",
        reply_markup=remove_kb()
    )
    await state.set_state(SupportStates.waiting_question)


@router.message(SupportStates.waiting_question)
async def support_receive_question(message: Message, state: FSMContext, bot: Bot):
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    ticket_id = await db.create_ticket(message.from_user.id, message.text)

    await message.answer(
        "✅ Ваш вопрос отправлен!\n\n"
        f"Номер обращения: <b>#{ticket_id}</b>\n"
        "Мы ответим вам в ближайшее время. 🌙",
        parse_mode="HTML"
    )

    user = await db.get_user(message.from_user.id)
    profile = await db.get_profile(message.from_user.id)
    name = profile["name"] if profile else "—"
    uname = f"@{user['username']}" if user and user.get("username") else f"ID:{message.from_user.id}"

    # Уведомить админа
    try:
        from keyboards import support_ticket_keyboard
        from admin import user_actions_keyboard
        admin_text = (
            f"🆘 <b>Новое обращение #{ticket_id}</b>\n\n"
            f"👤 {name} {uname}\n"
            f"🆔 <code>{message.from_user.id}</code>\n\n"
            f"📝 <b>Вопрос:</b>\n{message.text}"
        )
        await bot.send_message(
            ADMIN_ID, admin_text, parse_mode="HTML",
            reply_markup=support_ticket_keyboard(ticket_id)
        )
        # Кнопки управления пользователем
        await bot.send_message(
            ADMIN_ID,
            f"Управление пользователем {uname}:",
            reply_markup=user_actions_keyboard(
                message.from_user.id,
                bool(user.get("is_banned")),
                bool(user.get("is_premium"))
            )
        )
    except Exception as e:
        pass

    await state.clear()
    u = await db.get_user(message.from_user.id)
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu(u["gender"] if u else "male", True)
    )


# ─── Ответ на тикет (для админа) ─────────────────────────
@router.callback_query(F.data.startswith("support_reply_"))
async def support_reply_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await call.answer()
    ticket_id = int(call.data.split("_")[-1])
    await state.update_data(reply_ticket_id=ticket_id)
    await call.message.answer(
        f"✏️ Введите ответ на обращение <b>#{ticket_id}</b>:",
        parse_mode="HTML"
    )
    await state.set_state(SupportStates.waiting_reply)


@router.message(SupportStates.waiting_reply)
async def support_send_reply(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return
    data      = await state.get_data()
    ticket_id = data.get("reply_ticket_id")
    if not ticket_id:
        await state.clear()
        return

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await message.answer("Тикет не найден.")
        await state.clear()
        return

    await db.reply_ticket(ticket_id, message.text)

    # Отправить ответ пользователю
    try:
        await bot.send_message(
            ticket["user_id"],
            f"💬 <b>Ответ поддержки на ваш вопрос #{ticket_id}:</b>\n\n"
            f"{message.text}\n\n"
            "Если остались вопросы — напишите снова через «🆘 Поддержка».",
            parse_mode="HTML"
        )
        await message.answer(f"✅ Ответ отправлен пользователю (тикет #{ticket_id})")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")

    await state.clear()


# ─── Помощь ───────────────────────────────────────────────
@router.message(F.text == "ℹ️ Помощь")
async def help_cmd(message: Message):
    await message.answer(
        "🌙 <b>ЛямАлиф Никях — помощь</b>\n\n"
        "👀 <b>Смотреть анкеты</b> — просматривайте и ставьте лайки\n"
        "❤️ <b>Мои симпатии</b> — взаимные симпатии и входящие лайки\n"
        "👤 <b>Моя анкета</b> — как выглядит ваша анкета\n"
        "✏️ <b>Изменить анкету</b> — редактировать информацию\n"
        "👁 <b>Скрыть/показать анкету</b> — временно скрыть себя\n"
        "⭐ <b>Премиум</b> — расширенные возможности\n"
        "🔗 <b>Рефералы</b> — пригласить друзей и зарабатывать\n"
        "🆘 <b>Поддержка</b> — написать вопрос команде\n\n"
        "بَارَكَ اللَّهُ فِيكُم 🤲",
        parse_mode="HTML"
    )
    
