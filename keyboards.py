"""
keyboards.py — все клавиатуры бота
"""
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ─── Главное меню ─────────────────────────────────────────

def main_menu(gender: str, has_profile: bool) -> ReplyKeyboardMarkup:
    buttons = []
    if has_profile:
        buttons.append([KeyboardButton(text="👀 Смотреть анкеты")])
        buttons.append([KeyboardButton(text="❤️ Мои симпатии"),
                        KeyboardButton(text="👤 Моя анкета")])
        buttons.append([KeyboardButton(text="✏️ Изменить анкету"),
                        KeyboardButton(text="⭐ Премиум")])
    else:
        buttons.append([KeyboardButton(text="📝 Заполнить анкету")])
    buttons.append([KeyboardButton(text="ℹ️ Помощь")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# ─── Правила ──────────────────────────────────────────────

def rules_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Принимаю правила", callback_data="accept_rules")
    ]])


# ─── Выбор пола ───────────────────────────────────────────

def gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👨 Я мужчина", callback_data="gender_male"),
        InlineKeyboardButton(text="👩 Я женщина", callback_data="gender_female"),
    ]])


# ─── Подтверждение анкеты ─────────────────────────────────

def confirm_profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="profile_confirm")],
        [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="profile_edit")],
    ])


# ─── Просмотр анкет (browsing) ────────────────────────────

def browse_keyboard(is_premium: bool, gender: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❤️ Лайк", callback_data="browse_like")
    builder.button(text="👎 Дизлайк", callback_data="browse_dislike")
    if is_premium:
        builder.button(text="💌 Лайк с сообщением", callback_data="browse_like_msg")
        builder.button(text="↩️ Назад", callback_data="browse_back")
    builder.adjust(2)
    return builder.as_markup()


# ─── Лайк с сообщением (тип) ──────────────────────────────

def like_message_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Текст", callback_data="likemsg_text")],
        [InlineKeyboardButton(text="🎤 Аудио", callback_data="likemsg_audio")],
        [InlineKeyboardButton(text="🎥 Видеокружок", callback_data="likemsg_video_note")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="likemsg_cancel")],
    ])


# ─── Взаимные симпатии ────────────────────────────────────

def mutual_like_keyboard(target_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"💬 Написать @{target_username}",
            url=f"https://t.me/{target_username}"
        )
    ]])


# ─── Редактирование анкеты ────────────────────────────────

def edit_field_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Имя",    callback_data="edit_name"),
         InlineKeyboardButton(text="🎂 Возраст", callback_data="edit_age")],
        [InlineKeyboardButton(text="📍 Город",  callback_data="edit_city")],
        [InlineKeyboardButton(text="💬 О себе", callback_data="edit_about")],
        [InlineKeyboardButton(text="📸 Фото",   callback_data="edit_photos")],
        [InlineKeyboardButton(text="🔙 Назад",  callback_data="edit_cancel")],
    ])


# ─── Премиум ──────────────────────────────────────────────

def premium_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить Премиум (700₽/мес)",
                              url="https://t.me/rau_ff")],
    ])


# ─── Удалить клавиатуру ───────────────────────────────────

def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# ─── Пропустить / Отмена ──────────────────────────────────

def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


# ─── Симпатии — выбор раздела ─────────────────────────────

def likes_menu_keyboard(gender: str, is_premium: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔁 Взаимные симпатии", callback_data="likes_mutual")
    # Входящие лайки для просмотра кто лайкнул:
    # Бесплатно для девушек, только премиум для парней
    if gender == "female" or is_premium:
        builder.button(text="💌 Кто меня лайкнул", callback_data="likes_incoming")
    else:
        builder.button(text="🔒 Кто меня лайкнул (Премиум)", callback_data="likes_need_premium")
    builder.adjust(1)
    return builder.as_markup()
