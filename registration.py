"""
handlers/registration.py — регистрация и заполнение анкеты
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

import database as db
from states import RegStates, EditStates
from keyboards import (
    rules_keyboard, gender_keyboard, confirm_profile_keyboard,
    cancel_keyboard, remove_kb, main_menu, edit_field_keyboard
)
from utils import (
    check_subscription, has_username, contains_links_or_mentions,
    format_profile, send_profile_card
)
from config import ABOUT_MIN_CHARS, ABOUT_HINT, RULES_TEXT, MAX_PHOTOS

router = Router()


# ─── /start ───────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user = await db.get_user(message.from_user.id)

    if user and user.get("is_banned"):
        await message.answer("🚫 Вы заблокированы. По вопросам: @rau_ff")
        return

    await db.upsert_user(message.from_user.id, message.from_user.username)

    # Если уже зарегистрирован — главное меню
    profile = await db.get_profile(message.from_user.id)
    if profile:
        gender = user["gender"] if user else "male"
        await message.answer(
            "С возвращением! 🌙",
            reply_markup=main_menu(gender, has_profile=True)
        )
        return

    # Новый пользователь — правила
    await message.answer(
        "Ас-саляму алейкум! 🌙\n\n"
        "Добро пожаловать в <b>ЛямАлиф Никях</b> — бот для знакомств "
        "с намерением создать семью.\n\n"
        "Пожалуйста, ознакомьтесь с правилами:",
        parse_mode="HTML"
    )
    await message.answer(RULES_TEXT, parse_mode="HTML",
                         reply_markup=rules_keyboard())
    await state.set_state(RegStates.waiting_rules)


# ─── Принятие правил ──────────────────────────────────────

@router.callback_query(RegStates.waiting_rules, F.data == "accept_rules")
async def accept_rules(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()

    # Проверка username
    if not call.from_user.username:
        await call.message.answer(
            "⚠️ У вас не задан username в Telegram!\n\n"
            "Перейдите в Настройки → Изменить профиль → Имя пользователя.\n"
            "После этого нажмите /start снова."
        )
        return

    # Проверка подписки
    is_sub = await check_subscription(bot, call.from_user.id)
    if not is_sub:
        await call.message.answer(
            "📢 Для использования бота необходимо подписаться на канал "
            "@lamalif_official\n\nПосле подписки нажмите /start снова."
        )
        return

    await call.message.answer(
        "Отлично! Правила приняты ✅\n\nВыберите ваш пол:",
        reply_markup=gender_keyboard()
    )
    await state.set_state(RegStates.waiting_gender)


# ─── Выбор пола ───────────────────────────────────────────

@router.callback_query(RegStates.waiting_gender, F.data.in_({"gender_male", "gender_female"}))
async def choose_gender(call: CallbackQuery, state: FSMContext):
    await call.answer()
    gender = "male" if call.data == "gender_male" else "female"
    await state.update_data(gender=gender)
    await db.set_gender(call.from_user.id, gender)

    await call.message.answer(
        "Как вас зовут? Введите имя (не полное ФИО):",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(RegStates.waiting_name)


# ─── Имя ──────────────────────────────────────────────────

@router.message(RegStates.waiting_name)
async def get_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=remove_kb())
        return

    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await message.answer("Имя должно быть от 2 до 50 символов. Попробуйте снова:")
        return
    if contains_links_or_mentions(name):
        await message.answer("⛔ Имя не должно содержать ссылки или @упоминания.")
        return

    await state.update_data(name=name)
    await message.answer("Ваш возраст (число от 18 до 80):")
    await state.set_state(RegStates.waiting_age)


# ─── Возраст ──────────────────────────────────────────────

@router.message(RegStates.waiting_age)
async def get_age(message: Message, state: FSMContext):
    try:
        age = int(message.text.strip())
        assert 18 <= age <= 80
    except (ValueError, AssertionError):
        await message.answer("Введите корректный возраст (от 18 до 80):")
        return

    await state.update_data(age=age)
    await message.answer("Ваш город проживания:")
    await state.set_state(RegStates.waiting_city)


# ─── Город ────────────────────────────────────────────────

@router.message(RegStates.waiting_city)
async def get_city(message: Message, state: FSMContext):
    city = message.text.strip()
    if len(city) < 2 or len(city) > 100:
        await message.answer("Пожалуйста, введите корректный город:")
        return
    if contains_links_or_mentions(city):
        await message.answer("⛔ Поле не должно содержать ссылки или @упоминания.")
        return

    await state.update_data(city=city)
    await message.answer(ABOUT_HINT, parse_mode="HTML")
    await state.set_state(RegStates.waiting_about)


# ─── О себе ───────────────────────────────────────────────

@router.message(RegStates.waiting_about)
async def get_about(message: Message, state: FSMContext):
    about = message.text.strip() if message.text else ""

    if contains_links_or_mentions(about):
        await message.answer(
            "⛔ Текст не должен содержать ссылки, @упоминания или контакты.\n"
            "Пожалуйста, перепишите:"
        )
        return

    if len(about) < ABOUT_MIN_CHARS:
        await message.answer(
            f"❗ Слишком коротко ({len(about)} симв.). "
            f"Минимум {ABOUT_MIN_CHARS} символов.\n"
            "Расскажите подробнее о себе:"
        )
        return

    await state.update_data(about=about)
    await message.answer(
        f"📸 Загрузите фото (до {MAX_PHOTOS} штук).\n\n"
        "Можно отправить все сразу как альбом.\n"
        "⚠️ Анкета без фото не публикуется.",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(RegStates.waiting_photos)


# ─── Фото ─────────────────────────────────────────────────

@router.message(RegStates.waiting_photos, F.photo)
async def get_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])

    # Берём наибольшее разрешение
    file_id = message.photo[-1].file_id
    if file_id not in photos:
        photos.append(file_id)

    await state.update_data(photos=photos)

    if len(photos) >= MAX_PHOTOS:
        await _finish_photos(message, state)
    else:
        await message.answer(
            f"✅ Фото {len(photos)}/{MAX_PHOTOS} получено. "
            f"Отправьте ещё или нажмите /done для завершения."
        )


@router.message(RegStates.waiting_photos, F.text == "/done")
@router.message(RegStates.waiting_photos, F.text == "done")
async def photos_done(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("photos"):
        await message.answer("⚠️ Нужно загрузить хотя бы одно фото.")
        return
    await _finish_photos(message, state)


async def _finish_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    # Показать превью анкеты
    profile_preview = {
        "name": data["name"],
        "age": data["age"],
        "city": data["city"],
        "about": data["about"],
        "gender": data["gender"],
        "username": message.from_user.username,
        "is_premium": False,
    }
    text = "👀 <b>Ваша анкета:</b>\n\n" + format_profile(profile_preview)
    await message.answer(
        text, parse_mode="HTML",
        reply_markup=confirm_profile_keyboard()
    )
    await state.set_state(RegStates.confirm_profile)


# ─── Подтверждение анкеты ─────────────────────────────────

@router.callback_query(RegStates.confirm_profile, F.data == "profile_confirm")
async def confirm_profile(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    data = await state.get_data()

    await db.save_profile(
        call.from_user.id,
        data["name"], data["age"], data["city"], data["about"]
    )
    await db.save_photos(call.from_user.id, data["photos"])

    user = await db.get_user(call.from_user.id)
    gender = data["gender"]

    await state.clear()
    await call.message.answer(
        "🎉 Анкета успешно создана!\n\n"
        "بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيم\n"
        "Да поможет Аллах найти вашу половинку! 🌙",
        reply_markup=main_menu(gender, has_profile=True)
    )


@router.callback_query(RegStates.confirm_profile, F.data == "profile_edit")
async def back_to_edit(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer(
        "Что хотите изменить?",
        reply_markup=edit_field_keyboard()
    )
    await state.set_state(EditStates.choose_field)


# ─── Редактирование анкеты ────────────────────────────────

@router.message(F.text == "✏️ Изменить анкету")
async def edit_profile_menu(message: Message, state: FSMContext):
    profile = await db.get_profile(message.from_user.id)
    if not profile:
        await message.answer("Сначала заполните анкету.")
        return
    await message.answer("Что хотите изменить?", reply_markup=edit_field_keyboard())
    await state.set_state(EditStates.choose_field)


@router.callback_query(EditStates.choose_field, F.data == "edit_name")
async def edit_name_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("Введите новое имя:", reply_markup=cancel_keyboard())
    await state.set_state(EditStates.edit_name)


@router.message(EditStates.edit_name)
async def edit_name_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=remove_kb())
        return
    name = message.text.strip()
    if len(name) < 2 or contains_links_or_mentions(name):
        await message.answer("Некорректное имя. Попробуйте снова:")
        return
    profile = await db.get_profile(message.from_user.id)
    await db.save_profile(message.from_user.id, name,
                          profile["age"], profile["city"], profile["about"])
    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer("✅ Имя обновлено!", reply_markup=main_menu(user["gender"], True))


@router.callback_query(EditStates.choose_field, F.data == "edit_age")
async def edit_age_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("Введите новый возраст:", reply_markup=cancel_keyboard())
    await state.set_state(EditStates.edit_age)


@router.message(EditStates.edit_age)
async def edit_age_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=remove_kb())
        return
    try:
        age = int(message.text.strip())
        assert 18 <= age <= 80
    except (ValueError, AssertionError):
        await message.answer("Введите корректный возраст (18–80):")
        return
    profile = await db.get_profile(message.from_user.id)
    await db.save_profile(message.from_user.id, profile["name"],
                          age, profile["city"], profile["about"])
    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer("✅ Возраст обновлён!", reply_markup=main_menu(user["gender"], True))


@router.callback_query(EditStates.choose_field, F.data == "edit_city")
async def edit_city_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("Введите новый город:", reply_markup=cancel_keyboard())
    await state.set_state(EditStates.edit_city)


@router.message(EditStates.edit_city)
async def edit_city_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=remove_kb())
        return
    city = message.text.strip()
    if contains_links_or_mentions(city):
        await message.answer("⛔ Некорректный город. Попробуйте снова:")
        return
    profile = await db.get_profile(message.from_user.id)
    await db.save_profile(message.from_user.id, profile["name"],
                          profile["age"], city, profile["about"])
    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer("✅ Город обновлён!", reply_markup=main_menu(user["gender"], True))


@router.callback_query(EditStates.choose_field, F.data == "edit_about")
async def edit_about_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer(ABOUT_HINT, parse_mode="HTML",
                              reply_markup=cancel_keyboard())
    await state.set_state(EditStates.edit_about)


@router.message(EditStates.edit_about)
async def edit_about_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=remove_kb())
        return
    about = message.text.strip()
    if contains_links_or_mentions(about):
        await message.answer("⛔ Текст содержит ссылки или @упоминания. Перепишите:")
        return
    if len(about) < ABOUT_MIN_CHARS:
        await message.answer(f"❗ Минимум {ABOUT_MIN_CHARS} символов. Сейчас: {len(about)}.")
        return
    profile = await db.get_profile(message.from_user.id)
    await db.save_profile(message.from_user.id, profile["name"],
                          profile["age"], profile["city"], about)
    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer("✅ Описание обновлено!", reply_markup=main_menu(user["gender"], True))


@router.callback_query(EditStates.choose_field, F.data == "edit_photos")
async def edit_photos_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer(
        f"Отправьте новые фото (до {MAX_PHOTOS}). Старые будут заменены.\n"
        "По завершении — /done",
        reply_markup=cancel_keyboard()
    )
    await state.update_data(photos=[])
    await state.set_state(EditStates.edit_photos)


@router.message(EditStates.edit_photos, F.photo)
async def edit_photos_receive(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    file_id = message.photo[-1].file_id
    if file_id not in photos:
        photos.append(file_id)
    await state.update_data(photos=photos)
    if len(photos) >= MAX_PHOTOS:
        await db.save_photos(message.from_user.id, photos)
        await state.clear()
        user = await db.get_user(message.from_user.id)
        await message.answer("✅ Фото обновлены!",
                             reply_markup=main_menu(user["gender"], True))
    else:
        await message.answer(f"Фото {len(photos)}/{MAX_PHOTOS}. Ещё или /done:")


@router.message(EditStates.edit_photos, F.text.in_({"/done", "done"}))
async def edit_photos_done(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if not photos:
        await message.answer("⚠️ Нужно хотя бы одно фото.")
        return
    await db.save_photos(message.from_user.id, photos)
    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer("✅ Фото обновлены!", reply_markup=main_menu(user["gender"], True))


@router.callback_query(EditStates.choose_field, F.data == "edit_cancel")
async def edit_cancel(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    user = await db.get_user(call.from_user.id)
    await call.message.answer("Отменено.", reply_markup=main_menu(user["gender"], True))
