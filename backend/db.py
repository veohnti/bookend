"""SQLite storage: readers, books, finished-book records, chat rooms, messages, moderation events.

The database is a single file (data/bookend.db) created and seeded on first start, so the app
needs no database server and no extra keys. Delete the file (or POST /api/reset) to start over.

Sample data: eight demo readers with finish dates *relative to today*, so the time-window matching
works whenever the app is run. Books are real Open Library works from data/seed_books.json.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from .config import DATA, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
    color TEXT NOT NULL, bio TEXT DEFAULT '', muted_until TEXT,
    password_hash TEXT,  -- NULL for demo readers (one-click sign-in); set for real accounts
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS books (
    work_id TEXT PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL, cover_url TEXT,
    first_publish_year INTEGER, description TEXT DEFAULT '', subjects TEXT DEFAULT '[]',
    source TEXT DEFAULT 'openlibrary'
);
CREATE TABLE IF NOT EXISTS finishes (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
    work_id TEXT NOT NULL REFERENCES books(work_id), finished_on TEXT NOT NULL, rating INTEGER,
    UNIQUE(user_id, work_id)
);
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('readers', 'companion', 'recs')),
    work_id TEXT REFERENCES books(work_id), owner_id INTEGER REFERENCES users(id),
    host_on INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS room_members (
    room_id INTEGER NOT NULL REFERENCES rooms(id), user_id INTEGER NOT NULL REFERENCES users(id),
    joined_at TEXT NOT NULL, PRIMARY KEY (room_id, user_id)
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY, room_id INTEGER NOT NULL REFERENCES rooms(id),
    sender TEXT NOT NULL CHECK (sender IN ('user', 'host', 'companion', 'librarian', 'system')),
    user_id INTEGER REFERENCES users(id), text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'shown' CHECK (status IN ('shown', 'hidden')),
    mod_category TEXT, mod_reason TEXT, meta TEXT DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mod_events (
    id INTEGER PRIMARY KEY, user_id INTEGER, room_id INTEGER, text TEXT NOT NULL,
    verdict TEXT NOT NULL, category TEXT NOT NULL, reason TEXT NOT NULL, layer TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS next_books (
    user_id INTEGER NOT NULL REFERENCES users(id), based_on TEXT NOT NULL, picks TEXT NOT NULL,
    message TEXT DEFAULT '', created_at TEXT NOT NULL, PRIMARY KEY (user_id, based_on)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_finishes_work ON finishes(work_id, finished_on);
CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room_id, id);
"""

DEMO_USERS = [
    # id, username, display name, color, bio
    (1, "alex", "Alex", "#051230", "Grad student. Reads on the train."),
    (2, "jordan", "Jordan", "#bb7125", "Sci-fi first, questions later."),
    (3, "priya", "Priya", "#d9634a", "Book club dropout looking for a better one."),
    (4, "sam", "Sam", "#3f7484", "Audiobooks at 1.5x."),
    (5, "kenji", "Kenji", "#857a22", "Ishiguro completist."),
    (6, "amara", "Amara", "#9c4a6e", "Literary fiction and long walks."),
    (7, "leo", "Leo", "#4d6b2e", "Classics, slowly."),
    (8, "rosa", "Rosa", "#8a4b2d", "Reads the last page first. Sorry."),
]

# (user_id, work_id, days ago, rating)
DEMO_FINISHES = [
    (2, "OL21745884W", 2, 5), (3, "OL21745884W", 5, 4), (4, "OL21745884W", 12, 5), (5, "OL21745884W", 40, 4),
    (6, "OL26004554W", 3, 5), (7, "OL26004554W", 20, 4),
    (8, "OL20965973W", 9, 3),
    (3, "OL25344431W", 15, 4), (8, "OL25344431W", 60, 4),
    (5, "OL20883297W", 4, 5),
    (4, "OL893414W", 1, 5), (7, "OL893414W", 8, 4), (2, "OL893414W", 25, 5),
    (6, "OL18012166W", 6, 5), (8, "OL18012166W", 2, 4),
    (7, "OL66554W", 100, 5),
    (2, "OL17091839W", 70, 4),
    (6, "OL17795349W", 30, 5),
    (3, "OL18139176W", 45, 4),
    # Alex's own shelf (gives the Recommendation agent some history)
    (1, "OL66554W", 200, 5), (1, "OL18012166W", 50, 4),
]

# A readers room that's already going, so the app isn't empty on first open.
DEMO_ROOM_WORK = "OL21745884W"  # Project Hail Mary
DEMO_ROOM_MESSAGES = [
    ("host", None, "Welcome, Jordan and Priya! You both finished *Project Hail Mary* this week. To start: "
                   "at what point did you realize Ryland's memory loss was hiding something about why he "
                   "was on the ship?"),
    ("user", 2, "Honestly the reveal that he didn't volunteer wrecked me. I spent the whole book thinking he was a hero."),
    ("user", 3, "Same! But I think it makes the ending land harder. He chooses it the second time."),
    ("user", 2, "Also I need everyone to know I would die for Rocky."),
]


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def tx():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def rows(sql: str, params: tuple = ()) -> list[dict]:
    with tx() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def one(sql: str, params: tuple = ()) -> dict | None:
    r = rows(sql, params)
    return r[0] if r else None


def execute(sql: str, params: tuple = ()) -> int:
    with tx() as c:
        return c.execute(sql, params).lastrowid


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def init_db(reset: bool = False) -> None:
    if reset and DB_PATH.exists():
        for suffix in ("", "-wal", "-shm"):
            p = DB_PATH.with_name(DB_PATH.name + suffix)
            if p.exists():
                p.unlink()
    with tx() as c:
        # Upgrade databases created before accounts existed (adds the columns; keeps all data).
        if c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone():
            cols = {r[1] for r in c.execute("PRAGMA table_info(users)")}
            for col in ("password_hash", "created_at"):
                if col not in cols:
                    c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
        c.executescript(SCHEMA)
        # The daily AI budget counts only usage since this database was created, so --reset starts it fresh.
        c.execute("INSERT OR IGNORE INTO meta VALUES ('created_at', ?)", (_now(),))
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        c.executemany("INSERT INTO users (id, username, display_name, color, bio) VALUES (?,?,?,?,?)", DEMO_USERS)
        for b in json.loads((DATA / "seed_books.json").read_text(encoding="utf-8")):
            _upsert_book(c, b)
        today = date.today()
        c.executemany("INSERT INTO finishes (user_id, work_id, finished_on, rating) VALUES (?,?,?,?)",
                      [(u, w, (today - timedelta(days=d)).isoformat(), r) for u, w, d, r in DEMO_FINISHES])
        room = c.execute("INSERT INTO rooms (kind, work_id, host_on, created_at) VALUES ('readers', ?, 1, ?)",
                         (DEMO_ROOM_WORK, _now())).lastrowid
        for uid in (2, 3):
            c.execute("INSERT INTO room_members VALUES (?,?,?)", (room, uid, _now()))
        start = datetime.now().astimezone() - timedelta(hours=5)
        for i, (sender, uid, text) in enumerate(DEMO_ROOM_MESSAGES):
            c.execute("INSERT INTO messages (room_id, sender, user_id, text, meta, created_at) VALUES (?,?,?,?,?,?)",
                      (room, sender, uid, text, json.dumps({"sample": True}),
                       (start + timedelta(minutes=7 * i)).isoformat(timespec="seconds")))


def _upsert_book(c: sqlite3.Connection, b: dict) -> None:
    c.execute(
        """INSERT INTO books (work_id, title, author, cover_url, first_publish_year, description, subjects, source)
           VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(work_id) DO UPDATE SET
             description = CASE WHEN excluded.description != '' THEN excluded.description ELSE books.description END,
             cover_url = COALESCE(excluded.cover_url, books.cover_url)""",
        (b["work_id"], b["title"], b["author"], b.get("cover_url"), b.get("first_publish_year"),
         b.get("description", ""), json.dumps(b.get("subjects", [])), b.get("source", "openlibrary")))


def upsert_book(b: dict) -> None:
    with tx() as c:
        _upsert_book(c, b)


# ---------------------------------------------------------------------------
# Queries used by the API and the agents' tools
# ---------------------------------------------------------------------------

def book(work_id: str) -> dict | None:
    b = one("SELECT * FROM books WHERE work_id = ?", (work_id,))
    if b:
        b["subjects"] = json.loads(b["subjects"] or "[]")
    return b


def user(user_id: int) -> dict | None:
    return one("SELECT * FROM users WHERE id = ?", (user_id,))


def created_at() -> str:
    row = one("SELECT value FROM meta WHERE key = 'created_at'")
    return row["value"] if row else ""


def last_logged(user_id: int) -> dict | None:
    """The book this reader logged most recently (latest finish date, then latest entry)."""
    return one("""SELECT f.work_id, f.rating, f.finished_on, b.title, b.author, b.cover_url FROM finishes f
                  JOIN books b USING (work_id) WHERE f.user_id = ? ORDER BY f.finished_on DESC, f.id DESC LIMIT 1""",
               (user_id,))


def shelf(user_id: int) -> list[dict]:
    return rows("""SELECT f.work_id, f.finished_on, f.rating, b.title, b.author, b.cover_url
                   FROM finishes f JOIN books b USING (work_id)
                   WHERE f.user_id = ? ORDER BY f.finished_on DESC""", (user_id,))


def readers_in_window(work_id: str, window_days: int, exclude_user: int | None = None) -> list[dict]:
    """The core match: other readers who finished the same work within the last N days."""
    since = (date.today() - timedelta(days=window_days)).isoformat()
    return rows("""SELECT u.id AS user_id, u.display_name, u.color, f.finished_on, f.rating
                   FROM finishes f JOIN users u ON u.id = f.user_id
                   WHERE f.work_id = ? AND f.finished_on >= ? AND u.id != COALESCE(?, -1)
                   ORDER BY f.finished_on DESC""", (work_id, since, exclude_user))


def readers_room(work_id: str) -> dict | None:
    return one("SELECT * FROM rooms WHERE kind = 'readers' AND work_id = ?", (work_id,))


def room_messages(room_id: int, after_id: int = 0, limit: int = 200) -> list[dict]:
    msgs = rows("""SELECT m.*, u.display_name, u.color FROM messages m LEFT JOIN users u ON u.id = m.user_id
                   WHERE m.room_id = ? AND m.id > ? ORDER BY m.id DESC LIMIT ?""", (room_id, after_id, limit))
    for m in msgs:
        m["meta"] = json.loads(m["meta"] or "{}")
    return list(reversed(msgs))


def add_message(room_id: int, sender: str, text: str, user_id: int | None = None, status: str = "shown",
                mod_category: str | None = None, mod_reason: str | None = None, meta: dict | None = None) -> int:
    return execute("""INSERT INTO messages (room_id, sender, user_id, text, status, mod_category, mod_reason, meta,
                      created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                   (room_id, sender, user_id, text, status, mod_category, mod_reason, json.dumps(meta or {}),
                    _now()))


def active_books(days: int = 30, limit: int = 10) -> list[dict]:
    """Books with the most recent finishes: where a new reader would find people to talk to."""
    since = (date.today() - timedelta(days=days)).isoformat()
    return rows("""SELECT b.work_id, b.title, b.author, b.cover_url, COUNT(*) AS recent_finishers
                   FROM finishes f JOIN books b USING (work_id) WHERE f.finished_on >= ?
                   GROUP BY b.work_id ORDER BY recent_finishers DESC, MAX(f.finished_on) DESC LIMIT ?""",
                (since, limit))
