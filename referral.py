"""
handlers/referral.py — реферальная система
Уровень 1: 30% с оплат приглашённых клиентов
Уровень 2: 10% с оплат клиентов партнёров (которых ты пригласил)
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

import database as db
from keyboards import main_menu

router = Router()


# ─── /start с реферальным параметром ─────────────────────
# Пример ссылки: https://t.me/BOT_USERNAME?start=ref_123456789

async def handle_referral_start(user_id: int, ref_code: str, bot: Bot):
    """Вызывается из registration.py при /start ref_XXXXX"""
    if not ref_code.startswith("ref_"):
        return
    try:
        referrer_id = int(ref_code[4:])
    except ValueError:
        return

    if referrer_id == user_id:
        return  # нельзя пригласить самого себя

    # Проверяем что реферер существует
    referrer = await db.get_user(referrer_id)
    if not referrer:
        return

    # Записываем только если пользователь ещё не привязан
    existing = await db.get_referral_info(user_id)
    if existing and existing.get("referred_by"):
        return

    await db.set_referral(user_id, referrer_id)


# ─── Моя реферальная ссылка ───────────────────────────────

@router.message(F.text.in_({"🔗 Реферальная ссылка", "🔗 Рефералы"}))
async def my_referral(message: Message, bot: Bot):
    await show_referral_info(message.from_user.id, message, bot)


async def show_referral_info(user_id: int, message: Message, bot: Bot):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    stats = await db.get_referral_stats(user_id)
    earnings = await db.get_ref_earnings(user_id)

    total_stars = sum(e["amount"] for e in earnings)
    lvl1_count  = stats.get("lvl1_count", 0)
    lvl2_count  = stats.get("lvl2_count", 0)

    # Последние начисления
    recent = earnings[-5:] if earnings else []
    recent_text = ""
    if recent:
        recent_text = "\n\n<b>Последние начисления:</b>\n"
        for e in reversed(recent):
            lvl = e["level"]
            pct = "30%" if lvl == 1 else "10%"
            recent_text += f"• {e['amount']} ⭐ ({pct} от {e['original_amount']} ⭐) — ур.{lvl}\n"

    await message.answer(
        f"🔗 <b>Ваша реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"👥 Приглашено партнёров (ур.1): <b>{lvl1_count}</b>\n"
        f"👥 Их рефералы (ур.2): <b>{lvl2_count}</b>\n"
        f"💰 Заработано всего: <b>{total_stars} ⭐</b>\n\n"
        f"<b>Условия:</b>\n"
        f"• 30% — с каждой оплаты вашего реферала\n"
        f"• 10% — с оплат рефералов ваших партнёров"
        f"{recent_text}\n\n"
        "Поделитесь ссылкой — и зарабатывайте на каждой оплате! 🌙",
        parse_mode="HTML"
    )
