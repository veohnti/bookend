"""Build data/seed_books.json from Open Library (run once; the app reads the JSON offline).

Every seeded book is a real Open Library work: title, author, cover, description and
subjects come from the catalog, not from a model.

    python scripts/build_seed_books.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.catalog import get_work, search_books  # noqa: E402

TITLES = [
    ("Project Hail Mary", "Andy Weir"),
    ("Tomorrow, and Tomorrow, and Tomorrow", "Gabrielle Zevin"),
    ("The Midnight Library", "Matt Haig"),
    ("Lessons in Chemistry", "Bonnie Garmus"),
    ("Klara and the Sun", "Kazuo Ishiguro"),
    ("The Remains of the Day", "Kazuo Ishiguro"),
    ("Pride and Prejudice", "Jane Austen"),
    ("Dune", "Frank Herbert"),
    ("Circe", "Madeline Miller"),
    ("The Martian", "Andy Weir"),
    ("Homegoing", "Yaa Gyasi"),
    ("Educated", "Tara Westover"),
]


def main() -> None:
    books = []
    for title, author in TITLES:
        hits = [h for h in search_books(f"{title} {author}", limit=5) if author.split()[-1] in h["author"]]
        if not hits:
            print(f"not found: {title}")
            continue
        book = get_work(hits[0]["work_id"], fallback=hits[0])
        books.append(book)
        print(f"{book['work_id']}  {book['title']} by {book['author']}  ({len(book['description'])} chars)")
    out = ROOT / "data" / "seed_books.json"
    out.write_text(json.dumps(books, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(books)} books to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
