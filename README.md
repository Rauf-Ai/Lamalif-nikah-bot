# 🌙 ЛямАлиф Никях-бот

Telegram-бот для знакомств с намерением — для мусульман.

## Структура проекта

```
nikah_bot/
├── main.py              # Точка входа
├── config.py            # Токены, настройки, лимиты
├── database.py          # Слой работы с SQLite (aiosqlite)
├── states.py            # FSM-состояния aiogram 3
├── keyboards.py         # Все клавиатуры
├── utils.py             # Вспомогательные функции
├── requirements.txt
└── handlers/
    ├── __init__.py
    ├── registration.py  # Регистрация, анкета, редактирование
    ├── browse.py        # Просмотр анкет, лайки, дизлайки
    └── misc.py          # Симпатии, профиль, премиум, админ
```

## Установка и запуск

### 1. Создайте бота

Напишите [@BotFather](https://t.me/BotFather), получите `BOT_TOKEN`.

### 2. Установите зависимости

```bash
pip install -r requirements.txt
```

### 3. Настройте config.py

```python
BOT_TOKEN = "ВАШ_ТОКЕН"
ADMIN_ID   = 123456789   # Ваш Telegram ID (узнать: @userinfobot)
```

### 4. Запуск

```bash
python main.py
```

### 5. Запуск как systemd-сервис (VPS Timeweb)

Создайте файл `/etc/systemd/system/nikah_bot.service`:

```ini
[Unit]
Description=LyaMalif Nikah Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/nikah_bot
ExecStart=/usr/bin/python3 /root/nikah_bot/main.py
Restart=always
RestartSec=5
Environment=BOT_TOKEN=ВАШ_ТОКЕН
Environment=ADMIN_ID=ВАШ_ID

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable nikah_bot
systemctl start nikah_bot
systemctl status nikah_bot
```

---

## Логика подписки

### Девушки
| Функция                        | Бесплатно | Премиум (700₽/мес) |
|--------------------------------|-----------|---------------------|
| Лайки в день                   | 15        | Безлимит            |
| Видимость анкеты               | Обычная   | Выше                |
| Вернуться к предыдущей анкете  | ❌        | ✅                  |
| Лайк с сообщением              | ❌        | ✅                  |
| Просмотр входящих лайков       | ✅        | ✅                  |
| Взаимные симпатии              | ✅        | ✅                  |

### Парни
| Функция                        | Бесплатно      | Премиум (700₽/мес) |
|--------------------------------|----------------|---------------------|
| Лайки в неделю                 | 30             | Безлимит            |
| Просмотр кто лайкнул           | ❌             | ✅                  |
| Взаимные симпатии с контактом  | ❌             | ✅                  |
| Вернуться к предыдущей анкете  | ❌             | ✅                  |
| Лайк с сообщением              | ❌             | ✅                  |

---

## Админ-команды

| Команда                         | Действие                              |
|---------------------------------|---------------------------------------|
| `/ban <user_id>`                | Бан пользователя                      |
| `/unban <user_id>`              | Снять бан                             |
| `/premium <user_id> <дата>`     | Выдать Премиум до даты (YYYY-MM-DD)   |
| `/stats`                        | Статистика бота                       |
| `/broadcast <текст>`            | Рассылка всем пользователям           |

---

## Добавление платёжной системы

Сейчас оплата идёт через @rau_ff вручную.
Для автоматизации можно подключить:
- **ЮKassa** (`aiogram-payments` + webhook)
- **Telegram Stars** (встроенные платежи Telegram)
- **Tinkoff API**

Напишите в issues если нужна автоматическая оплата.
