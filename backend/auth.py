"""Accounts and sessions.

- Passwords are stored as pbkdf2_sha256$<iterations>$<salt>$<hash> and checked in constant time. A stored hash
  can't be turned back into a password.
- Signing in returns a random session token. Only a SHA-256 hash of it is stored (table `sessions`), so someone
  who reads the database gets hashes, not working sessions. Sessions last 14 days.
- Every API route that acts as a reader gets the reader from the token (`current_user`), never from the request
  body, so nobody can post, read hidden messages, or spend AI budget as someone else.
- Accounts sign in with an email address, which is stored for log-in only and never shown to other readers.
- Demo readers (the sample users, who have no password) can be entered with one click for grading and demos.
  Real accounts can only be entered with their password.
- Abuse limits: at most 5 sign-ups per hour from one address, and 10 failed log-ins per 15 minutes per address.
"""

from __future__ import annotations

import hashlib
import hmac
import random
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from . import db, safety
from .config import audit

ITERATIONS = 240_000
SESSION_DAYS = 14
# Accounts sign in with an email address (kept private: other readers only ever see the display name).
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[a-z]{2,}$")
COLORS = ["#051230", "#bb7125", "#d9634a", "#3f7484", "#857a22", "#9c4a6e", "#4d6b2e", "#8a4b2d"]

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Passwords and tokens
# ---------------------------------------------------------------------------

def hash_password(password: str, *, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algorithm, iters, salt_hex, hash_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(candidate, bytes.fromhex(hash_hex))
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now().astimezone()
    db.execute("INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
               (_token_hash(token), user_id, now.isoformat(timespec="seconds"),
                (now + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")))
    return token


def _public_user(u: dict) -> dict:
    """What the signed-in reader sees about themselves. Other readers only ever get display_name and color."""
    return {"id": u["id"], "username": u["username"], "display_name": u["display_name"], "color": u["color"],
            "bio": u.get("bio") or "", "is_demo": not u.get("password_hash")}


# ---------------------------------------------------------------------------
# The signed-in reader (used by every route that acts as a reader)
# ---------------------------------------------------------------------------

def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in first.")
    row = db.one("""SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
                    WHERE s.token_hash = ? AND s.expires_at > ?""",
                 (_token_hash(authorization[7:].strip()), datetime.now().astimezone().isoformat(timespec="seconds")))
    if not row:
        raise HTTPException(401, "Your session has ended. Sign in again.")
    return row


# ---------------------------------------------------------------------------
# Abuse limits (in memory: they reset when the app restarts, which is fine for a single small server)
# ---------------------------------------------------------------------------

_events: dict[str, deque] = defaultdict(deque)


def _limited(key: str, limit: int, window_s: int) -> bool:
    q, now = _events[key], time.monotonic()
    while q and now - q[0] > window_s:
        q.popleft()
    return len(q) >= limit


def _note(key: str) -> None:
    _events[key].append(time.monotonic())


def _mask(email: str) -> str:
    """For the audit trail: enough to recognize an account, not the full address (b***@yale.edu)."""
    name, _, domain = email.partition("@")
    return f"{name[:1]}***@{domain}" if domain else "***"


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

class SignUpIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    display_name: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=8, max_length=200)


class LogInIn(BaseModel):
    email: str
    password: str


@router.post("/signup")
def signup(body: SignUpIn, request: Request):
    ip = _client(request)
    if _limited(f"signup:{ip}", 5, 3600):
        audit("rate_limited", action="signup", ip=ip)
        raise HTTPException(429, "Too many new accounts from here. Try again in an hour.")
    email = body.email.strip().lower()
    if not EMAIL.fullmatch(email):
        raise HTTPException(400, "Enter a valid email address.")
    name = " ".join(body.display_name.split())
    # Display names are shown to strangers: same code screen as chat (no contact details, links, AI instructions).
    if not name or safety.screen(name, user_id=-1, room_id=None):
        raise HTTPException(400, "Pick a display name without contact details or links.")
    if db.one("SELECT 1 FROM users WHERE username = ?", (email,)):
        raise HTTPException(409, "There's already an account with that email. Log in instead.")
    _note(f"signup:{ip}")
    uid = db.execute("""INSERT INTO users (username, display_name, color, bio, password_hash, created_at)
                        VALUES (?,?,?,?,?,?)""",
                     (email, name, random.choice(COLORS), "", hash_password(body.password), db._now()))
    audit("signup", user_id=uid, email=_mask(email), ip=ip)
    return {"token": new_session(uid), "user": _public_user(db.user(uid))}


@router.post("/login")
def login(body: LogInIn, request: Request):
    key = f"login:{_client(request)}"
    if _limited(key, 10, 900):
        audit("rate_limited", action="login", ip=_client(request))
        raise HTTPException(429, "Too many tries. Wait 15 minutes and try again.")
    u = db.one("SELECT * FROM users WHERE username = ?", (body.email.strip().lower(),))
    if not u or not verify_password(body.password, u.get("password_hash")):
        _note(key)
        audit("login_failed", email=_mask(body.email.strip().lower()), ip=_client(request))
        raise HTTPException(401, "That email and password don't match.")
    audit("login", user_id=u["id"], email=_mask(u["username"]), ip=_client(request))
    return {"token": new_session(u["id"]), "user": _public_user(u)}


class DemoIn(BaseModel):
    user_id: int


@router.post("/demo")
def demo(body: DemoIn):
    u = db.user(body.user_id)
    if not u or u.get("password_hash"):  # real accounts are never enterable without their password
        audit("demo_login_refused", user_id=body.user_id)
        raise HTTPException(403, "That isn't a demo reader.")
    audit("demo_login", user_id=u["id"])
    return {"token": new_session(u["id"]), "user": _public_user(u)}


@router.get("/demo-readers")
def demo_readers():
    return [_public_user(u) for u in db.rows("SELECT * FROM users WHERE password_hash IS NULL ORDER BY id")]


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return _public_user(user)


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.lower().startswith("bearer "):
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(authorization[7:].strip()),))
        audit("logout")
    return {"ok": True}
