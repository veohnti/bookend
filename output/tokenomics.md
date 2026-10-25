# Tokenomics (measured)

Run 2026-10-24T13:10:11-04:00 with `python scripts/tokenomics.py`: 3 typical sessions on gpt-6-luna. Prices from `data/prices.json`: $0.1/1M input, $0.01/1M cached input, $0.5/1M output. Every number below is the token count the API returned (`output/tokenomics_usage_log.jsonl`).

## Per agent

| Agent | Runs / session | Avg input | Avg cached | Avg output (reasoning) | Model requests / run | Avg cost / run | Avg time |
|---|---|---|---|---|---|---|---|
| moderator | 9.0 | 1,728 | 1,587 | 34 (0) | 1.0 | $0.000047 | 1.3s |
| matchmaker | 1.0 | 4,697 | 0 | 193 (0) | 5.7 | $0.000566 | 9.6s |
| host | 2.0 | 2,118 | 0 | 116 (0) | 2.0 | $0.000270 | 4.0s |
| companion | 3.0 | 2,617 | 404 | 117 (21) | 2.1 | $0.000284 | 3.8s |
| recommender | 2.0 | 3,404 | 0 | 248 (0) | 2.5 | $0.000465 | 16.5s |

## Per session, user, and organization

- **One typical session:** 39,144 input tokens (15,495 cached), 1,577 output tokens = **$0.0033** (range $0.0033 to $0.0034).
- **Per active user per month** (2 sessions): **$0.0066**
- **100 users:** $0.66 / month
- **10,000 users:** $66.17 / month ($794 / year)

## Cost-cutting steps and what they cost in quality

1. **Free code screen before the Moderator.** 6 of 22 test messages (contact details, links, injection phrases) were decided in code with no model call.
2. **Matchmaker only when the plain query fails.** In each session the first match (a book with recent readers) ran no agent; only the no-readers case did: 3 Matchmaker runs for 6 matches.
3. **Code decides when the Host speaks** (join, @host, or every 4 reader messages), not after every message.
4. **Prompt caching:** each agent's instructions are a fixed prefix with its own cache key; 40% of session input tokens were billed at the cached rate.
5. **Low reasoning effort** for every agent. Tested against medium on the labeled moderation set:

| Reasoning effort | Correct | Model calls | Avg output tokens (reasoning) | Avg cost / call | Avg time |
|---|---|---|---|---|---|
| low | 22/22 | 16 | 37 (0) | $0.000047 | 1.4s |
| medium | 22/22 | 16 | 41 (3) | $0.000061 | 2.4s |

Medium costs 1.3x as much per moderation call and takes 1.6x as long. Accuracy was the same, so low effort lost nothing on this set.
