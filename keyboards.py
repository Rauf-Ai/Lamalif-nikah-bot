"""
keyboards.py (обновлённая) — добавлена кнопка рефералов в главном меню
"""
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu(gender: str, has_profile: bool) -> ReplyKeyboardMarkup:
    buttons = []
    if has_profile:
        buttons.append([KeyboardButton(text="👀 Смотреть анкеты")])
        buttons.append([
            KeyboardButton(text="❤️ Мои симпатии"),
            KeyboardButton(text="👤 Моя анкета"),
        ])
        buttons.append([
            KeyboardButton(text="✏️ Изменить анкету"),
            KeyboardButton(text="⭐ Премиум"),
        ])
        buttons.append([
            KeyboardButton(text="🔗 Рефералы"),
            KeyboardButton(text="ℹ️ Помощь"),
        ])
    else:
        buttons.append([KeyboardButton(text="📝 Заполнить анкету")])
        buttons.append([KeyboardButton(text="ℹ️ Помощь")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def browse_keyboard(is_premium: bool) -> ReplyKeyboardMarkup:
    if is_premium:
        row = [
            KeyboardButton(text="♥️"),
            KeyboardButton(text="💌"),
            KeyboardButton(text="👎"),
            KeyboardButton(text="💤"),
        ]
    else:
        row = [
            KeyboardButton(text="♥️"),
            KeyboardButton(text="👎"),
            KeyboardButton(text="💤"),
        ]
    return ReplyKeyboardMarkup(
        keyboard=[row, [KeyboardButton(text="🔙 В главное меню")]],
        resize_keyboard=True
    )


def rules_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Принимаю правила", callback_data="accept_rules")
    ]])


def gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👨 Я мужчина", callback_data="gender_male"),
        InlineKeyboardButton(text="👩 Я женщина", callback_data="gender_female"),
    ]])


def confirm_profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="profile_confirm")],
        [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="profile_edit")],
    ])


def like_message_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Текст",       callback_data="likemsg_text")],
        [InlineKeyboardButton(text="🎤 Аудио",       callback_data="likemsg_audio")],
        [InlineKeyboardButton(text="🎥 Видеокружок", callback_data="likemsg_video_note")],
        [InlineKeyboardButton(text="❌ Отмена",      callback_data="likemsg_cancel")],
    ])


def mutual_like_keyboard(target_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"💬 Написать @{target_username}",
            url=f"https://t.me/{target_username}"
        )
    ]])


def edit_field_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Имя",     callback_data="edit_name"),
         InlineKeyboardButton(text="🎂 Возраст", callback_data="edit_age")],
        [InlineKeyboardButton(text="📍 Город",   callback_data="edit_city")],
        [InlineKeyboardButton(text="💬 О себе",  callback_data="edit_about")],
        [InlineKeyboardButton(text="📸 Фото",    callback_data="edit_photos")],
        [InlineKeyboardButton(text="🔙 Назад",   callback_data="edit_cancel")],
    ])


def premium_plans_keyboard() -> InlineKeyboardMarkup:
    from handlers.payment import PLANS
    rows = []
    for i, (label, days, stars) in enumerate(PLANS):
        rows.append([InlineKeyboardButton(
            text=f"{label}  •  ⭐ {stars}",
            callback_data=f"buy_plan_{i}"
        )])
    rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="premium_close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def likes_menu_keyboard(gender: str, is_premium: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔁 Взаимные симпатии", callback_data="likes_mutual")
    if gender == "female" or is_premium:
        builder.button(text="💌 Кто меня лайкнул", callback_data="likes_incoming")
    else:
        builder.button(text="🔒 Кто меня лайкнул (Премиум)", callback_data="likes_need_premium")
    builder.adjust(1)
    return builder.as_markup()


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )
        
