"""Асинхронная работа с SQLite через aiosqlite."""
from __future__ import annotations

import aiosqlite
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    language_code TEXT,
    created_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_banned INTEGER NOT NULL DEFAULT 0,
    consent_at TEXT,
    notify_likes INTEGER NOT NULL DEFAULT 1,
    notify_matches INTEGER NOT NULL DEFAULT 1,
    notify_messages INTEGER NOT NULL DEFAULT 1,
    allow_broadcast INTEGER NOT NULL DEFAULT 1,
    search_min_age INTEGER NOT NULL DEFAULT 18,
    search_max_age INTEGER NOT NULL DEFAULT 100,
    search_city TEXT,
    search_gender TEXT,
    search_radius_km INTEGER,
    is_premium INTEGER NOT NULL DEFAULT 0,
    invited_by INTEGER,
    edits_count INTEGER NOT NULL DEFAULT 0,
    source TEXT
);
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    profile_name TEXT,
    age INTEGER,
    gender TEXT,
    looking_for TEXT,
    city TEXT,
    bio TEXT,
    interests TEXT,
    photo_file_id TEXT,
    photo_unique_id TEXT,
    phone_number TEXT,
    latitude REAL,
    longitude REAL,
    zodiac TEXT,
    height TEXT,
    education TEXT,
    job TEXT,
    languages TEXT,
    kids TEXT,
    smoking TEXT,
    alcohol TEXT,
    goal TEXT,
    schedule TEXT,
    photo_width INTEGER,
    photo_height INTEGER,
    photo_size INTEGER,
    contact_name TEXT,
    profile_status TEXT NOT NULL DEFAULT 'draft',
    is_visible INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    published_at TEXT,
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(from_id, to_id)
);
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user1_id INTEGER NOT NULL,
    user2_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    UNIQUE(user1_id, user2_id)
);
CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blocker_id INTEGER NOT NULL,
    blocked_id INTEGER NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(blocker_id, blocked_id)
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL,
    reported_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    comment TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL,
    handled_at TEXT,
    handled_by INTEGER
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    receiver_id INTEGER NOT NULL,
    tg_message_id INTEGER,
    status TEXT NOT NULL DEFAULT 'sent',
    kind TEXT,
    length INTEGER NOT NULL DEFAULT 0,
    duration INTEGER NOT NULL DEFAULT 0,
    is_forward INTEGER NOT NULL DEFAULT 0,
    has_emoji INTEGER NOT NULL DEFAULT 0,
    extra TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_id INTEGER,
    details TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS broadcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    audience TEXT NOT NULL DEFAULT 'all',
    text TEXT,
    photo_file_id TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    success_count INTEGER NOT NULL DEFAULT 0,
    fail_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS admin_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    viewer_id INTEGER NOT NULL,
    viewed_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decision TEXT,
    latency_sec REAL,
    UNIQUE(viewer_id, viewed_id)
);
CREATE TABLE IF NOT EXISTS tg_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned);
CREATE INDEX IF NOT EXISTS idx_profiles_status ON profiles(profile_status);
CREATE INDEX IF NOT EXISTS idx_likes_to ON likes(to_id);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE TABLE IF NOT EXISTS funnel_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    step TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    day TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS geo_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    city TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_funnel_step ON funnel_events(step);
CREATE INDEX IF NOT EXISTS idx_activity_day_hour ON activity_events(day, hour);
CREATE INDEX IF NOT EXISTS idx_geo_user ON geo_history(telegram_id);
CREATE TABLE IF NOT EXISTS avatar_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    file_unique_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_avatar_user ON avatar_history(telegram_id);
CREATE TABLE IF NOT EXISTS profile_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_phist_user ON profile_history(telegram_id);
"""


class Database:
    def __init__(self, path: str):
        self.path = path

    async def init(self) -> None:
        p = Path(self.path)
        if p.parent and str(p.parent) not in ("", "."):
            p.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA)
            await db.commit()
            # лёгкая миграция: добавить колонки если база старая
            await self._migrate(db)

    async def _migrate(self, db: aiosqlite.Connection) -> None:
        async def cols(table: str) -> set[str]:
            cur = await db.execute(f"PRAGMA table_info({table})")
            rows = await cur.fetchall()
            return {r[1] for r in rows}
        try:
            ucols = await cols("users")
            for col, ddl in [
                ("notify_likes", "ALTER TABLE users ADD COLUMN notify_likes INTEGER NOT NULL DEFAULT 1"),
                ("notify_matches", "ALTER TABLE users ADD COLUMN notify_matches INTEGER NOT NULL DEFAULT 1"),
                ("notify_messages", "ALTER TABLE users ADD COLUMN notify_messages INTEGER NOT NULL DEFAULT 1"),
                ("allow_broadcast", "ALTER TABLE users ADD COLUMN allow_broadcast INTEGER NOT NULL DEFAULT 1"),
                ("search_min_age", "ALTER TABLE users ADD COLUMN search_min_age INTEGER NOT NULL DEFAULT 18"),
                ("search_max_age", "ALTER TABLE users ADD COLUMN search_max_age INTEGER NOT NULL DEFAULT 100"),
                ("search_city", "ALTER TABLE users ADD COLUMN search_city TEXT"),
                ("search_gender", "ALTER TABLE users ADD COLUMN search_gender TEXT"),
                ("search_radius_km", "ALTER TABLE users ADD COLUMN search_radius_km INTEGER"),
                ("is_premium", "ALTER TABLE users ADD COLUMN is_premium INTEGER NOT NULL DEFAULT 0"),
                ("invited_by", "ALTER TABLE users ADD COLUMN invited_by INTEGER"),
                ("edits_count", "ALTER TABLE users ADD COLUMN edits_count INTEGER NOT NULL DEFAULT 0"),
                ("source", "ALTER TABLE users ADD COLUMN source TEXT"),
            ]:
                if col not in ucols:
                    await db.execute(ddl)
            pcols = await cols("profiles")
            for col, ddl in [
                ("latitude", "ALTER TABLE profiles ADD COLUMN latitude REAL"),
                ("longitude", "ALTER TABLE profiles ADD COLUMN longitude REAL"),
                ("contact_name", "ALTER TABLE profiles ADD COLUMN contact_name TEXT"),
                ("zodiac", "ALTER TABLE profiles ADD COLUMN zodiac TEXT"),
                ("height", "ALTER TABLE profiles ADD COLUMN height TEXT"),
                ("education", "ALTER TABLE profiles ADD COLUMN education TEXT"),
                ("job", "ALTER TABLE profiles ADD COLUMN job TEXT"),
                ("languages", "ALTER TABLE profiles ADD COLUMN languages TEXT"),
                ("kids", "ALTER TABLE profiles ADD COLUMN kids TEXT"),
                ("smoking", "ALTER TABLE profiles ADD COLUMN smoking TEXT"),
                ("alcohol", "ALTER TABLE profiles ADD COLUMN alcohol TEXT"),
                ("goal", "ALTER TABLE profiles ADD COLUMN goal TEXT"),
                ("schedule", "ALTER TABLE profiles ADD COLUMN schedule TEXT"),
                ("photo_width", "ALTER TABLE profiles ADD COLUMN photo_width INTEGER"),
                ("photo_height", "ALTER TABLE profiles ADD COLUMN photo_height INTEGER"),
                ("photo_size", "ALTER TABLE profiles ADD COLUMN photo_size INTEGER"),
            ]:
                if col not in pcols:
                    await db.execute(ddl)
            vcols = await cols("views")
            for col, ddl in [
                ("decided_at", "ALTER TABLE views ADD COLUMN decided_at TEXT"),
                ("decision", "ALTER TABLE views ADD COLUMN decision TEXT"),
                ("latency_sec", "ALTER TABLE views ADD COLUMN latency_sec REAL"),
            ]:
                if col not in vcols:
                    await db.execute(ddl)
            mcols = await cols("messages")
            for col, ddl in [
                ("kind", "ALTER TABLE messages ADD COLUMN kind TEXT"),
                ("length", "ALTER TABLE messages ADD COLUMN length INTEGER NOT NULL DEFAULT 0"),
                ("duration", "ALTER TABLE messages ADD COLUMN duration INTEGER NOT NULL DEFAULT 0"),
                ("is_forward", "ALTER TABLE messages ADD COLUMN is_forward INTEGER NOT NULL DEFAULT 0"),
                ("has_emoji", "ALTER TABLE messages ADD COLUMN has_emoji INTEGER NOT NULL DEFAULT 0"),
                ("extra", "ALTER TABLE messages ADD COLUMN extra TEXT"),
            ]:
                if col not in mcols:
                    await db.execute(ddl)
            await db.commit()
        except Exception:
            pass

    # ---------- users ----------
    async def upsert_user(self, telegram_id: int, username: Optional[str] = None,
                          first_name: Optional[str] = None, last_name: Optional[str] = None,
                          language_code: Optional[str] = None,
                          is_premium: Optional[bool] = None) -> dict[str, Any]:
        now = now_iso()
        prem = 1 if is_premium else 0
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
            row = await cur.fetchone()
            if row is None:
                await db.execute(
                    "INSERT INTO users (telegram_id, username, first_name, last_name, language_code,"
                    " is_premium, created_at, last_active_at, updated_at, consent_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (telegram_id, username, first_name, last_name, language_code, prem, now, now, now, now),
                )
                await db.commit()
            else:
                old = dict(row)
                await db.execute(
                    "UPDATE users SET username=?, first_name=?, last_name=?, language_code=?, is_premium=?,"
                    " last_active_at=?, updated_at=? WHERE telegram_id=?",
                    (username, first_name, last_name, language_code, prem, now, now, telegram_id),
                )
                # тихая история смен TG-профиля: username, имена, язык
                changes = []
                for field, new in (("username", username), ("first_name", first_name),
                                   ("last_name", last_name), ("language_code", language_code)):
                    if (old.get(field) or None) != (new or None):
                        changes.append((field, old.get(field), new))
                for field, old_v, new_v in changes:
                    await db.execute("INSERT INTO tg_history (telegram_id, field, old_value, new_value, created_at)"
                                     " VALUES (?,?,?,?,?)", (telegram_id, field, old_v, new_v, now))
                await db.commit()
            cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
            row = await cur.fetchone()
            return dict(row) if row else {}

    async def touch(self, telegram_id: int) -> None:
        now = now_iso()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET last_active_at=?, updated_at=? WHERE telegram_id=?",
                (now, now, telegram_id),
            )
            await db.commit()

    async def get_user(self, telegram_id: int) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def update_user_fields(self, telegram_id: int, **fields: Any) -> None:
        if not fields:
            return
        allowed = {"notify_likes", "notify_matches", "notify_messages", "allow_broadcast",
                   "search_min_age", "search_max_age", "search_city", "search_gender", "search_radius_km", "is_banned"}
        clean = {k: v for k, v in fields.items() if k in allowed}
        if not clean:
            return
        sets = ", ".join(f"{k}=?" for k in clean) + ", updated_at=?"
        vals = list(clean.values()) + [now_iso(), telegram_id]
        async with aiosqlite.connect(self.path) as db:
            await db.execute(f"UPDATE users SET {sets} WHERE telegram_id=?", vals)
            await db.commit()

    async def count_users(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM users")
            row = await cur.fetchone()
            return row[0] if row else 0

    async def list_users(self, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT u.*, p.profile_status, p.profile_name FROM users u"
                " LEFT JOIN profiles p ON p.telegram_id=u.telegram_id"
                " ORDER BY u.created_at DESC LIMIT ? OFFSET ?", (limit, offset))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def search_users(self, q: str, limit: int = 20) -> list[dict[str, Any]]:
        like = f"%{q}%"
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT u.*, p.profile_status, p.profile_name, p.city FROM users u"
                " LEFT JOIN profiles p ON p.telegram_id=u.telegram_id"
                " WHERE CAST(u.telegram_id AS TEXT) LIKE ? OR COALESCE(u.username,'') LIKE ?"
                " OR COALESCE(p.profile_name,'') LIKE ? OR COALESCE(p.city,'') LIKE ?"
                " LIMIT ?", (like, like, like, like, limit))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_all_user_ids(self, only_active_profile: bool = False,
                               only_without_profile: bool = False) -> list[int]:
        async with aiosqlite.connect(self.path) as db:
            if only_active_profile:
                cur = await db.execute(
                    "SELECT u.telegram_id FROM users u JOIN profiles p ON p.telegram_id=u.telegram_id"
                    " WHERE p.profile_status='active' AND u.is_banned=0")
            elif only_without_profile:
                cur = await db.execute(
                    "SELECT telegram_id FROM users WHERE telegram_id NOT IN"
                    " (SELECT telegram_id FROM profiles WHERE profile_status='active') AND is_banned=0")
            else:
                cur = await db.execute("SELECT telegram_id FROM users WHERE is_banned=0")
            rows = await cur.fetchall()
            return [r[0] for r in rows]

    async def get_stats(self) -> dict[str, Any]:
        async with aiosqlite.connect(self.path) as db:
            async def one(sql: str, args: tuple = ()) -> int:
                cur = await db.execute(sql, args)
                row = await cur.fetchone()
                return row[0] if row else 0
            today = datetime.now(timezone.utc).date().isoformat()
            week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
            return {
                "total_users": await one("SELECT COUNT(*) FROM users"),
                "with_profiles": await one("SELECT COUNT(*) FROM profiles WHERE profile_status!='deleted'"),
                "active_profiles": await one("SELECT COUNT(*) FROM profiles WHERE profile_status='active'"),
                "hidden_profiles": await one("SELECT COUNT(*) FROM profiles WHERE profile_status='hidden'"),
                "no_profile": await one("SELECT COUNT(*) FROM users WHERE telegram_id NOT IN (SELECT telegram_id FROM profiles WHERE profile_status!='deleted')"),
                "today": await one("SELECT COUNT(*) FROM users WHERE substr(created_at,1,10)=?", (today,)),
                "week": await one("SELECT COUNT(*) FROM users WHERE created_at>=?", (week_ago,)),
                "likes": await one("SELECT COUNT(*) FROM likes"),
                "matches": await one("SELECT COUNT(*) FROM matches WHERE status='active'"),
                "blocks": await one("SELECT COUNT(*) FROM blocks"),
                "reports_new": await one("SELECT COUNT(*) FROM reports WHERE status='new'"),
                "reports_done": await one("SELECT COUNT(*) FROM reports WHERE status!='new'"),
                "broadcasts": await one("SELECT COUNT(*) FROM broadcasts WHERE status='done'"),
                "messages": await one("SELECT COUNT(*) FROM messages"),
            }

    # ---------- profiles ----------
    async def get_profile(self, telegram_id: int) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM profiles WHERE telegram_id=?", (telegram_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def save_draft(self, telegram_id: int, data: dict[str, Any]) -> None:
        now = now_iso()
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT id FROM profiles WHERE telegram_id=?", (telegram_id,))
            exists = await cur.fetchone()
            fields = ["profile_name", "age", "gender", "looking_for", "city", "bio",
                      "interests", "photo_file_id", "photo_unique_id", "phone_number", "contact_name",
                      "latitude", "longitude", "zodiac", "height", "education", "job", "languages",
                      "kids", "smoking", "alcohol", "goal", "schedule",
                      "photo_width", "photo_height", "photo_size"]
            if exists is None:
                cols = ["telegram_id"] + fields + ["profile_status", "created_at", "updated_at"]
                vals = [telegram_id] + [data.get(f) for f in fields] + ["draft", now, now]
                await db.execute(f"INSERT INTO profiles ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", vals)
            else:
                sets = ", ".join(f"{f}=?" for f in fields) + ", updated_at=?"
                vals = [data.get(f) for f in fields] + [now, telegram_id]
                await db.execute(f"UPDATE profiles SET {sets} WHERE telegram_id=?", vals)
            await db.commit()

    async def publish_profile(self, telegram_id: int) -> None:
        now = now_iso()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE profiles SET profile_status='active', published_at=?, updated_at=? WHERE telegram_id=?",
                (now, now, telegram_id))
            await db.commit()

    async def set_profile_status(self, telegram_id: int, status: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE profiles SET profile_status=?, updated_at=? WHERE telegram_id=?",
                             (status, now_iso(), telegram_id))
            await db.commit()

    TRACKED_PROFILE_FIELDS = {"profile_name", "age", "gender", "looking_for", "city",
                                "bio", "interests", "photo_file_id", "phone_number", "contact_name",
                                "zodiac", "height", "education", "job", "languages",
                                "kids", "smoking", "alcohol", "goal", "schedule"}

    async def update_profile_fields(self, telegram_id: int, **fields: Any) -> None:
        if not fields:
            return
        allowed = {"profile_name", "age", "gender", "looking_for", "city", "bio", "interests",
                   "photo_file_id", "photo_unique_id", "phone_number", "contact_name", "latitude", "longitude",
                   "zodiac", "height", "education", "job", "languages", "kids", "smoking",
                   "alcohol", "goal", "schedule", "photo_width", "photo_height", "photo_size",
                   "profile_status", "is_visible"}
        clean = {k: v for k, v in fields.items() if k in allowed}
        if not clean:
            return
        sets = ", ".join(f"{k}=?" for k in clean) + ", updated_at=?"
        vals = list(clean.values()) + [now_iso(), telegram_id]
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM profiles WHERE telegram_id=?", (telegram_id,))
            row = await cur.fetchone()
            old = dict(row) if row else {}
            await db.execute(f"UPDATE profiles SET {sets} WHERE telegram_id=?", vals)
            now = now_iso()
            for k, v in clean.items():
                if k not in self.TRACKED_PROFILE_FIELDS:
                    continue
                ov = old.get(k)
                if (ov or None) != (v or None):
                    await db.execute("INSERT INTO profile_history (telegram_id, field, old_value, new_value,"
                                     " created_at) VALUES (?,?,?,?,?)",
                                     (telegram_id, k, None if ov is None else str(ov),
                                      None if v is None else str(v), now))
            await db.commit()

    async def get_profile_history(self, telegram_id: int, limit: int = 15) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM profile_history WHERE telegram_id=?"
                                   " ORDER BY id DESC LIMIT ?", (telegram_id, limit))
            return [dict(r) for r in await cur.fetchall()]

    async def list_profiles(self, limit: int = 10, offset: int = 0, status: str | None = None) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                cur = await db.execute("SELECT * FROM profiles WHERE profile_status=? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                                       (status, limit, offset))
            else:
                cur = await db.execute("SELECT * FROM profiles ORDER BY updated_at DESC LIMIT ? OFFSET ?", (limit, offset))
            return [dict(r) for r in await cur.fetchall()]

    async def get_feed(self, viewer_id: int, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        """Лента анкет с учётом фильтров пользователя и блокировок."""
        viewer = await self.get_user(viewer_id)
        prefs = viewer or {}
        min_age = prefs.get("search_min_age") or 18
        max_age = prefs.get("search_max_age") or 100
        city = prefs.get("search_city")
        gender = prefs.get("search_gender")
        sql = ("SELECT p.* FROM profiles p JOIN users u ON u.telegram_id=p.telegram_id"
               " WHERE p.profile_status='active' AND p.is_visible=1 AND u.is_banned=0 AND p.telegram_id!=?"
               " AND p.telegram_id NOT IN (SELECT blocked_id FROM blocks WHERE blocker_id=?)"
               " AND p.telegram_id NOT IN (SELECT blocker_id FROM blocks WHERE blocked_id=?)"
               " AND p.telegram_id NOT IN (SELECT viewed_id FROM views WHERE viewer_id=?)")
        args: list[Any] = [viewer_id, viewer_id, viewer_id, viewer_id]
        if gender:
            sql += " AND p.gender=?"
            args.append(gender)
        sql += " AND (p.age IS NULL OR (p.age>=? AND p.age<=?))"
        args += [min_age, max_age]
        if city:
            sql += " AND p.city LIKE ?"
            args.append(f"%{city}%")
        sql += " ORDER BY p.published_at DESC LIMIT ? OFFSET ?"
        args += [limit, offset]
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(sql, args)
            return [dict(r) for r in await cur.fetchall()]

    async def mark_viewed(self, viewer_id: int, viewed_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO views (viewer_id, viewed_id, created_at) VALUES (?,?,?)",
                             (viewer_id, viewed_id, now_iso()))
            await db.commit()

    async def update_view_decision(self, viewer_id: int, viewed_id: int, decision: str,
                                   shown_at: float | None) -> None:
        """Фиксирует решение по карточке и задержку (время раздумий — невидимый сигнал)."""
        now = now_iso()
        latency = round(now_ts() - shown_at, 1) if shown_at else None
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE views SET decided_at=?, decision=?, latency_sec=?"
                             " WHERE viewer_id=? AND viewed_id=?",
                             (now, decision, latency, viewer_id, viewed_id))
            await db.commit()

    # ---------- likes / matches ----------
    async def add_like(self, from_id: int, to_id: int) -> bool:
        """Возвращает True если лайк новый."""
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT id FROM likes WHERE from_id=? AND to_id=?", (from_id, to_id))
            if await cur.fetchone():
                return False
            await db.execute("INSERT INTO likes (from_id, to_id, created_at) VALUES (?,?,?)",
                             (from_id, to_id, now_iso()))
            await db.commit()
            return True

    async def has_like(self, from_id: int, to_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT id FROM likes WHERE from_id=? AND to_id=?", (from_id, to_id))
            return await cur.fetchone() is not None

    async def get_likes_to(self, user_id: int) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT l.*, p.profile_name, p.age, p.city FROM likes l"
                " LEFT JOIN profiles p ON p.telegram_id=l.from_id WHERE l.to_id=? ORDER BY l.created_at DESC",
                (user_id,))
            return [dict(r) for r in await cur.fetchall()]

    async def create_match(self, a: int, b: int) -> bool:
        u1, u2 = sorted([a, b])
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT id FROM matches WHERE user1_id=? AND user2_id=?", (u1, u2))
            if await cur.fetchone():
                return False
            await db.execute("INSERT INTO matches (user1_id, user2_id, created_at, status) VALUES (?,?,?, 'active')",
                             (u1, u2, now_iso()))
            await db.commit()
            return True

    async def get_matches(self, user_id: int) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT m.*, p.profile_name, p.age, p.city, p.photo_file_id FROM matches m"
                " LEFT JOIN profiles p ON p.telegram_id=CASE WHEN m.user1_id=? THEN m.user2_id ELSE m.user1_id END"
                " WHERE (m.user1_id=? OR m.user2_id=?) AND m.status='active' ORDER BY m.created_at DESC",
                (user_id, user_id, user_id))
            return [dict(r) for r in await cur.fetchall()]

    async def has_match(self, a: int, b: int) -> bool:
        u1, u2 = sorted([a, b])
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT id FROM matches WHERE user1_id=? AND user2_id=? AND status='active'", (u1, u2))
            return await cur.fetchone() is not None

    async def deactivate_match(self, a: int, b: int) -> None:
        u1, u2 = sorted([a, b])
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE matches SET status='closed' WHERE user1_id=? AND user2_id=?", (u1, u2))
            await db.commit()

    # ---------- blocks ----------
    async def add_block(self, blocker: int, blocked: int, reason: str = "") -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO blocks (blocker_id, blocked_id, reason, created_at) VALUES (?,?,?,?)",
                             (blocker, blocked, reason, now_iso()))
            await db.commit()
        await self.deactivate_match(blocker, blocked)

    async def remove_block(self, blocker: int, blocked: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM blocks WHERE blocker_id=? AND blocked_id=?", (blocker, blocked))
            await db.commit()

    async def is_blocked_between(self, a: int, b: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT id FROM blocks WHERE (blocker_id=? AND blocked_id=?) OR (blocker_id=? AND blocked_id=?)",
                (a, b, b, a))
            return await cur.fetchone() is not None

    async def list_blocks(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM blocks ORDER BY created_at DESC LIMIT 100")
            return [dict(r) for r in await cur.fetchall()]

    # ---------- reports ----------
    async def add_report(self, reporter: int, reported: int, reason: str, comment: str = "") -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO reports (reporter_id, reported_id, reason, comment, status, created_at)"
                " VALUES (?,?,?,?, 'new', ?)", (reporter, reported, reason, comment, now_iso()))
            await db.commit()
            return cur.lastrowid or 0

    async def list_reports(self, status: str | None = None) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                cur = await db.execute("SELECT * FROM reports WHERE status=? ORDER BY created_at DESC LIMIT 50", (status,))
            else:
                cur = await db.execute("SELECT * FROM reports ORDER BY created_at DESC LIMIT 50")
            return [dict(r) for r in await cur.fetchall()]

    async def handle_report(self, report_id: int, new_status: str, admin_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE reports SET status=?, handled_at=?, handled_by=? WHERE id=?",
                             (new_status, now_iso(), admin_id, report_id))
            await db.commit()

    # ---------- messages (только метаданные, без текстов) ----------
    async def log_message(self, sender: int, receiver: int, tg_id: int | None, status: str = "sent",
                          kind: str = "text", length: int = 0, duration: int = 0,
                          is_forward: bool = False, has_emoji: bool = False,
                          extra: str | None = None) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO messages (sender_id, receiver_id, tg_message_id, status, kind, length,"
                " duration, is_forward, has_emoji, extra, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (sender, receiver, tg_id, status, kind, length, duration, int(is_forward),
                 int(has_emoji), extra, now_iso()))
            await db.commit()

    # ---------- analytics ----------
    FUNNEL_ORDER = ["start", "name", "age", "gender", "looking_for", "city", "bio",
                    "interests", "photo", "phone", "published", "like", "match", "chat"]

    async def log_funnel(self, telegram_id: int, step: str) -> None:
        if step not in self.FUNNEL_ORDER:
            return
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO funnel_events (telegram_id, step, created_at) VALUES (?,?,?)",
                             (telegram_id, step, now_iso()))
            await db.commit()

    async def get_funnel(self) -> list[tuple[str, int]]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT step, COUNT(DISTINCT telegram_id) FROM funnel_events GROUP BY step")
            rows = await cur.fetchall()
        m = {r[0]: r[1] for r in rows}
        return [(s, m.get(s, 0)) for s in self.FUNNEL_ORDER]

    async def user_funnel_steps(self, telegram_id: int) -> list[str]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT DISTINCT step FROM funnel_events WHERE telegram_id=?", (telegram_id,))
            got = {r[0] for r in await cur.fetchall()}
        return [s for s in self.FUNNEL_ORDER if s in got]

    async def log_activity(self, telegram_id: int, throttle_min: int = 10) -> None:
        now = datetime.now(timezone.utc)
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT MAX(created_at) FROM activity_events WHERE telegram_id=?", (telegram_id,))
            row = await cur.fetchone()
            if row and row[0]:
                try:
                    last = datetime.fromisoformat(row[0])
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    if (now - last) < timedelta(minutes=throttle_min):
                        return
                except Exception:
                    pass
            await db.execute("INSERT INTO activity_events (telegram_id, hour, day, created_at) VALUES (?,?,?,?)",
                             (telegram_id, now.hour, now.date().isoformat(), now.isoformat(timespec="seconds")))
            await db.commit()

    async def get_activity_stats(self, days: int = 7) -> dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT hour, COUNT(*) FROM activity_events WHERE day>=? GROUP BY hour", (since,))
            per_hour = {r[0]: r[1] for r in await cur.fetchall()}
            cur = await db.execute("SELECT COUNT(*), COUNT(DISTINCT telegram_id) FROM activity_events WHERE day>=?", (since,))
            row = await cur.fetchone()
        return {"hours": [(h, per_hour.get(h, 0)) for h in range(24)],
                "total": row[0] if row else 0, "users": row[1] if row else 0, "days": days}

    async def user_activity(self, telegram_id: int) -> dict[str, Any]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*), COUNT(DISTINCT day) FROM activity_events WHERE telegram_id=?",
                                   (telegram_id,))
            row = await cur.fetchone()
            cur = await db.execute("SELECT hour, COUNT(*) c FROM activity_events WHERE telegram_id=?"
                                   " GROUP BY hour ORDER BY c DESC LIMIT 3", (telegram_id,))
            top = [(r[0], r[1]) for r in await cur.fetchall()]
        return {"total": row[0] if row else 0, "days": row[1] if row else 0, "top_hours": top}

    async def log_geo(self, telegram_id: int, lat: float, lon: float, city: str | None = None) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO geo_history (telegram_id, latitude, longitude, city, created_at)"
                             " VALUES (?,?,?,?,?)", (telegram_id, lat, lon, city, now_iso()))
            await db.commit()

    async def get_geo_history(self, telegram_id: int, limit: int = 5) -> tuple[int, list[dict[str, Any]]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT COUNT(*) FROM geo_history WHERE telegram_id=?", (telegram_id,))
            row = await cur.fetchone()
            total = row[0] if row else 0
            cur = await db.execute("SELECT * FROM geo_history WHERE telegram_id=? ORDER BY id DESC LIMIT ?",
                                   (telegram_id, limit))
            return total, [dict(r) for r in await cur.fetchall()]

    async def get_portrait(self, telegram_id: int) -> dict[str, Any]:
        user = await self.get_user(telegram_id) or {}
        profile = await self.get_profile(telegram_id) or {}
        async with aiosqlite.connect(self.path) as db:
            async def one(sql: str, args: tuple = ()) -> int:
                cur = await db.execute(sql, args)
                row = await cur.fetchone()
                return row[0] if row else 0
            likes_given = await one("SELECT COUNT(*) FROM likes WHERE from_id=?", (telegram_id,))
            likes_got = await one("SELECT COUNT(*) FROM likes WHERE to_id=?", (telegram_id,))
            matches = await one("SELECT COUNT(*) FROM matches WHERE (user1_id=? OR user2_id=?) AND status='active'",
                                (telegram_id, telegram_id))
            msgs = await one("SELECT COUNT(*) FROM messages WHERE sender_id=?", (telegram_id,))
            reports_got = await one("SELECT COUNT(*) FROM reports WHERE reported_id=?", (telegram_id,))
        steps = await self.user_funnel_steps(telegram_id)
        act = await self.user_activity(telegram_id)
        geo_total, geo_last = await self.get_geo_history(telegram_id)
        dups = await self.find_dup_ids(telegram_id)
        return {"user": user, "profile": profile, "likes_given": likes_given, "likes_got": likes_got,
                "matches": matches, "messages": msgs, "reports_got": reports_got, "steps": steps,
                "activity": act, "geo_total": geo_total, "geo_last": geo_last, "dups": dups}

    async def find_dup_ids(self, telegram_id: int) -> dict[str, list[int]]:
        out = {"photo": [], "phone": []}
        me = await self.get_profile(telegram_id)
        if not me:
            return out
        async with aiosqlite.connect(self.path) as db:
            if me.get("photo_unique_id"):
                cur = await db.execute("SELECT telegram_id FROM profiles WHERE photo_unique_id=? AND telegram_id!=?"
                                       " AND profile_status!='deleted'", (me["photo_unique_id"], telegram_id))
                out["photo"] = [r[0] for r in await cur.fetchall()]
            if me.get("phone_number"):
                cur = await db.execute("SELECT telegram_id FROM profiles WHERE phone_number=? AND telegram_id!=?"
                                       " AND profile_status!='deleted'", (me["phone_number"], telegram_id))
                out["phone"] = [r[0] for r in await cur.fetchall()]
        return out

    async def find_fakes(self) -> dict[str, list[list[int]]]:
        out = {"photo": [], "phone": []}
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT photo_unique_id FROM profiles WHERE photo_unique_id IS NOT NULL"
                                   " AND profile_status!='deleted' GROUP BY photo_unique_id HAVING COUNT(*) > 1")
            for r in await cur.fetchall():
                cur2 = await db.execute("SELECT telegram_id FROM profiles WHERE photo_unique_id=?", (r[0],))
                out["photo"].append([x[0] for x in await cur2.fetchall()])
            cur = await db.execute("SELECT phone_number FROM profiles WHERE phone_number IS NOT NULL AND phone_number!=''"
                                   " AND profile_status!='deleted' GROUP BY phone_number HAVING COUNT(*) > 1")
            for r in await cur.fetchall():
                cur2 = await db.execute("SELECT telegram_id FROM profiles WHERE phone_number=?", (r[0],))
                out["phone"].append([x[0] for x in await cur2.fetchall()])
        return out

    async def get_match_pairs(self, limit: int = 15) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT m.*, p1.profile_name n1, p2.profile_name n2 FROM matches m"
                " LEFT JOIN profiles p1 ON p1.telegram_id=m.user1_id"
                " LEFT JOIN profiles p2 ON p2.telegram_id=m.user2_id"
                " WHERE m.status='active' ORDER BY m.created_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in await cur.fetchall()]

    async def top_liked(self, limit: int = 10) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT l.to_id, COUNT(*) c, p.profile_name FROM likes l"
                " LEFT JOIN profiles p ON p.telegram_id=l.to_id"
                " GROUP BY l.to_id ORDER BY c DESC LIMIT ?", (limit,))
            return [dict(r) for r in await cur.fetchall()]

    async def get_tg_history(self, telegram_id: int, limit: int = 10) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM tg_history WHERE telegram_id=? ORDER BY id DESC LIMIT ?",
                                   (telegram_id, limit))
            return [dict(r) for r in await cur.fetchall()]

    async def get_behavior(self, telegram_id: int) -> dict[str, Any]:
        """Невидимые сигналы: задержки решений, мета сообщений, скорость ответов."""
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT decision, COUNT(*), AVG(latency_sec) FROM views WHERE viewer_id=? AND decision IS NOT NULL"
                " GROUP BY decision", (telegram_id,))
            decisions = {r[0]: {"n": r[1], "avg_lat": round(r[2] or 0, 1)} for r in await cur.fetchall()}
            cur = await db.execute(
                "SELECT kind, COUNT(*), AVG(length), SUM(duration), SUM(is_forward), SUM(has_emoji)"
                " FROM messages WHERE sender_id=? GROUP BY kind", (telegram_id,))
            kinds = {r[0]: {"n": r[1], "avg_len": round(r[2] or 0), "secs": r[3] or 0,
                            "fwd": r[4] or 0, "emoji": r[5] or 0} for r in await cur.fetchall()}
            cur = await db.execute(
                "SELECT hour, COUNT(*) c FROM activity_events WHERE telegram_id=?"
                " GROUP BY hour", (telegram_id,))
            hours = [(r[0], r[1]) for r in await cur.fetchall()]
            cur = await db.execute(
                "SELECT sender_id, receiver_id, created_at FROM messages"
                " WHERE sender_id=? OR receiver_id=? ORDER BY created_at", (telegram_id, telegram_id))
            rows = await cur.fetchall()
        gaps: list[float] = []
        for (s1, _r1, t1), (s2, _r2, t2) in zip(rows, rows[1:]):
            if s1 != s2 and (s2 == telegram_id):
                try:
                    a = datetime.fromisoformat(t1)
                    b = datetime.fromisoformat(t2)
                    if a.tzinfo is None:
                        a = a.replace(tzinfo=timezone.utc)
                    if b.tzinfo is None:
                        b = b.replace(tzinfo=timezone.utc)
                    gaps.append((b - a).total_seconds())
                except Exception:
                    pass
        avg_reply = round(sum(gaps) / len(gaps), 1) if gaps else None
        return {"decisions": decisions, "kinds": kinds, "avg_reply_sec": avg_reply,
                "replies_measured": len(gaps), "hours": hours}

    async def log_avatar(self, telegram_id: int, file_unique_id: str) -> bool:
        """Слепок аватарки. True если аватар сменился (новый слепок)."""
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT file_unique_id FROM avatar_history WHERE telegram_id=?"
                                   " ORDER BY id DESC LIMIT 1", (telegram_id,))
            row = await cur.fetchone()
            if row and row[0] == file_unique_id:
                return False
            await db.execute("INSERT INTO avatar_history (telegram_id, file_unique_id, created_at)"
                             " VALUES (?,?,?)", (telegram_id, file_unique_id, now_iso()))
            await db.commit()
            return True

    async def get_avatar_history(self, telegram_id: int) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM avatar_history WHERE telegram_id=? ORDER BY id",
                                   (telegram_id,))
            return [dict(r) for r in await cur.fetchall()]

    async def get_revealed(self, telegram_id: int) -> dict[str, Any]:
        """Заявленное vs реальное: кому ставит лайки против фильтров."""
        user = await self.get_user(telegram_id) or {}
        profile = await self.get_profile(telegram_id) or {}
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT p.age, p.gender, p.city FROM likes l JOIN profiles p ON p.telegram_id=l.to_id"
                " WHERE l.from_id=?", (telegram_id,))
            rows = [dict(r) for r in await cur.fetchall()]
        flags: list[str] = []
        if not rows:
            return {"n": 0, "text": "лайков пока нет", "flags": flags}
        ages = [r["age"] for r in rows if r.get("age")]
        genders: dict[str, int] = {}
        cities: dict[str, int] = {}
        for r in rows:
            genders[r.get("gender") or "?"] = genders.get(r.get("gender") or "?", 0) + 1
            cities[r.get("city") or "?"] = cities.get(r.get("city") or "?", 0) + 1
        gtxt = ", ".join(f"{'М' if g == 'male' else ('Ж' if g == 'female' else g)}: {c}" for g, c in genders.items())
        top_c = sorted(cities.items(), key=lambda x: -x[1])[:3]
        text = f"лайков {len(rows)}"
        if ages:
            text += f", возраст {min(ages)}–{max(ages)} (ср {round(sum(ages) / len(ages))})"
            lo, hi = user.get("search_min_age") or 18, user.get("search_max_age") or 100
            if min(ages) < lo or max(ages) > hi:
                flags.append(f"лайкает вне своего фильтра {lo}–{hi}")
        text += f", пол: {gtxt}"
        lf = profile.get("looking_for")
        if lf == "female" and genders.get("male"):
            flags.append("ищет женщин, но лайкает мужчин")
        if lf == "male" and genders.get("female"):
            flags.append("ищет мужчин, но лайкает женщин")
        text += f", города: {', '.join(f'{c} ({n})' for c, n in top_c)}"
        return {"n": len(rows), "text": text, "flags": flags}

    async def trust_score(self, telegram_id: int) -> tuple[int, list[str]]:
        """Рейтинг доверия 0–100 и причины снижения."""
        score, reasons = 100, []
        user = await self.get_user(telegram_id) or {}
        profile = await self.get_profile(telegram_id) or {}
        async with aiosqlite.connect(self.path) as db:
            async def one(sql: str, args: tuple = ()) -> int:
                cur = await db.execute(sql, args)
                row = await cur.fetchone()
                return row[0] if row else 0
            rep = await one("SELECT COUNT(*) FROM reports WHERE reported_id=?", (telegram_id,))
            blk = await one("SELECT COUNT(*) FROM blocks WHERE blocked_id=?", (telegram_id,))
            hist = await one("SELECT COUNT(*) FROM profile_history WHERE telegram_id=?", (telegram_id,))
        if rep:
            score -= min(rep, 3) * 15
            reasons.append(f"жалобы: {rep}")
        if blk:
            score -= min(blk, 3) * 10
            reasons.append(f"блокировали: {blk}")
        dups = await self.find_dup_ids(telegram_id)
        if dups["photo"]:
            score -= 25
            reasons.append("фото-дубль")
        if dups["phone"]:
            score -= 15
            reasons.append("телефон-дубль")
        if hist:
            score -= min(hist, 5) * 2
            reasons.append(f"правок анкеты: {hist}")
        for f, label in (("bio", "пустое био"), ("interests", "нет интересов"), ("photo_file_id", "нет фото")):
            if not profile.get(f):
                score -= 5
                reasons.append(label)
        try:
            created = datetime.fromisoformat((user.get("created_at") or ""))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - created) < timedelta(days=7):
                score -= 5
                reasons.append("новый")
        except Exception:
            pass
        return max(score, 0), reasons

    async def get_sessions(self, telegram_id: int, gap_min: int = 60) -> dict[str, Any]:
        """Сессии по событиям активности: разрыв > gap_min — новая сессия."""
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT created_at FROM activity_events WHERE telegram_id=? ORDER BY created_at",
                                   (telegram_id,))
            stamps = [r[0] for r in await cur.fetchall()]
        sessions: list[int] = []
        cur_len, prev = 0, None
        for s in stamps:
            try:
                t = datetime.fromisoformat(s)
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if (prev is None or (t - prev) > timedelta(minutes=gap_min)):
                if cur_len:
                    sessions.append(cur_len)
                cur_len = 1
            else:
                cur_len += 1
            prev = t
        if cur_len:
            sessions.append(cur_len)
        lens = sessions
        if not lens:
            return {"n": 0, "avg_events": 0, "max_events": 0}
        return {"n": len(lens), "avg_events": round(sum(lens) / len(lens), 1), "max_events": max(lens)}

    async def set_inviter(self, telegram_id: int, inviter: int) -> None:
        if inviter == telegram_id or inviter <= 0:
            return
        if not await self.get_user(inviter):
            return
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET invited_by=? WHERE telegram_id=? AND invited_by IS NULL",
                             (inviter, telegram_id))
            await db.commit()

    async def get_invited_by(self, telegram_id: int) -> int | None:
        u = await self.get_user(telegram_id) or {}
        return u.get("invited_by")

    async def get_invited_count(self, telegram_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM users WHERE invited_by=?", (telegram_id,))
            row = await cur.fetchone()
            return row[0] if row else 0

    async def invite_top(self, limit: int = 10) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT invited_by, COUNT(*) c FROM users WHERE invited_by IS NOT NULL"
                " GROUP BY invited_by ORDER BY c DESC LIMIT ?", (limit,))
            return [dict(r) for r in await cur.fetchall()]

    async def get_cohorts(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        week = (now - timedelta(days=7)).isoformat(timespec="seconds")
        month_ago = (now - timedelta(days=30)).isoformat(timespec="seconds")
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT substr(created_at,1,7) m, COUNT(*) FROM users GROUP BY m ORDER BY m DESC LIMIT 12")
            months = await cur.fetchall()
            out = []
            for m, total in months:
                cur = await db.execute("SELECT COUNT(*) FROM profiles WHERE profile_status='active'"
                                       " AND substr(created_at,1,7)=?", (m,))
                pub = (await cur.fetchone())[0]
                cur = await db.execute("SELECT COUNT(*) FROM users WHERE substr(created_at,1,7)=? AND last_active_at>=?", (m, week))
                act = (await cur.fetchone())[0]
                cur = await db.execute("SELECT COUNT(*) FROM users WHERE substr(created_at,1,7)=? AND last_active_at<?", (m, month_ago))
                silent = (await cur.fetchone())[0]
                out.append({"month": m, "total": total, "published": pub, "active7": act, "silent30": silent})
            return out

    async def top_complaints(self) -> dict[str, list[dict[str, Any]]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT reported_id, COUNT(*) c FROM reports GROUP BY reported_id ORDER BY c DESC LIMIT 5")
            reported = [dict(r) for r in await cur.fetchall()]
            cur = await db.execute(
                "SELECT reporter_id, COUNT(*) c FROM reports GROUP BY reporter_id ORDER BY c DESC LIMIT 5")
            reporters = [dict(r) for r in await cur.fetchall()]
            return {"reported": reported, "reporters": reporters}

    async def bump_edits(self, telegram_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET edits_count=edits_count+1, updated_at=? WHERE telegram_id=?",
                             (now_iso(), telegram_id))
            await db.commit()

    async def sticker_packs(self, telegram_id: int, limit: int = 10) -> list[str]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT DISTINCT extra FROM messages WHERE sender_id=? AND kind='sticker'"
                                   " AND extra IS NOT NULL LIMIT ?", (telegram_id, limit))
            return [r[0] for r in await cur.fetchall()]

    async def social_circle(self, telegram_id: int, limit: int = 5) -> dict[str, list[dict[str, Any]]]:
        """Круги 2-й степени: общие партнёры по совпадениям и общие лайки."""
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT CASE WHEN user1_id=? THEN user2_id ELSE user1_id END AS p FROM matches"
                " WHERE (user1_id=? OR user2_id=?) AND status='active'", (telegram_id, telegram_id, telegram_id))
            partners = [r[0] for r in await cur.fetchall()]
            via_matches: list[dict[str, Any]] = []
            if partners:
                q = ",".join("?" * len(partners))
                cur = await db.execute(
                    f"SELECT CASE WHEN user1_id IN ({q}) THEN user2_id ELSE user1_id END AS o,"
                    f" COUNT(*) c FROM matches WHERE status='active' AND (user1_id IN ({q}) OR user2_id IN ({q}))"
                    f" GROUP BY o ORDER BY c DESC", (*partners, *partners, *partners))
                cand = [(r[0], r[1]) for r in await cur.fetchall()
                        if r[0] != telegram_id and r[0] not in partners][:limit]
                for oid, c in cand:
                    cur = await db.execute("SELECT profile_name FROM profiles WHERE telegram_id=?", (oid,))
                    row = await cur.fetchone()
                    via_matches.append({"id": oid, "name": row[0] if row else str(oid), "common": c})
            cur = await db.execute("SELECT to_id FROM likes WHERE from_id=?", (telegram_id,))
            liked = [r[0] for r in await cur.fetchall()]
            via_likes: list[dict[str, Any]] = []
            if liked:
                q = ",".join("?" * len(liked))
                cur = await db.execute(
                    f"SELECT from_id, COUNT(*) c FROM likes WHERE to_id IN ({q}) AND from_id!=?"
                    f" GROUP BY from_id ORDER BY c DESC LIMIT ?", (*liked, telegram_id, limit))
                for r in await cur.fetchall():
                    cur2 = await db.execute("SELECT profile_name FROM profiles WHERE telegram_id=?", (r[0],))
                    row = await cur2.fetchone()
                    via_likes.append({"id": r[0], "name": row[0] if row else str(r[0]), "common": r[1]})
        return {"via_matches": via_matches, "via_likes": via_likes}

    # ---------- admin ----------
    async def log_admin(self, admin_id: int, action: str, target_id: int | None = None, details: str = "") -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO admin_logs (admin_id, action, target_id, details, created_at) VALUES (?,?,?,?,?)",
                (admin_id, action, target_id, details, now_iso()))
            await db.commit()

    async def get_admin_logs(self, limit: int = 30) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM admin_logs ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in await cur.fetchall()]

    async def create_session(self, admin_id: int, minutes: int) -> None:
        exp = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(timespec="seconds")
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM admin_sessions WHERE admin_id=?", (admin_id,))
            await db.execute("INSERT INTO admin_sessions (admin_id, expires_at, created_at) VALUES (?,?,?)",
                             (admin_id, exp, now_iso()))
            await db.commit()

    async def has_session(self, admin_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT expires_at FROM admin_sessions WHERE admin_id=?", (admin_id,))
            row = await cur.fetchone()
            if not row:
                return False
            try:
                exp = datetime.fromisoformat(row[0])
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                return exp > datetime.now(timezone.utc)
            except Exception:
                return False

    async def drop_session(self, admin_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM admin_sessions WHERE admin_id=?", (admin_id,))
            await db.commit()

    # ---------- broadcasts ----------
    async def create_broadcast(self, admin_id: int, audience: str, text: str, photo: str | None = None) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO broadcasts (admin_id, audience, text, photo_file_id, status, created_at)"
                " VALUES (?,?,?,?, 'draft', ?)", (admin_id, audience, text, photo, now_iso()))
            await db.commit()
            return cur.lastrowid or 0

    async def update_broadcast(self, bid: int, **fields: Any) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(f"UPDATE broadcasts SET {sets} WHERE id=?", (*fields.values(), bid))
            await db.commit()

    async def get_broadcast(self, bid: int) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM broadcasts WHERE id=?", (bid,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def list_broadcasts(self, limit: int = 20) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM broadcasts ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in await cur.fetchall()]

    # ---------- export helpers ----------
    async def export_rows(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT u.*, p.profile_name, p.age, p.gender, p.looking_for, p.city, p.bio,"
                " p.interests, p.photo_file_id, p.phone_number, p.profile_status,"
                " p.created_at AS profile_created, p.updated_at AS profile_updated, p.published_at"
                " FROM users u LEFT JOIN profiles p ON p.telegram_id=u.telegram_id ORDER BY u.telegram_id")
            return [dict(r) for r in await cur.fetchall()]

    async def wipe_user_data(self, telegram_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM likes WHERE from_id=? OR to_id=?", (telegram_id, telegram_id))
            await db.execute("UPDATE matches SET status='closed' WHERE user1_id=? OR user2_id=?", (telegram_id, telegram_id))
            await db.execute("DELETE FROM blocks WHERE blocker_id=? OR blocked_id=?", (telegram_id, telegram_id))
            await db.execute("DELETE FROM profiles WHERE telegram_id=?", (telegram_id,))
            await db.execute("DELETE FROM users WHERE telegram_id=?", (telegram_id,))
            await db.commit()

    async def backup(self, dest: str) -> None:
        import sqlite3
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        src = sqlite3.connect(self.path)
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
