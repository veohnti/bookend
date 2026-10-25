# Cost-cut history (measured during development, 2026-10-23)

Both rows come from `scripts/tokenomics.py` runs on gpt-6-luna; the only change between them was the Moderator
prompt (`backend/prompts/moderator.md`).

| Moderator prompt | Avg input tokens / call | Avg cached | Avg cost / call | Moderation accuracy |
|---|---|---|---|---|
| Before: rules only (~510 words, under the 1,024-token caching minimum) | 918 | 0 | $0.000107 | 21/21 |
| After: rules + room types + 15 worked examples (~760 words) | 1,351 | 1,161 | $0.000046 | 22/22 |

A longer prompt made each moderation call **57% cheaper**: once the fixed part of the prompt passed 1,024
tokens, the provider cached it and billed it at a tenth of the price. Accuracy did not drop (one test message
was added between runs).

## Safety hardening (2026-10-24)

Adding the book-only rules, the `suspicious_content` field, the tripwire marker, and cleaned catalog text made every
agent's instructions longer. Measured with `scripts/tokenomics.py` before and after:

| | Typical session | Moderator per call | Off-topic request |
|---|---|---|---|
| Before | $0.0029 | $0.000042 | full Booksy run (about $0.00026) |
| After | $0.0033 | $0.000047 | $0 (redirect from code, no AI run) |

About 14% more per session, for defenses that all held in `scripts/safety_test.py`.
