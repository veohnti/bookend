"""Defense layer 1 for third-party text (as in HW6's sanitize.py): clean it before any agent reads it.

Chat messages already pass the code screen and the Moderator. But two other kinds of text reach the agents:
- Open Library catalog data (book descriptions, subjects, titles), which anyone on the internet can edit, and
- the room history the Host and Booksy read (already moderated; cleaned again here as defense in depth).

This removes what a reader wouldn't see or what tries to give an AI orders, and returns what it removed so
the audit trail records it:
- zero-width and text-direction characters, HTML tags and comments, links;
- any line or sentence that names our agents or tools, or tells "the AI" what to do ("ignore your
  instructions", "you must", "new instructions", "system prompt", ...).
"""

from __future__ import annotations

import re

from .safety import INJECTION_PATTERNS

INVISIBLE = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩﻿]")
TAGS = re.compile(r"<!--.*?-->|<[^>]{1,200}>", re.S)
LINKS = re.compile(r"https?://\S+|www\.\S+")
# Text that addresses the app's AI or its tools. A real book description never needs to.
ORDERS = re.compile(
    # a note addressed to an AI ("NOTE TO THE AI:", "instructions for the assistant")
    r"\b(notes?|messages?|instructions?)\s+(to|for)\s+(the\s+|any\s+)?(ai|assistant|model|bot|chatbot|host|booksy|moderator)\b"
    # our own agents told what to do (books about AIs, like Klara and the Sun, aren't affected)
    r"|\b(booksy|discussion host|moderator|matchmaker|recommendation agent)\b.{0,40}\b(must|should|needs? to|has to|from now on)\b"
    # an AI addressed directly: "AI: you must...", "Assistant, from now on..."
    r"|\b(ai|assistant|chatbot|language model|llm)\s*[,:]\s*(you\s+)?(must|should|will|need to|have to|from now on|ignore|always|never)\b"
    # our tool names (a real description never mentions them)
    r"|\b(book_record|read_room|room_readers|search_catalog|my_shelf|sender_history|readers_in_window|related_books)\b"
    r"|\bdo not (tell|reveal|mention)\b.{0,40}\b(reader|user)s?\b",
    re.I,
)
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def clean(text: str, source: str, limit: int = 2500) -> tuple[str, list[dict]]:
    """Return (cleaned text, what was removed). `source` labels the removal in the audit trail."""
    removed: list[dict] = []
    if not text:
        return "", removed
    if INVISIBLE.search(text):
        removed.append({"source": source, "kind": "invisible characters", "text": f"{len(INVISIBLE.findall(text))} chars"})
        text = INVISIBLE.sub("", text)
    for pat, kind in ((TAGS, "markup"), (LINKS, "link")):
        for m in pat.findall(text):
            removed.append({"source": source, "kind": kind, "text": str(m)[:200]})
        text = pat.sub(" ", text)
    kept = []
    for part in SENTENCE.split(text):
        if part and (INJECTION_PATTERNS.search(part) or ORDERS.search(part)):
            removed.append({"source": source, "kind": "instruction to the AI", "text": " ".join(part.split())[:300]})
            continue
        kept.append(part)
    return " ".join(" ".join(kept).split())[:limit], removed
