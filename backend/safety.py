"""Defense layer 1 (code): free, instant checks that run before any model sees a message.

- Personal info: emails, phone numbers, street addresses, social handles, and links are hidden.
  Strangers chat here, so contact details never go through (readers can stay anonymous).
- Prompt injection: text that tries to give the AI orders is hidden before the Host,
  Companion or Recommendation agent reads it.
- Spam and flooding: very long messages, the same message repeated, or too many messages a minute.
- Mute: three hidden messages in 24 hours mutes the sender for an hour.

Anything that passes goes to the Moderator agent (layer 2) for judgment calls such as harassment.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from . import db

MAX_LEN = 800
MAX_PER_MINUTE = 8
STRIKES_TO_MUTE = 3
MUTE_HOURS = 1

PII_PATTERNS = [
    ("an email address", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("a phone number", re.compile(r"(?<!\d)(?:\+?\d[\s().-]*){10,}(?!\d)")),
    ("a street address", re.compile(
        r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s){1,3}(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Lane|Ln|Dr|Drive|Ct|Court|Way)\b\.?")),
    ("a link", re.compile(r"https?://|www\.|\b[\w-]+\.(?:com|net|org|io|ly|me|gg)\b", re.I)),
    ("a social media handle", re.compile(
        r"(?:\b(?:insta(?:gram)?|ig|snap(?:chat)?|tiktok|twitter|discord|whatsapp|telegram)\b[\s:@-]*\w+)|(?<!\w)@\w{3,}",
        re.I)),
]

INJECTION_PATTERNS = re.compile(
    r"ignore (?:all |any |your |the )?(?:previous |prior |above )?(?:instructions|rules|prompt)"
    r"|disregard (?:your|all|the) (?:instructions|rules)"
    r"|(?:reveal|print|show|repeat) (?:me )?(?:your|the) (?:system )?(?:prompt|instructions)"
    r"|system prompt|developer mode|jailbreak|\bDAN\b"
    r"|you are now (?:a|an|my)|new instructions?:|</?(?:system|instructions|reader_messages)>"
    r"|(?:host|companion|assistant|AI|bot),? (?:you must|you will|from now on)"
    r"|^\s*\[?(?:system|admin|moderator|developer)\]?\s*:",
    re.I,
)

# The Host never answers itself and @host is how readers call it in.
HOST_MENTION = re.compile(r"@host\b", re.I)


def screen(text: str, user_id: int, room_id: int | None) -> dict | None:
    """Return a hide verdict if code alone can decide, else None (go on to the Moderator agent)."""
    t = text.strip()
    if len(t) > MAX_LEN:
        return _hide("spam", f"Messages are limited to {MAX_LEN} characters.")
    if INJECTION_PATTERNS.search(t):
        return _hide("prompt_injection", "This looks like an attempt to give the AI instructions, so it wasn't posted.")
    scan = HOST_MENTION.sub("", t)  # "@host" is how readers call the Host in, not a handle
    for label, pat in PII_PATTERNS:
        if pat.search(scan):
            return _hide("personal_info", f"For everyone's safety, messages can't include {label}.")
    minute_ago = (datetime.now().astimezone() - timedelta(minutes=1)).isoformat(timespec="seconds")
    recent = db.rows("SELECT text FROM messages WHERE user_id = ? AND created_at >= ?", (user_id, minute_ago))
    if len(recent) >= MAX_PER_MINUTE:
        return _hide("spam", "You're sending messages very fast. Take a breath and try again in a minute.")
    if room_id is not None:
        last3 = db.rows("SELECT text FROM messages WHERE user_id = ? AND room_id = ? ORDER BY id DESC LIMIT 2",
                        (user_id, room_id))
        if len(last3) == 2 and all(m["text"].strip().lower() == t.lower() for m in last3):
            return _hide("spam", "That message was already sent twice.")
    return None


def _hide(category: str, reason: str) -> dict:
    return {"verdict": "hide", "category": category, "reason": reason, "layer": "code"}


def is_muted(user_id: int) -> str | None:
    u = db.user(user_id)
    if u and u["muted_until"] and u["muted_until"] > datetime.now().astimezone().isoformat(timespec="seconds"):
        return u["muted_until"]
    return None


def record_and_maybe_mute(user_id: int, room_id: int | None, text: str, verdict: dict) -> str | None:
    """Log every moderation decision. Three hides in 24 hours mutes the sender for an hour."""
    db.execute("""INSERT INTO mod_events (user_id, room_id, text, verdict, category, reason, layer, created_at)
                  VALUES (?,?,?,?,?,?,?,?)""",
               (user_id, room_id, text[:500], verdict["verdict"], verdict["category"], verdict["reason"],
                verdict["layer"], datetime.now().astimezone().isoformat(timespec="seconds")))
    if verdict["verdict"] != "hide":
        return None
    since = (datetime.now().astimezone() - timedelta(hours=24)).isoformat(timespec="seconds")
    strikes = db.one("SELECT COUNT(*) AS n FROM mod_events WHERE user_id = ? AND verdict = 'hide' AND created_at >= ?",
                     (user_id, since))["n"]
    if strikes >= STRIKES_TO_MUTE:
        until = (datetime.now().astimezone() + timedelta(hours=MUTE_HOURS)).isoformat(timespec="seconds")
        db.execute("UPDATE users SET muted_until = ? WHERE id = ?", (until, user_id))
        return until
    return None


def recent_strikes(user_id: int) -> int:
    since = (datetime.now().astimezone() - timedelta(hours=24)).isoformat(timespec="seconds")
    return db.one("SELECT COUNT(*) AS n FROM mod_events WHERE user_id = ? AND verdict = 'hide' AND created_at >= ?",
                  (user_id, since))["n"]


OUTPUT_PII = [p for label, p in PII_PATTERNS if label != "a social media handle"]


def clean_agent_output(text: str) -> str | None:
    """Output check: an agent's message never posts if it contains a link or contact details."""
    for p in OUTPUT_PII:
        if p.search(text):
            return None
    return text
