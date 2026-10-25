"""Start Bookend: python app.py  (then open http://localhost:8000)

Looks for .env in this folder first, then the folder above it. Creates and seeds
data/bookend.db on first start. Options: --port 8000, --reset (fresh sample data), --no-browser.
"""

from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn

from backend import db
from backend.config import env_file, has_api_key

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bookend book club app")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reset", action="store_true", help="Start over with fresh sample data")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    db.init_db(reset=args.reset)
    if has_api_key():
        print(f"Found PORTKEY_API_KEY in {env_file()}")
    else:
        print("WARNING: PORTKEY_API_KEY not found in .env (this folder or the one above). "
              "Reader chat works; the AI agents won't.")
    url = f"http://localhost:{args.port}"
    print(f"Bookend is running at {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("backend.main:app", host="127.0.0.1", port=args.port, log_level="warning")
