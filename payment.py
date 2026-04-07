"""
handlers/payment.py — оплата Telegram Stars + реферальные начисления
"""
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from datetime import date, timedelta

import database as db
from config import ADMIN_ID

router = Router()

# ─── Тарифы: (label, days, stars) ────────────────────────
PLANS = [
    ("2 дня",    2,   250),
    ("30 дней",  30,  750),
    ("90 дней",  90,  1500),
    ("180 дней", 180, 2500),
]

TERMS_URL = "https://t.me/lamalif_official"   # замени на свой URL условий


def premium_plans_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for i, (label, days, stars) in enumerate(PLANS):
        rows.append([InlineKeyboardButton(
            text=f"{label}  •  ⭐ {stars}",
            callback_data=f"buy_plan_{i}"
        )])
    rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="premium_close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Показ тарифов ────────────────────────────────────────

@router.message(F.text == "⭐ Премиум")
async def show_premium(message: Message):
    user = await db.get_user(message.from_user.id)
    if user and user["is_premium"]:
        until = user.get("premium_until", "—")
        await message.answer(
            f"✅ У вас активен Премиум до <b>{until}</b>\n\n"
            "Хотите продлить?",
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
            "💌 Лайк с сообщением (текст/аудио/видео)\n"
            "↩️ Вернуться к предыдущей анкете"
        )
    else:
        perks = (
            "📈 Больше показов анкеты\n"
            "🚀 Безлимитные лайки (вместо 30/неделю)\n"
            "👀 Кто тебя лайкнул — видишь сразу\n"
            "⭐️ Анкета выше остальных\n"
            "💌 Лайк с сообщением (текст/аудио/видео)\n"
            "↩️ Вернуться к предыдущей анкете"
        )

    await message.answer(
        "✨ <b>Активируй Premium и будь в топе</b>\n\n"
        "Выделяйся среди других:\n"
        f"{perks}\n\n"
        "Больше внимания. Больше взаимностей. Больше знакомств 💫\n\n"
        "<b>Выбери срок действия Premium:</b>",
        parse_mode="HTML",
        reply_markup=premium_plans_keyboard()
    )


@router.callback_query(F.data == "premium_close")
async def close_premium(call: CallbackQuery):
    await call.answer()
    await call.message.delete()


# ─── Выбор тарифа → инвойс ────────────────────────────────

@router.callback_query(F.data.startswith("buy_plan_"))
async def buy_plan(call: CallbackQuery, bot: Bot):
    await call.answer()
    idx = int(call.data.split("_")[-1])
    label, days, stars = PLANS[idx]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"Premium {label}",
        description=(
            f"ЛямАлиф Никях — Premium на {label}\n"
            "Безлимитные лайки, топ в выдаче, лайк с сообщением и другие преимущества."
        ),
        payload=f"premium_{idx}_{call.from_user.id}",
        currency="XTR",                   # Telegram Stars
        prices=[LabeledPrice(label=f"Premium {label}", amount=stars)],
        provider_token="",                 # пусто для Stars
        # Ссылка на условия
        protect_content=False,
    )


# ─── Pre-checkout (обязательно) ───────────────────────────

@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


# ─── Успешная оплата ──────────────────────────────────────

@router.message(F.successful_payment)
async def payment_success(message: Message, bot: Bot):
    payload = message.successful_payment.invoice_payload
    # payload формат: premium_{plan_idx}_{user_id}
    parts = payload.split("_")
    if len(parts) < 3 or parts[0] != "premium":
        return

    plan_idx = int(parts[1])
    buyer_id = int(parts[2])
    label, days, stars = PLANS[plan_idx]

    # Считаем дату окончания
    user = await db.get_user(buyer_id)
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
    await db.set_premium(buyer_id, until)

    await message.answer(
        f"🎉 <b>Premium активирован!</b>\n\n"
        f"⭐ Тариф: {label}\n"
        f"📅 Действует до: <b>{until}</b>\n\n"
        "Теперь ваша анкета в топе!\n"
        "بَارَكَ اللَّهُ فِيكَ 🌙",
        parse_mode="HTML"
    )

    # ── Реферальные начисления ────────────────────────────
    ref = await db.get_referral_info(buyer_id)
    if ref and ref.get("referred_by"):
        lvl1_id = ref["referred_by"]
        amount_lvl1 = int(stars * 0.30)   # 30% приглашённому
        await db.add_ref_earning(lvl1_id, buyer_id, stars, amount_lvl1, level=1)

        # Уведомить реферера
        try:
            await bot.send_message(
                lvl1_id,
                f"💰 Ваш реферал оплатил Premium!\n"
                f"Вы получили: <b>{amount_lvl1} ⭐</b> (30%)\n\n"
                f"Тариф: {label}",
                parse_mode="HTML"
            )
        except Exception:
            pass

        # 2-й уровень: кто пригласил lvl1
        ref2 = await db.get_referral_info(lvl1_id)
        if ref2 and ref2.get("referred_by"):
            lvl2_id = ref2["referred_by"]
            amount_lvl2 = int(stars * 0.10)  # 10% от партнёра
            await db.add_ref_earning(lvl2_id, buyer_id, stars, amount_lvl2, level=2)
            try:
                await bot.send_message(
                    lvl2_id,
                    f"💰 Реферал вашего партнёра оплатил Premium!\n"
                    f"Вы получили: <b>{amount_lvl2} ⭐</b> (10%)\n\n"
                    f"Тариф: {label}",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    # Уведомить админа
    try:
        profile = await db.get_profile(buyer_id)
        name = profile["name"] if profile else str(buyer_id)
        await bot.send_message(
            ADMIN_ID,
            f"💳 <b>Новая оплата Premium</b>\n"
            f"Пользователь: {name} (ID: {buyer_id})\n"
            f"Тариф: {label} — {stars} ⭐\n"
            f"До: {until}",
            parse_mode="HTML"
        )
    except Exception:
        pass
