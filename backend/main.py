"""Bookend API (FastAPI). Also serves the built React app from frontend/dist at "/".

Run with `python app.py` from the repo folder (see README).
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agents, auth, catalog, db, safety
from .auth import current_user
from .config import AUDIT_LOG, ROOT, USAGE_LOG, audit, env_file, has_api_key, read_jsonl

DIST = ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    for r in db.rows("SELECT DISTINCT author FROM books"):  # usual English spellings of authors already on shelves
        if not catalog.NON_LATIN.search(r["author"]):
            catalog.KNOWN_NAMES.setdefault(frozenset(catalog._tokens(r["author"])), r["author"])
    yield


app = FastAPI(title="Bookend", lifespan=lifespan)
app.include_router(auth.router)

Me = Depends(current_user)  # the signed-in reader, from their session token (never from the request body)


# ---------------------------------------------------------------------------
# Readers, books, shelf
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    p = env_file()
    where = None if p is None else ("repo folder" if p.parent == ROOT else "folder above the repo")
    return {"ok": True, "has_api_key": has_api_key(), "env_file": where}


@app.get("/api/me/shelf")
def shelf(me: dict = Me):
    return db.shelf(me["id"])


@app.get("/api/search")
async def search(q: str, prefix: bool = False):
    """prefix=true: suggestions while typing (the last word may be unfinished)."""
    return await asyncio.to_thread(catalog.search_books, q, 6 if prefix else 10, False, prefix)


@app.get("/api/books/{work_id}")
def book_page(work_id: str, me: dict = Me):
    user_id = me["id"]
    b = db.book(work_id)
    if not b:
        raise HTTPException(404, "Book not found")
    counts = {str(w): len(db.readers_in_window(work_id, w, exclude_user=user_id)) for w in (7, 30, 90, 365)}
    recent = agents._public(db.readers_in_window(work_id, 30, exclude_user=user_id))[:5]
    room = db.readers_room(work_id)
    mine = db.one("SELECT * FROM finishes WHERE user_id = ? AND work_id = ?", (user_id, work_id))
    member = bool(room and db.one("SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?", (room["id"], user_id)))
    return b | {"reader_counts": counts, "recent_readers": recent, "room_id": room["id"] if room else None,
                "is_member": member, "my_finish": mine}


@app.get("/api/active-books")
def active_books():
    return db.active_books(days=30, limit=8)


class FinishIn(BaseModel):
    book: dict  # a search result (work_id, title, author, cover_url, ...)
    finished_on: date | None = None
    rating: int | None = Field(default=None, ge=1, le=5)


@app.post("/api/finish")
async def finish(body: FinishIn, tasks: BackgroundTasks, me: dict = Me):
    if not body.book.get("work_id"):
        raise HTTPException(400, "Missing work_id")
    full = await asyncio.to_thread(catalog.get_work, body.book["work_id"], body.book)
    db.upsert_book(full)
    when = (body.finished_on or date.today()).isoformat()
    db.execute("""INSERT INTO finishes (user_id, work_id, finished_on, rating) VALUES (?,?,?,?)
                  ON CONFLICT(user_id, work_id) DO UPDATE SET finished_on = excluded.finished_on,
                  rating = excluded.rating""", (me["id"], full["work_id"], when, body.rating))
    tasks.add_task(agents.next_books, me["id"])  # "Your next book" refreshes for the newly logged book
    return db.book(full["work_id"])


@app.get("/api/me/next")
def next_books(tasks: BackgroundTasks, me: dict = Me):
    user_id = me["id"]
    """Picks based on the reader's most recently logged book. Starts the agent if they aren't ready yet."""
    last = db.last_logged(user_id)
    if not last:
        return {"based_on": None, "status": "empty", "picks": []}
    row = db.one("SELECT * FROM next_books WHERE user_id = ? AND based_on = ?", (user_id, last["work_id"]))
    if row:
        return {"based_on": last, "status": "ready", "picks": json.loads(row["picks"]), "message": row["message"]}
    if (user_id, last["work_id"]) not in agents.NEXT_BUSY:
        tasks.add_task(agents.next_books, user_id)
    return {"based_on": last, "status": "pending", "picks": []}


@app.get("/api/covers")
def covers():
    """Every book cover in the app, for the scrolling cover panel."""
    return db.rows("SELECT work_id, title, author, cover_url FROM books WHERE cover_url IS NOT NULL ORDER BY title")


class MatchIn(BaseModel):
    work_id: str
    window_days: int = Field(default=30, ge=1, le=365)


@app.post("/api/match")
async def match(body: MatchIn, me: dict = Me):
    try:
        return await agents.match(me["id"], body.work_id, body.window_days)
    except agents.BudgetExceeded as e:
        raise HTTPException(429, str(e))
    except Exception as e:
        raise HTTPException(502, f"The Matchmaker couldn't finish: {type(e).__name__}")


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------

class JoinIn(BaseModel):
    work_id: str
    host_on: bool | None = None


@app.post("/api/rooms/readers/join")
def join_readers(body: JoinIn, tasks: BackgroundTasks, me: dict = Me):
    uid = me["id"]
    if not db.one("SELECT 1 FROM finishes WHERE user_id = ? AND work_id = ?", (uid, body.work_id)):
        raise HTTPException(403, "Mark the book as finished first: reader rooms are for people who finished it.")
    room = db.readers_room(body.work_id)
    if not room:
        rid = db.execute("INSERT INTO rooms (kind, work_id, host_on, created_at) VALUES ('readers', ?, ?, ?)",
                         (body.work_id, int(bool(body.host_on)), db._now()))
        room = db.one("SELECT * FROM rooms WHERE id = ?", (rid,))
    elif body.host_on is not None and bool(room["host_on"]) != body.host_on:
        db.execute("UPDATE rooms SET host_on = ? WHERE id = ?", (int(body.host_on), room["id"]))
    is_new = not db.one("SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?", (room["id"], uid))
    if is_new:
        db.execute("INSERT INTO room_members VALUES (?,?,?)", (room["id"], uid, db._now()))
        u = db.user(uid)
        db.add_message(room["id"], "system", f"{u['display_name']} joined the room.")
        if agents.host_turn_reason(room["id"], None, joined=True):
            tasks.add_task(agents.host_speak, room["id"], "welcome", uid, u["display_name"])
    return {"room_id": room["id"]}


class HostIn(BaseModel):
    on: bool


@app.post("/api/rooms/{room_id}/host")
def toggle_host(room_id: int, body: HostIn, me: dict = Me):
    room = db.one("SELECT * FROM rooms WHERE id = ?", (room_id,))
    if not room or room["kind"] != "readers":
        raise HTTPException(404, "Reader room not found")
    if not db.one("SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?", (room_id, me["id"])):
        raise HTTPException(403, "Join the room first.")
    db.execute("UPDATE rooms SET host_on = ? WHERE id = ?", (int(body.on), room_id))
    u = me
    db.add_message(room_id, "system", f"{u['display_name']} turned the Discussion Host {'on' if body.on else 'off'}.")
    return {"host_on": body.on}


class OwnRoomIn(BaseModel):
    work_id: str | None = None


@app.post("/api/rooms/companion")
def companion_room(body: OwnRoomIn, me: dict = Me):
    uid = me["id"]
    if not body.work_id or not db.book(body.work_id):
        raise HTTPException(404, "Book not found")
    room = db.one("SELECT * FROM rooms WHERE kind = 'companion' AND owner_id = ? AND work_id = ?",
                  (uid, body.work_id))
    if room:
        return {"room_id": room["id"]}
    rid = db.execute("INSERT INTO rooms (kind, work_id, owner_id, created_at) VALUES ('companion', ?, ?, ?)",
                     (body.work_id, uid, db._now()))
    db.execute("INSERT INTO room_members VALUES (?,?,?)", (rid, uid, db._now()))
    b = db.book(body.work_id)
    db.add_message(rid, "companion", f"Hi! I'm Booksy, your AI reading companion. You just finished {b['title']}. "
                                     "What's still on your mind about it?", meta={"basis": "catalog", "greeting": True})
    return {"room_id": rid}


@app.post("/api/rooms/recs")
def recs_room(body: OwnRoomIn, me: dict = Me):
    uid = me["id"]
    room = db.one("SELECT * FROM rooms WHERE kind = 'recs' AND owner_id = ?", (uid,))
    if room:
        return {"room_id": room["id"]}
    rid = db.execute("INSERT INTO rooms (kind, owner_id, created_at) VALUES ('recs', ?, ?)", (uid, db._now()))
    db.execute("INSERT INTO room_members VALUES (?,?,?)", (rid, uid, db._now()))
    db.add_message(rid, "librarian", "Tell me what you loved (or didn't) lately, and I'll find your next book. "
                                     "Every suggestion comes from a real catalog search.", meta={"greeting": True})
    return {"room_id": rid}


@app.get("/api/me/rooms")
def my_rooms(me: dict = Me):
    user_id = me["id"]
    rs = db.rows("""SELECT r.*, b.title, b.author, b.cover_url,
                      (SELECT COUNT(*) FROM room_members m2 WHERE m2.room_id = r.id) AS members,
                      (SELECT MAX(id) FROM messages x WHERE x.room_id = r.id AND x.status = 'shown') AS last_id,
                      (SELECT text FROM messages x WHERE x.room_id = r.id AND x.status = 'shown'
                         ORDER BY id DESC LIMIT 1) AS last_text
                    FROM rooms r JOIN room_members m ON m.room_id = r.id AND m.user_id = ?
                    LEFT JOIN books b ON b.work_id = r.work_id ORDER BY last_id DESC""", (user_id,))
    return rs


@app.get("/api/rooms/{room_id}")
def get_room(room_id: int, after: int = 0, me: dict = Me):
    user_id = me["id"]
    room = db.one("""SELECT r.*, b.title, b.author, b.cover_url FROM rooms r LEFT JOIN books b USING (work_id)
                     WHERE r.id = ?""", (room_id,))
    if not room:
        raise HTTPException(404, "Room not found")
    if not db.one("SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?", (room_id, user_id)):
        raise HTTPException(403, "Join the room first.")  # rooms are private to their members
    msgs = [m for m in db.room_messages(room_id, after_id=after)
            if m["status"] == "shown" or m["user_id"] == user_id]  # hidden messages: only their sender sees them
    members = db.rows("""SELECT u.id, u.display_name, u.color, f.finished_on FROM room_members m
                         JOIN users u ON u.id = m.user_id LEFT JOIN finishes f ON f.user_id = u.id AND f.work_id = ?
                         WHERE m.room_id = ?""", (room["work_id"], room_id))
    today = date.today()
    for m in members:
        m["days_ago"] = (today - date.fromisoformat(m["finished_on"])).days if m["finished_on"] else None
    recent = len(db.readers_in_window(room["work_id"], 30, exclude_user=user_id)) if room["work_id"] else 0
    return {"room": room, "messages": msgs, "members": members, "recent_readers": recent,
            "host_typing": room_id in agents.HOST_BUSY,
            "muted_until": safety.is_muted(user_id)}


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@app.post("/api/rooms/{room_id}/messages")
async def post_message(room_id: int, body: MessageIn, tasks: BackgroundTasks, me: dict = Me):
    uid = me["id"]
    room = db.one("SELECT * FROM rooms WHERE id = ?", (room_id,))
    if not room:
        raise HTTPException(404, "Room not found")
    if not db.one("SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?", (room_id, uid)):
        raise HTTPException(403, "Join the room first.")
    if until := safety.is_muted(uid):
        raise HTTPException(423, f"You're muted until {until[11:16]} after several hidden messages.")
    text = body.text.strip()
    verdict = await agents.moderate(text, uid, room_id, room["kind"])
    hidden = verdict["verdict"] == "hide"
    mid = db.add_message(room_id, "user", text, user_id=uid, status="hidden" if hidden else "shown",
                         mod_category=verdict["category"] if hidden else None,
                         mod_reason=verdict["reason"] if hidden else None,
                         meta={"mod_layer": verdict["layer"], "self_harm_support": verdict.get("self_harm_support")})
    out = {"message_id": mid, "verdict": verdict}
    if hidden:
        return out
    if room["kind"] in ("companion", "recs") and verdict.get("off_topic"):
        # Not a general chatbot: an off-topic request gets a friendly redirect from code, and no AI run at all.
        b = db.book(room["work_id"]) if room["work_id"] else None
        reply = (f"I'm Booksy, and I only talk about books and reading, so I can't help with that one. "
                 f"But I'd love to hear more about {b['title'] if b else 'your book'}: what stuck with you?"
                 if room["kind"] == "companion" else
                 "I only help with finding your next book, so I can't help with that one. "
                 "What kind of book are you in the mood for?")
        db.add_message(room_id, "companion" if room["kind"] == "companion" else "librarian", reply,
                       meta={"off_topic_redirect": True})
        audit("off_topic_redirect", user_id=uid, room_id=room_id, room_kind=room["kind"], text=text[:160])
        out["off_topic"] = True
        return out
    try:
        if room["kind"] == "readers":
            if reason := agents.host_turn_reason(room_id, text):
                tasks.add_task(agents.host_speak, room_id, reason, uid)
        elif room["kind"] == "companion":
            out["reply"] = await agents.companion_reply(room_id, uid)
        elif room["kind"] == "recs":
            out["reply"] = await agents.recommend(room_id, uid)
    except agents.BudgetExceeded as e:
        db.add_message(room_id, "system", f"{e} The AI will be back tomorrow; reader chat still works.")
    except agents.PromptLeak:
        db.add_message(room_id, "system", "That reply was blocked by a safety check. Try asking another way?")
    except Exception as e:
        db.add_message(room_id, "system", f"The AI couldn't answer that one ({type(e).__name__}). Try again?")
    return out


# ---------------------------------------------------------------------------
# Behind the scenes: agent activity, token usage, moderation log
# ---------------------------------------------------------------------------

@app.get("/api/activity")
def activity(limit: int = 40, agent: str | None = None, me: dict = Me):
    """Agent runs only (each with its tool calls, cleaned text, and flags)."""
    rows = [r for r in read_jsonl(AUDIT_LOG) if r.get("event", "agent_run") == "agent_run" and r.get("output")
            and (not agent or r.get("agent") == agent)]
    return list(reversed(rows[-limit:]))


@app.get("/api/audit-events")
def audit_events(limit: int = 40, me: dict = Me):
    """Every other safety event: moderation decisions, off-topic redirects, blocked output, sign-ins, limits."""
    rows = [r for r in read_jsonl(AUDIT_LOG) if r.get("event") not in (None, "agent_run")]
    return list(reversed(rows[-limit:]))


@app.get("/api/usage")
def usage(me: dict = Me):
    rows = read_jsonl(USAGE_LOG)
    by_agent: dict[str, dict] = defaultdict(lambda: Counter())
    for r in rows:
        c = by_agent[r["agent"]]
        c["runs"] += 1
        for k in ("input_tokens", "cached_input_tokens", "output_tokens", "requests", "tool_calls"):
            c[k] += r.get(k, 0)
        c["cost_usd"] += r.get("cost_usd", 0)
        c["seconds"] += r.get("seconds", 0)
    agents_out = {}
    for name, c in by_agent.items():
        n = c["runs"]
        agents_out[name] = dict(c) | {"avg_input": round(c["input_tokens"] / n), "avg_cached": round(c["cached_input_tokens"] / n),
                                      "avg_output": round(c["output_tokens"] / n),
                                      "avg_cost_usd": c["cost_usd"] / n, "avg_seconds": round(c["seconds"] / n, 2)}
    totals = {k: sum(r.get(k, 0) for r in rows) for k in ("input_tokens", "cached_input_tokens", "output_tokens", "cost_usd")}
    return {"runs": len(rows), "totals": totals, "by_agent": agents_out, "recent": list(reversed(rows[-15:]))}


@app.get("/api/moderation")
def moderation(limit: int = 30, me: dict = Me):
    return db.rows("""SELECT e.*, u.display_name FROM mod_events e LEFT JOIN users u ON u.id = e.user_id
                      ORDER BY e.id DESC LIMIT ?""", (limit,))


@app.post("/api/reset")
def reset(request: Request):
    """Re-create the sample data (logs in output/ are kept: they're the report's evidence). Only from this computer."""
    if not request.client or request.client.host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(403, "Reset only works on the computer running the app.")
    db.init_db(reset=True)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Built frontend
# ---------------------------------------------------------------------------

if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        if path and f.is_file() and DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def no_frontend():
        return {"message": "API is running. The frontend isn't built: run `npm --prefix frontend run build`."}
