"""
utils.py — вспомогательные функции
"""
import re
from aiogram import Bot
from aiogram.types import Message, MediaGroup, InputMediaPhoto
from config import CHANNEL_USERNAME


# ─── Проверка подписки на канал ───────────────────────────

async def check_subscription(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id=f"@{CHANNEL_USERNAME}", user_id=user_id
        )
        return member.status not in ("left", "kicked", "banned")
    except Exception:
        return False


# ─── Проверка username ─────────────────────────────────────

def has_username(message: Message) -> bool:
    return bool(message.from_user.username)


# ─── Валидация текста анкеты ──────────────────────────────

def contains_links_or_mentions(text: str) -> bool:
    """True если текст содержит ссылки, @упоминания или t.me/"""
    patterns = [
        r"@\w+",
        r"https?://",
        r"t\.me/",
        r"telegram\.me/",
        r"wa\.me/",
        r"vk\.com/",
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


# ─── Форматирование анкеты ────────────────────────────────

def format_profile(profile: dict, show_username: bool = False) -> str:
    gender_emoji = "👩" if profile["gender"] == "female" else "👨"
    premium_badge = " ✅ Премиум" if profile.get("is_premium") else ""
    username_line = (
        f"\n📎 @{profile['username']}" if show_username and profile.get("username")
        else ""
    )
    return (
        f"{gender_emoji} <b>{profile['name']}</b>, {profile['age']} лет{premium_badge}\n"
        f"📍 {profile['city']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{profile['about']}"
        f"{username_line}"
    )


# ─── Отправка анкеты с фото ───────────────────────────────

async def send_profile_card(
    bot: Bot,
    chat_id: int,
    profile: dict,
    photos: list[str],
    reply_markup=None,
    show_username: bool = False,
    extra_text: str = ""
):
    caption = format_profile(profile, show_username=show_username)
    if extra_text:
        caption += f"\n\n{extra_text}"

    if not photos:
        await bot.send_message(chat_id, caption,
                               parse_mode="HTML", reply_markup=reply_markup)
        return

    if len(photos) == 1:
        await bot.send_photo(
            chat_id, photos[0],
            caption=caption, parse_mode="HTML",
            reply_markup=reply_markup
        )
    else:
        media = [
            InputMediaPhoto(
                media=fid,
                caption=caption if i == 0 else None,
                parse_mode="HTML" if i == 0 else None
            )
            for i, fid in enumerate(photos)
        ]
        msgs = await bot.send_media_group(chat_id, media)
        # Кнопки отправляем отдельным сообщением если есть клавиатура
        if reply_markup:
            await bot.send_message(
                chat_id, "👆 Анкета выше",
                reply_markup=reply_markup
            )
