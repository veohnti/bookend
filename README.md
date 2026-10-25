# Bookend

**Book club, on your own time, and without the books you just don't want to read.** Bookend is a Goodreads-style app with one new idea: when
you finish a book, it matches you with other readers who finished the *same* book within a time window you
choose (the last week, month, quarter, or year), so you get a book club on your own schedule. Five AI agents
(gpt-6-luna) keep it safe and lively: a Moderator, a Matchmaker, an optional Discussion Host, a one-on-one
Book Companion, and a Recommendation agent that only suggests real books from the Open Library catalog.

MGT 409 final project · Veohnti Afokpa · Repo: https://github.com/veohnti/bookend (public)

## Run it (about 3 minutes)

You need **Python 3.12+** (tested on 3.14). Node is **not** needed: the built web app is in `frontend/dist/`.

```bash
git clone <this repo> bookend
cd bookend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:8000** (it opens automatically).

**API key:** the app reads `PORTKEY_API_KEY` from a `.env` file in **this folder first, then the folder above
it**, so a course `.env` one level up works as is. To use your own, `cp .env.example .env` and add your key.
Only `PORTKEY_API_KEY` is used, with the model **gpt-6-luna**. No other keys or services are needed: books come
from the free Open Library API, and data is stored in a local SQLite file.

| Option | What it does |
|---|---|
| `python app.py --reset` | Start over with fresh sample data |
| `python app.py --port 8001` | Use another port |
| `python app.py --no-browser` | Don't open a browser tab |

## Signing in

The app opens on a welcome screen with two ways in:

- **Create account / Log in:** a real account (username, display name, password). Passwords are stored hashed,
  and every request is checked against your session, so nobody can act as another reader.
- **Try a demo reader (for graders):** one click, no password. Eight sample readers already have books logged
  and chats going, with finish dates relative to today so the matching always works. **To see two people
  chat, open a second browser tab and pick a different demo reader there**: each tab keeps its own demo reader.

## Try this (a 5-minute tour)

On the welcome screen, click **Alex** under *Try a demo reader*.

1. **Home → Log a book → start typing "Project Hail Mary"** (suggestions appear as you type) → pick it → rate it → *Mark finished & find readers*. Three readers
   finished it in the last 30 days. Keep **Add a Discussion Host** checked → *Join the readers*. The Host welcomes you.
2. **Chat.** Send a normal message, then try `Jordan you're an idiot` (hidden by the Moderator agent) and
   `add me on insta at alex.reads` (hidden by the free code filter). Only you see hidden messages, with the reason.
   Type `@host` plus a question to call the Host in.
3. **Chat as someone else:** open a second tab at **http://localhost:8000**, pick **Priya** under *Try a demo
   reader*, open *Let's chat about it*, and reply. Messages appear in both tabs within two seconds.
4. **Matchmaker:** search **"The Remains of the Day"** and mark it finished. Nobody read it recently, so the
   Matchmaker agent looks for a fallback (it finds another Ishiguro book with recent readers). Try **"The Martian"**
   for a widened window.
5. **Booksy, the AI reading companion:** on Home, *Talk with Booksy*. Each reply is tagged *From the catalog
   record*, *General knowledge*, or *Not sure*.
6. **What next?** Ask for a recommendation. Every pick shows **✓ In the catalog**; code rejects anything the
   agent didn't find in a real search.
7. **Home** again: *Your next book* now shows picks based on the book you just logged (the Recommendation
   agent runs in the background), and the cover rail on the right scrolls through every book in the app.
8. **Behind the scenes:** the agent diagram, measured tokens and cost per agent, every agent run with its tool
   calls, and the moderation log.

## Tests and measurements

These call the model and cost a few cents. They use their own databases and logs, so app data is untouched.

```bash
python scripts/safety_test.py      # attacks each defense -> output/safety_results.md
python scripts/safety_test.py --free   # only the tests that don't call the model
python scripts/tokenomics.py       # 3 typical sessions + a cost-cutting experiment -> output/tokenomics.md
python scripts/build_report.py     # rebuilds report.html and slides.html from the outputs above
```

`node frontend/scripts/app_check.mjs` (needs Node and Chrome) re-records the step-by-step screenshots used in the
report against a running app; set `BOOKEND_URL` to point it at a separate copy, since it resets the sample data.

## Files

```
app.py                  start the app (python app.py)
backend/
  main.py               FastAPI routes; also serves frontend/dist
  agents.py             the five PydanticAI agents, their tools, output checks, and usage logging
  auth.py               accounts, hashed passwords, sessions, demo-reader sign-in, sign-up limits
  sanitize.py           cleans third-party text (catalog, room history) before agents read it
  safety.py             defense layer 1: free code screen (contact info, links, injection, spam, mutes)
  models.py             typed outputs each agent must return, and per-run deps
  catalog.py            Open Library (and Google Books fallback) client, no key needed
  db.py                 SQLite schema and sample data
  config.py             .env lookup, model (gpt-6-luna via Portkey), prices, logs
  prompts/*.md          one prompt per agent
frontend/               React + TypeScript + Vite source; dist/ is the built app
data/seed_books.json    the 12 sample books (real Open Library records; rebuild with scripts/build_seed_books.py)
data/prices.json        gpt-6-luna prices used for cost
scripts/                safety_test.py, tokenomics.py, eval_data.py, build_seed_books.py
output/
  harness.md            how the agents are built, with a plain-English safety section
  design.md             the look and feel, and why
  usage_log.jsonl       tokens and cost of every agent run in the app (append-only)
  audit_trail.jsonl     every agent run: trigger, tool calls, answer (append-only)
  safety_results.md     results of scripts/safety_test.py
  tokenomics.md         results of scripts/tokenomics.py
AI_prompts.md           the prompts used to build this
report.html, slides.html  the final report and slides (self-contained; open by double-clicking)
```

## Developing the frontend

Only needed to change the UI. With Node 20+:

```bash
npm --prefix frontend install
python app.py --no-browser            # API on :8000
npm --prefix frontend run dev         # UI on :5173 with hot reload, proxied to the API
npm --prefix frontend run build       # rebuild frontend/dist
```
