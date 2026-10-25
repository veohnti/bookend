"""Paths, the .env lookup, the model (gpt-6-luna via Portkey), and token/cost logging.

.env lookup order (course rule): this repo's folder first, then the folder above it.
Only PORTKEY_API_KEY is used. The key is never printed or logged.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
PROMPTS = Path(__file__).resolve().parent / "prompts"
DB_PATH = Path(os.getenv("BOOKEND_DB", DATA / "bookend.db"))
# Test scripts set BOOKEND_LOG_PREFIX (e.g. "safety_") so their runs don't mix with the app's own logs.
_PREFIX = os.getenv("BOOKEND_LOG_PREFIX", "")
USAGE_LOG = OUTPUT / f"{_PREFIX}usage_log.jsonl"
AUDIT_LOG = OUTPUT / f"{_PREFIX}audit_trail.jsonl"

MODEL_NAME = "gpt-6-luna"  # course key: gpt-6-luna only
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
PRICES = json.loads((DATA / "prices.json").read_text())[MODEL_NAME]

# Overspending guard: a per-user daily token budget across every agent (checked in code before each run).
DAILY_TOKEN_BUDGET_PER_USER = 60_000


def env_file() -> Path | None:
    """The .env this app uses: repo folder first, then one folder up."""
    for p in (ROOT / ".env", ROOT.parent / ".env"):
        if p.is_file():
            return p
    return None


def load_env() -> None:
    p = env_file()
    if p:
        load_dotenv(p)


def has_api_key() -> bool:
    load_env()
    return bool(os.getenv("PORTKEY_API_KEY"))


@lru_cache(maxsize=1)
def get_model() -> OpenAIResponsesModel:
    load_env()
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY not found. Put a .env in this folder or the folder above it "
                           "(copy .env.example).")
    # Portkey's response cache can replay an old answer for an identical request; force a real model call.
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=api_key,
                         default_headers={"x-portkey-cache-force-refresh": "true"})
    # Responses API: gpt-6-luna tool calls are rejected on /chat/completions (found in HW6).
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


# Cost cut: low reasoning effort for every agent. scripts/tokenomics.py measures what "medium" would cost and gain.
REASONING_EFFORT = os.getenv("BOOKEND_REASONING", "low")


def settings_for(agent: str, max_tokens: int = 1200) -> OpenAIResponsesModelSettings:
    """Each agent's instructions are a fixed prefix, so a per-agent cache key lets repeat calls reuse it."""
    return OpenAIResponsesModelSettings(
        max_tokens=max_tokens,
        openai_reasoning_effort=REASONING_EFFORT,
        openai_prompt_cache_key=f"bookend-{agent}",
    )


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Logs: JSON Lines, append-only (one object per line, never rewritten)
# ---------------------------------------------------------------------------

_lock = threading.Lock()


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")


def audit(event: str, **data) -> None:
    """One line in output/audit_trail.jsonl for every safety-relevant event (agent runs log their own fuller record).

    Events: moderation, off_topic_redirect, output_blocked, prompt_leak_blocked, catalog_text_cleaned,
    budget_blocked, signup, login, login_failed, demo_login, logout, rate_limited. Never logs passwords or tokens.
    """
    append_jsonl(AUDIT_LOG, {"time": now(), "event": event, **data})


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def cost_usd(input_tokens: int, cached: int, output_tokens: int) -> float:
    return ((input_tokens - cached) * PRICES["input_per_1m"] + cached * PRICES["cached_input_per_1m"]
            + output_tokens * PRICES["output_per_1m"]) / 1e6


def usage_record(agent: str, user_id: int | None, run_id: str, usage, **extra) -> dict:
    """What the API reported for one agent run, plus its dollar cost."""
    cached = usage.cache_read_tokens
    return {"time": now(), "run_id": run_id, "agent": agent, "user_id": user_id, "model": MODEL_NAME,
            "requests": usage.requests, "tool_calls": usage.tool_calls,
            "input_tokens": usage.input_tokens, "cached_input_tokens": cached,
            "output_tokens": usage.output_tokens,
            "reasoning_tokens": (usage.details or {}).get("reasoning_tokens", 0),
            "cost_usd": round(cost_usd(usage.input_tokens, cached, usage.output_tokens), 8), **extra}
