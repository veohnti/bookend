"""Tokenomics: measure real token use for a typical session, then scale to users and months.

    python scripts/tokenomics.py              # 3 typical sessions + the cost-cutting experiment (~$0.05)
    python scripts/tokenomics.py --sessions 1

Writes output/tokenomics.json and output/tokenomics.md. Uses its own database
(data/test_tokenomics.db) and logs (output/tokenomics_usage_log.jsonl), so app data is untouched.

A typical session = what one reader does after finishing one book:
  1. log a book that has recent readers  -> plain match query (no agent)
  2. join that room with the Host on      -> Host welcome
  3. send 4 messages in the room          -> 4 Moderator checks, then a Host nudge
  4. log a book nobody finished recently  -> Matchmaker
  5. 3 turns with the Book Companion      -> 3 Moderator checks + 3 Companion replies
  6. 2 turns of "what next?"              -> 2 Moderator checks + 2 Recommendation replies
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("BOOKEND_DB", str(ROOT / "data" / "test_tokenomics.db"))
os.environ.setdefault("BOOKEND_LOG_PREFIX", "tokenomics_")
sys.path.insert(0, str(ROOT))

from backend import agents, db, safety  # noqa: E402
from backend.config import PRICES, REASONING_EFFORT, USAGE_LOG, now, read_jsonl  # noqa: E402
from scripts.eval_data import MODERATION_SET  # noqa: E402

OUT_JSON = ROOT / "output" / "tokenomics.json"
OUT_MD = ROOT / "output" / "tokenomics.md"
PART = ROOT / "output" / ".tokenomics_medium.json"

SESSIONS_PER_USER_PER_MONTH = 2  # an active reader finishes about two books a month

ROOM_MESSAGES = ["Just finished it last night and I'm still thinking about the ending.",
                 "I didn't see the twist about why he was on the ship coming at all.",
                 "Rocky is the best character I've read in years honestly",
                 "Did anyone else think the middle section with the lab experiments dragged a little?"]
COMPANION_TURNS = ["I finished it and loved it. The friendship carried the whole book for me.",
                   "Why do you think the author waited so long to reveal the memory loss reason?",
                   "Do you remember what Grace's job was before the mission?"]
RECS_TURNS = ["I loved Project Hail Mary and Circe. What should I read next?",
              "Something shorter, maybe under 300 pages?"]


async def say(room_id: int, uid: int, text: str, kind: str) -> None:
    v = await agents.moderate(text, uid, room_id, kind)
    if v["verdict"] == "hide":
        print(f"    (hidden: {text[:40]})")
        return
    db.add_message(room_id, "user", text, user_id=uid)
    try:
        await _reply(room_id, uid, text, kind)
    except Exception as e:  # same as the app: a failed AI reply is reported, the session goes on
        print(f"    ({kind} reply failed: {type(e).__name__})")


async def _reply(room_id: int, uid: int, text: str, kind: str) -> None:
    if kind == "readers" and (reason := agents.host_turn_reason(room_id, text)):
        await agents.host_speak(room_id, reason, uid)
    elif kind == "companion":
        await agents.companion_reply(room_id, uid)
    elif kind == "recs":
        await agents.recommend(room_id, uid)


async def typical_session(i: int) -> dict:
    uid = 50 + i
    db.execute("INSERT OR IGNORE INTO users (id, username, display_name, color) VALUES (?,?,?,?)",
               (uid, f"session{uid}", f"Session reader {i}", "#777"))
    start = len(read_jsonl(USAGE_LOG))
    hail_mary, remains = "OL21745884W", "OL59048W"
    for w in (hail_mary, remains):
        db.execute("INSERT OR REPLACE INTO finishes (user_id, work_id, finished_on, rating) VALUES (?,?,date('now'),5)",
                   (uid, w))
    # Every session's second book must have no recent readers, so earlier test readers of it are cleared.
    db.execute("DELETE FROM finishes WHERE work_id = ? AND user_id != ?", (remains, uid))
    m1 = await agents.match(uid, hail_mary, 30)                   # 1. plain query
    room = db.readers_room(hail_mary)["id"]                        # 2. join, Host on
    db.execute("INSERT OR IGNORE INTO room_members VALUES (?,?,?)", (room, uid, now()))
    db.execute("UPDATE rooms SET host_on = 1 WHERE id = ?", (room,))
    await agents.host_speak(room, "welcome", uid, f"Session reader {i}")
    for t in ROOM_MESSAGES:                                        # 3. chat
        await say(room, uid, t, "readers")
    m2 = await agents.match(uid, remains, 30)                      # 4. Matchmaker
    comp = db.execute("INSERT INTO rooms (kind, work_id, owner_id, created_at) VALUES ('companion', ?, ?, ?)",
                      (hail_mary, uid, now()))
    for t in COMPANION_TURNS:                                      # 5. Companion
        await say(comp, uid, t, "companion")
    recs = db.execute("INSERT INTO rooms (kind, owner_id, created_at) VALUES ('recs', ?, ?)", (uid, now()))
    for t in RECS_TURNS:                                           # 6. Recommendation
        await say(recs, uid, t, "recs")
    runs = read_jsonl(USAGE_LOG)[start:]
    print(f"  session {i}: {len(runs)} agent runs, ${sum(r['cost_usd'] for r in runs):.5f} "
          f"(first match agent_ran={m1['agent_ran']}, second={m2['agent_ran']})")
    return {"session": i, "runs": runs, "match_agent_ran": [m1["agent_ran"], m2["agent_ran"]]}


async def moderation_eval() -> dict:
    """Accuracy and cost of moderation on the labeled set, at the current reasoning effort."""
    start = len(read_jsonl(USAGE_LOG))
    correct, rows = 0, []
    for i, (text, should_hide, what) in enumerate(MODERATION_SET):
        uid = 300 + i
        db.execute("INSERT OR IGNORE INTO users (id, username, display_name, color) VALUES (?,?,?,?)",
                   (uid, f"mod{uid}", f"Mod tester {i}", "#777"))
        v = await agents.moderate(text, uid, None, "readers")
        ok = (v["verdict"] == "hide") == should_hide
        correct += ok
        rows.append({"what": what, "expected": "hide" if should_hide else "allow", "got": v["verdict"],
                     "layer": v["layer"], "correct": ok})
    runs = [r for r in read_jsonl(USAGE_LOG)[start:] if r["agent"] == "moderator"]
    n = len(runs) or 1
    return {"reasoning_effort": REASONING_EFFORT, "messages": len(MODERATION_SET), "correct": correct,
            "model_calls": len(runs), "decided_by_code": sum(r["layer"] == "code" for r in rows),
            "avg_input": sum(r["input_tokens"] for r in runs) / n,
            "avg_output": sum(r["output_tokens"] for r in runs) / n,
            "avg_reasoning": sum(r["reasoning_tokens"] for r in runs) / n,
            "avg_cost_usd": sum(r["cost_usd"] for r in runs) / n,
            "avg_seconds": sum(r["seconds"] for r in runs) / n, "rows": rows}


def summarize(sessions: list[dict]) -> dict:
    by_agent: dict[str, list] = defaultdict(list)
    for s in sessions:
        for r in s["runs"]:
            by_agent[r["agent"]].append(r)
    agents_out = {}
    for name, rs in by_agent.items():
        n = len(rs)
        agents_out[name] = {
            "runs": n, "runs_per_session": n / len(sessions),
            "avg_input": sum(r["input_tokens"] for r in rs) / n,
            "avg_cached": sum(r["cached_input_tokens"] for r in rs) / n,
            "avg_output": sum(r["output_tokens"] for r in rs) / n,
            "avg_reasoning": sum(r["reasoning_tokens"] for r in rs) / n,
            "avg_requests": sum(r["requests"] for r in rs) / n,
            "avg_cost_usd": sum(r["cost_usd"] for r in rs) / n,
            "avg_seconds": sum(r["seconds"] for r in rs) / n}
    per_session = [sum(r["cost_usd"] for r in s["runs"]) for s in sessions]
    tok = lambda k: sum(r[k] for s in sessions for r in s["runs"]) / len(sessions)  # noqa: E731
    session_cost = sum(per_session) / len(per_session)
    month = session_cost * SESSIONS_PER_USER_PER_MONTH
    return {"sessions": len(sessions), "by_agent": agents_out,
            "session": {"input_tokens": tok("input_tokens"), "cached_input_tokens": tok("cached_input_tokens"),
                        "output_tokens": tok("output_tokens"), "cost_usd": session_cost,
                        "min_cost_usd": min(per_session), "max_cost_usd": max(per_session)},
            "per_user_month": month, "users_100_month": month * 100, "users_10000_month": month * 10_000,
            "users_10000_year": month * 10_000 * 12}


def write_md(r: dict) -> None:
    s, m = r["summary"], r["summary"]["session"]
    L = ["# Tokenomics (measured)", "",
         f"Run {r['time']} with `python scripts/tokenomics.py`: {s['sessions']} typical sessions on gpt-6-luna. "
         f"Prices from `data/prices.json`: ${PRICES['input_per_1m']}/1M input, ${PRICES['cached_input_per_1m']}/1M "
         f"cached input, ${PRICES['output_per_1m']}/1M output. Every number below is the token count the API "
         "returned (`output/tokenomics_usage_log.jsonl`).", "",
         "## Per agent", "",
         "| Agent | Runs / session | Avg input | Avg cached | Avg output (reasoning) | Model requests / run | Avg cost / run | Avg time |",
         "|---|---|---|---|---|---|---|---|"]
    for name in ("moderator", "matchmaker", "host", "companion", "recommender"):
        a = s["by_agent"].get(name)
        if a:
            L.append(f"| {name} | {a['runs_per_session']:.1f} | {a['avg_input']:,.0f} | {a['avg_cached']:,.0f} | "
                     f"{a['avg_output']:,.0f} ({a['avg_reasoning']:,.0f}) | {a['avg_requests']:.1f} | "
                     f"${a['avg_cost_usd']:.6f} | {a['avg_seconds']:.1f}s |")
    L += ["", "## Per session, user, and organization", "",
          f"- **One typical session:** {m['input_tokens']:,.0f} input tokens ({m['cached_input_tokens']:,.0f} cached), "
          f"{m['output_tokens']:,.0f} output tokens = **${m['cost_usd']:.4f}** "
          f"(range ${m['min_cost_usd']:.4f} to ${m['max_cost_usd']:.4f}).",
          f"- **Per active user per month** ({SESSIONS_PER_USER_PER_MONTH} sessions): **${s['per_user_month']:.4f}**",
          f"- **100 users:** ${s['users_100_month']:.2f} / month",
          f"- **10,000 users:** ${s['users_10000_month']:.2f} / month (${s['users_10000_year']:,.0f} / year)", ""]
    c = r["cost_cutting"]
    lo, md = c["moderation_low"], c.get("moderation_medium")
    L += ["## Cost-cutting steps and what they cost in quality", "",
          f"1. **Free code screen before the Moderator.** {lo['decided_by_code']} of {lo['messages']} test messages "
          "(contact details, links, injection phrases) were decided in code with no model call.",
          f"2. **Matchmaker only when the plain query fails.** In each session the first match "
          f"(a book with recent readers) ran no agent; only the no-readers case did: "
          f"{c['match_agent_runs']} Matchmaker runs for {c['match_calls']} matches.",
          "3. **Code decides when the Host speaks** (join, @host, or every 4 reader messages), not after every message.",
          f"4. **Prompt caching:** each agent's instructions are a fixed prefix with its own cache key; "
          f"{m['cached_input_tokens'] / max(m['input_tokens'], 1):.0%} of session input tokens were billed at the cached rate.",
          "5. **Low reasoning effort** for every agent. Tested against medium on the labeled moderation set:", "",
          "| Reasoning effort | Correct | Model calls | Avg output tokens (reasoning) | Avg cost / call | Avg time |",
          "|---|---|---|---|---|---|"]
    for x in (lo, md):
        if x:
            L.append(f"| {x['reasoning_effort']} | {x['correct']}/{x['messages']} | {x['model_calls']} | "
                     f"{x['avg_output']:,.0f} ({x['avg_reasoning']:,.0f}) | ${x['avg_cost_usd']:.6f} | {x['avg_seconds']:.1f}s |")
    if md:
        L += ["", f"Medium costs {md['avg_cost_usd'] / max(lo['avg_cost_usd'], 1e-12):.1f}x as much per moderation call "
                  f"and takes {md['avg_seconds'] / max(lo['avg_seconds'], 1e-9):.1f}x as long. "
                  + ("Accuracy was the same, so low effort lost nothing on this set."
                     if md["correct"] == lo["correct"] else
                     f"Accuracy: low {lo['correct']}/{lo['messages']} vs medium {md['correct']}/{md['messages']}.")]
        diffs = [(a["what"], a["got"], b["got"]) for a, b in zip(lo["rows"], md["rows"]) if a["got"] != b["got"]]
        if diffs:
            L += ["", "Messages where the two settings disagreed: " +
                  "; ".join(f"{w} (low: {a}, medium: {b})" for w, a, b in diffs) + "."]
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")


async def main(n_sessions: int, moderation_only: bool) -> None:
    db.init_db(reset=True)
    safety.MAX_PER_MINUTE = 1000  # scripted sessions type faster than a person; don't trip the flood limit
    if moderation_only:
        PART.write_text(json.dumps(await moderation_eval()), encoding="utf-8")
        return
    print(f"Running {n_sessions} typical sessions…")
    sessions = [await typical_session(i) for i in range(n_sessions)]
    print("Moderation set at low reasoning effort…")
    low = await moderation_eval()
    print("Moderation set at medium reasoning effort…")
    env = os.environ | {"BOOKEND_REASONING": "medium", "BOOKEND_DB": str(ROOT / "data" / "test_tokenomics_medium.db")}
    subprocess.run([sys.executable, __file__, "--moderation-only"], env=env, check=True)
    medium = json.loads(PART.read_text())
    PART.unlink()
    flags = [f for s in sessions for f in s["match_agent_ran"]]
    r = {"time": now(), "summary": summarize(sessions),
         "cost_cutting": {"moderation_low": low, "moderation_medium": medium,
                          "match_calls": len(flags), "match_agent_runs": sum(flags)},
         "assumptions": {"sessions_per_user_per_month": SESSIONS_PER_USER_PER_MONTH}}
    OUT_JSON.write_text(json.dumps(r, indent=2, default=str) + "\n", encoding="utf-8")
    write_md(r)
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=3)
    ap.add_argument("--moderation-only", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    asyncio.run(main(a.sessions, a.moderation_only))
