"""
database.py — SQLite + aiosqlite слой для Никях-бота ЛямАлиф
"""
import aiosqlite
from datetime import datetime, date

DB_PATH = "nikah_bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            tg_id        INTEGER PRIMARY KEY,
            username     TEXT,
            gender       TEXT,           -- 'male' | 'female'
            is_banned    INTEGER DEFAULT 0,
            is_premium   INTEGER DEFAULT 0,
            premium_until TEXT,          -- ISO date
            created_at   TEXT DEFAULT (datetime('now')),
            last_active  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS profiles (
            tg_id        INTEGER PRIMARY KEY REFERENCES users(tg_id),
            name         TEXT,
            age          INTEGER,
            city         TEXT,
            about        TEXT,           -- мин 150 символов
            is_approved  INTEGER DEFAULT 1,
            updated_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS photos (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id   INTEGER REFERENCES users(tg_id),
            file_id TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS likes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id      INTEGER REFERENCES users(tg_id),
            to_id        INTEGER REFERENCES users(tg_id),
            value        INTEGER NOT NULL,  -- 1 = лайк, -1 = дизлайк
            message_text TEXT,
            message_file_id TEXT,
            message_type TEXT,             -- 'text'|'audio'|'video_note'
            created_at   TEXT DEFAULT (datetime('now')),
            UNIQUE(from_id, to_id)
        );

        CREATE TABLE IF NOT EXISTS daily_likes (
            tg_id  INTEGER,
            day    TEXT,                  -- YYYY-MM-DD
            count  INTEGER DEFAULT 0,
            PRIMARY KEY (tg_id, day)
        );

        CREATE TABLE IF NOT EXISTS weekly_likes (
            tg_id  INTEGER,
            week   TEXT,                  -- YYYY-Www
            count  INTEGER DEFAULT 0,
            PRIMARY KEY (tg_id, week)
        );

        CREATE TABLE IF NOT EXISTS viewed (
            viewer_id  INTEGER,
            target_id  INTEGER,
            viewed_at  TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (viewer_id, target_id)
        );
        """)
        await db.commit()


# ─── USERS ────────────────────────────────────────────────

async def get_user(tg_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE tg_id=?", (tg_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def upsert_user(tg_id: int, username: str | None, gender: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (tg_id, username, gender)
            VALUES (?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET
                username=excluded.username,
                last_active=datetime('now')
        """, (tg_id, username, gender))
        await db.commit()


async def set_gender(tg_id: int, gender: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET gender=? WHERE tg_id=?", (gender, tg_id)
        )
        await db.commit()


async def set_premium(tg_id: int, until_date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET is_premium=1, premium_until=?
            WHERE tg_id=?
        """, (until_date, tg_id))
        await db.commit()


async def ban_user(tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=1 WHERE tg_id=?", (tg_id,))
        await db.commit()


async def unban_user(tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=0 WHERE tg_id=?", (tg_id,))
        await db.commit()


# ─── PROFILES ─────────────────────────────────────────────

async def get_profile(tg_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT p.*, u.gender, u.username, u.is_premium
            FROM profiles p JOIN users u ON p.tg_id=u.tg_id
            WHERE p.tg_id=?
        """, (tg_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def save_profile(tg_id: int, name: str, age: int, city: str, about: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO profiles (tg_id, name, age, city, about)
            VALUES (?,?,?,?,?)
            ON CONFLICT(tg_id) DO UPDATE SET
                name=excluded.name, age=excluded.age,
                city=excluded.city, about=excluded.about,
                updated_at=datetime('now')
        """, (tg_id, name, age, city, about))
        await db.commit()


async def save_photos(tg_id: int, file_ids: list[str]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM photos WHERE tg_id=?", (tg_id,))
        await db.executemany(
            "INSERT INTO photos (tg_id, file_id) VALUES (?,?)",
            [(tg_id, fid) for fid in file_ids]
        )
        await db.commit()


async def get_photos(tg_id: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT file_id FROM photos WHERE tg_id=? LIMIT 3", (tg_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def delete_profile(tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM photos WHERE tg_id=?", (tg_id,))
        await db.execute("DELETE FROM profiles WHERE tg_id=?", (tg_id,))
        await db.execute("DELETE FROM users WHERE tg_id=?", (tg_id,))
        await db.commit()


# ─── FEED (следующая анкета для просмотра) ────────────────

async def get_next_profile(viewer_id: int, viewer_gender: str) -> dict | None:
    """
    Возвращает следующую анкету для просмотра.
    Сортировка: одинаковый город → возраст близкий → премиум выше.
    Исключает: уже просмотренных, себя, свой пол, забаненных.
    """
    target_gender = "female" if viewer_gender == "male" else "male"

    # Город зрителя
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT city, age FROM profiles WHERE tg_id=?", (viewer_id,)
        ) as cur:
            viewer_row = await cur.fetchone()

        viewer_city = viewer_row["city"] if viewer_row else ""
        viewer_age  = viewer_row["age"]  if viewer_row else 25

        async with db.execute("""
            SELECT p.*, u.gender, u.username, u.is_premium
            FROM profiles p
            JOIN users u ON p.tg_id = u.tg_id
            WHERE u.gender = ?
              AND u.is_banned = 0
              AND p.tg_id != ?
              AND p.tg_id NOT IN (
                  SELECT target_id FROM viewed WHERE viewer_id=?
              )
            ORDER BY
                (p.city = ?) DESC,
                u.is_premium DESC,
                ABS(p.age - ?) ASC
            LIMIT 1
        """, (target_gender, viewer_id, viewer_id, viewer_city, viewer_age)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def mark_viewed(viewer_id: int, target_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO viewed (viewer_id, target_id)
            VALUES (?,?)
        """, (viewer_id, target_id))
        await db.commit()


async def reset_viewed(viewer_id: int):
    """Сбросить историю просмотров (когда анкеты закончились)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM viewed WHERE viewer_id=?", (viewer_id,))
        await db.commit()


async def get_last_viewed(viewer_id: int) -> int | None:
    """ID последней просмотренной анкеты (для возврата назад)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT target_id FROM viewed
            WHERE viewer_id=?
            ORDER BY viewed_at DESC LIMIT 1
        """, (viewer_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def unview_last(viewer_id: int, target_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM viewed WHERE viewer_id=? AND target_id=?",
            (viewer_id, target_id)
        )
        await db.commit()


# ─── LIKES ────────────────────────────────────────────────

async def add_like(
    from_id: int, to_id: int, value: int,
    msg_text: str = None, msg_file: str = None, msg_type: str = None
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO likes (from_id, to_id, value, message_text, message_file_id, message_type)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(from_id, to_id) DO UPDATE SET
                value=excluded.value,
                message_text=excluded.message_text,
                message_file_id=excluded.message_file_id,
                message_type=excluded.message_type,
                created_at=datetime('now')
        """, (from_id, to_id, value, msg_text, msg_file, msg_type))
        await db.commit()


async def is_mutual_like(user_a: int, user_b: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT COUNT(*) FROM likes
            WHERE ((from_id=? AND to_id=? AND value=1)
                OR (from_id=? AND to_id=? AND value=1))
        """, (user_a, user_b, user_b, user_a)) as cur:
            row = await cur.fetchone()
            return row[0] == 2


async def get_mutual_likes(tg_id: int) -> list[dict]:
    """Список взаимных лайков."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT u.tg_id, u.username, p.name, p.age, p.city
            FROM likes l1
            JOIN likes l2 ON l1.from_id=l2.to_id AND l1.to_id=l2.from_id
            JOIN users u ON u.tg_id=l1.to_id
            JOIN profiles p ON p.tg_id=l1.to_id
            WHERE l1.from_id=? AND l1.value=1 AND l2.value=1
        """, (tg_id,)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_incoming_likes(tg_id: int) -> list[dict]:
    """Кто поставил лайк мне (только лайки, не взаимные)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT l.from_id, l.message_text, l.message_file_id, l.message_type,
                   u.username, p.name, p.age, p.city
            FROM likes l
            JOIN users u ON u.tg_id=l.from_id
            JOIN profiles p ON p.tg_id=l.from_id
            WHERE l.to_id=? AND l.value=1
        """, (tg_id,)) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ─── ЛИМИТЫ ЛАЙКОВ ────────────────────────────────────────

async def get_today_likes(tg_id: int) -> int:
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count FROM daily_likes WHERE tg_id=? AND day=?",
            (tg_id, today)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def increment_today_likes(tg_id: int):
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO daily_likes (tg_id, day, count) VALUES (?,?,1)
            ON CONFLICT(tg_id, day) DO UPDATE SET count=count+1
        """, (tg_id, today))
        await db.commit()


async def get_week_likes(tg_id: int) -> int:
    week = date.today().strftime("%Y-W%W")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count FROM weekly_likes WHERE tg_id=? AND week=?",
            (tg_id, week)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def increment_week_likes(tg_id: int):
    week = date.today().strftime("%Y-W%W")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO weekly_likes (tg_id, week, count) VALUES (?,?,1)
            ON CONFLICT(tg_id, week) DO UPDATE SET count=count+1
        """, (tg_id, week))
        await db.commit()
