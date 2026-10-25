"""Book catalog: Open Library first, Google Books as a fallback. Neither needs an API key.

Books are keyed on the Open Library *work* ID (e.g. OL21745884W), which covers every edition
(hardcover, paperback, ebook, audiobook, translations), so readers of any edition land in the
same chat. A Google Books result, used only when Open Library has nothing, is keyed "GB:<id>".
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

import httpx

OL = "https://openlibrary.org"
COVERS = "https://covers.openlibrary.org/b/id/{}-{}.jpg"
GOOGLE = "https://www.googleapis.com/books/v1/volumes"
HEADERS = {"User-Agent": "Bookend-MGT409-class-project/1.0"}
TIMEOUT = httpx.Timeout(12.0)
SEARCH_FIELDS = ("key,title,author_name,author_alternative_name,cover_i,first_publish_year,subject,edition_count,"
                 "editions,editions.title,editions.language,editions.cover_i")
# Titles must be readable in English: Latin letters, digits, punctuation (accents allowed).
NON_LATIN = re.compile(r"[^\u0000-\u024F\u1E00-\u1EFF\u2000-\u206F\u20A0-\u20CF\u2100-\u214F]")


def cover_url(cover_id: int | None, size: str = "M") -> str | None:
    return COVERS.format(cover_id, size) if cover_id else None


def _clean_description(desc) -> str:
    if isinstance(desc, dict):
        desc = desc.get("value", "")
    desc = (desc or "").replace("\r", "")
    desc = re.split(r"\n-{3,}|\n\*\*\*|\(\[source\]", desc)[0]  # drop "----" footers and source links
    desc = re.sub(r"\[([^\]]+)\]\[\d+\]", r"\1", desc)           # [text][1] -> text
    desc = re.sub(r"\[\d+\]:\s*\S+", "", desc)
    return " ".join(desc.split())[:2500]


def _english(d: dict) -> tuple[str, int | None] | None:
    """The title (and cover) of the work's English edition, or None if there's no readable English title.

    With lang=en, Open Library returns the work's best-matching English edition, so a book catalogued under its
    original title (e.g. 海辺のカフカ) comes back as its English edition (Kafka on the Shore).
    """
    ed = (d.get("editions") or {}).get("docs") or [{}]
    ed = ed[0]
    langs = ed.get("language") or []
    if "eng" in langs and ed.get("title"):
        title, cover = ed["title"], ed.get("cover_i") or d.get("cover_i")
    elif langs:  # the closest edition is in another language: not an English book
        return None
    else:
        title, cover = d.get("title", ""), d.get("cover_i")
    return (title, cover) if title and not NON_LATIN.search(title) else None


KNOWN_NAMES: dict[frozenset, str] = {}  # author spellings seen as a book's main (Latin) author name


def _author(d: dict) -> str:
    """First author name in Latin script. If there isn't one (村上春樹), use the most common Latin spelling among the
    alternative names, preferring given-name-first order (Haruki Murakami over Murakami Haruki)."""
    for name in d.get("author_name", []):
        if not NON_LATIN.search(name):
            KNOWN_NAMES.setdefault(frozenset(_tokens(name)), name)
            return name
    alts = [a for a in d.get("author_alternative_name", []) if not NON_LATIN.search(a) and len(a.split()) >= 2]
    for a in alts:  # a spelling another book already used as its main author name wins (Haruki Murakami)
        if (known := KNOWN_NAMES.get(frozenset(_tokens(a)))):
            return known
    if not alts:
        return (d.get("author_name") or ["Unknown author"])[0]
    groups: dict[frozenset, list[str]] = {}
    for a in alts:
        groups.setdefault(frozenset(_tokens(a)), []).append(a)
    best = max(groups.values(), key=len)
    titled = [a for a in best if not a.isupper()] or best
    # given-first: a spelling whose first word appears last in another spelling of the same name
    for a in titled:
        first = a.split()[0].lower()
        if any(b.split()[-1].lower() == first for b in best if b != a):
            continue
        return a
    return titled[0]


def _from_search_doc(d: dict) -> dict:
    title, cover = _english(d) or (d.get("title", "Untitled"), d.get("cover_i"))
    return {
        "work_id": d["key"].rsplit("/", 1)[-1],
        "title": title,
        "author": _author(d),
        "cover_url": cover_url(cover),
        "first_publish_year": d.get("first_publish_year"),
        "subjects": [s for s in d.get("subject", []) if ":" not in s][:8],
        "source": "openlibrary",
    }


def _google_search(query: str, limit: int) -> list[dict]:
    r = httpx.get(GOOGLE, params={"q": query, "maxResults": min(limit, 20), "printType": "books"},
                  headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for item in r.json().get("items", []):
        v = item.get("volumeInfo", {})
        img = (v.get("imageLinks") or {}).get("thumbnail")
        out.append({
            "work_id": f"GB:{item['id']}",
            "title": v.get("title", "Untitled"),
            "author": ", ".join(v.get("authors", [])[:2]) or "Unknown author",
            "cover_url": img.replace("http://", "https://") if img else None,
            "first_publish_year": int(v["publishedDate"][:4]) if v.get("publishedDate", "")[:4].isdigit() else None,
            "subjects": v.get("categories", [])[:8],
            "description": _clean_description(v.get("description", "")),
            "source": "googlebooks",
        })
    return out


# Words that make an Open Library query fail (it requires every word to match) without narrowing it usefully.
FILLER = {"a", "an", "the", "and", "or", "of", "with", "about", "for", "in", "on", "to", "book", "books", "novel",
          "novels", "story", "stories", "fiction", "read", "reads", "like", "similar", "something", "big",
          "heartwarming", "heart", "good", "great", "best", "new", "recent", "modern", "unusual", "literary"}


# Companion products that aren't the book itself (study guides, summaries, workbooks).
NOT_A_BOOK = re.compile(r"study guide|workbook|summary (of|and)|^summary\b|analysis of|trivia|sparknotes|cliffsnotes|"
                        r"book companion|reading guide", re.I)


def _ol_search(query: str, limit: int, popular: bool, field: str = "q") -> list[dict]:
    params = {field: query, "limit": limit + 8, "fields": SEARCH_FIELDS, "lang": "en"}
    if popular:
        params["sort"] = "readinglog"  # most-shelved first: well-known books before obscure editions
    r = httpx.get(f"{OL}/search.json", params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return [d for d in r.json().get("docs", [])
            if d.get("key", "").startswith("/works/") and not NOT_A_BOOK.search(d.get("title", "")) and _english(d)][:limit]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _matches(d: dict, words: list[str], title_only: bool = False) -> bool:
    """Every query word starts some word of the book's English title (or one of its author names)."""
    title = (_english(d) or ("",))[0]
    have = _tokens(title if title_only else " ".join([title, *d.get("author_name", []), *d.get("author_alternative_name", [])]))
    return all(any(t.startswith(w) for t in have) for w in words)


def search_books(query: str, limit: int = 8, popular: bool = False, prefix: bool = False) -> list[dict]:  # noqa: ARG001
    """Search the catalog for English books. Returns [] (never raises) if both catalogs are unreachable.

    Two Open Library searches run in parallel: by relevance, and by popularity (most-shelved first). Popular
    results come first, but only if the query's words are in their title or author ("haruki murakami" -> his
    novels, not books about him); relevance results fill in after. prefix=True treats the last word as
    unfinished, for suggestions while typing. If a long descriptive query finds nothing (Open Library matches
    every word), retry with its first two meaningful words.
    """
    query = " ".join(query.split())[:120]
    if not query:
        return []
    words = [w for w in _tokens(query) if w not in FILLER] or _tokens(query)
    try:
        with ThreadPoolExecutor(3) as pool:
            if prefix:
                # While typing: title and author searches with the unfinished last word as a wildcard, plus a plain
                # search on the finished words (finds books catalogued under another language's title).
                q = query + "*" if query[-1].isalnum() else query
                done = " ".join(query.split()[:-1]) if len(query.split()) > 1 else ""
                futures = [pool.submit(_ol_search, q, limit, True, "title"), pool.submit(_ol_search, q, limit, True, "author")]
                if done:
                    futures.append(pool.submit(_ol_search, done, limit, False))
                found = [d for f in futures for d in f.result()]
                hits = [x for x in found if _matches(x, words)]
                # books whose own title matches first, then matches on the author
                first, rest = [x for x in hits if _matches(x, words, title_only=True)] + hits, []
            else:
                rel_f = pool.submit(_ol_search, query, limit, False)
                pop_f = pool.submit(_ol_search, query, limit, True)
                rel, pop = rel_f.result(), pop_f.result()
                first, rest = [x for x in pop if _matches(x, words)], rel
        seen, docs = set(), []
        for d in first + rest:
            if d["key"] not in seen and (not prefix or _matches(d, words)):
                seen.add(d["key"])
                docs.append(d)
        if not docs and len(query.split()) > 2 and len(words) >= 2 and not prefix:
            docs = _ol_search(" ".join(words[:2]), limit, popular=True)
        if docs:
            for d in docs:  # learn main spellings first, so every result can use them
                _author(d)
            return [_from_search_doc(d) for d in docs[:limit]]
    except httpx.HTTPError:
        pass
    if prefix:
        return []
    try:
        return _google_search(query, limit)
    except httpx.HTTPError:
        return []


def get_work(work_id: str, fallback: dict | None = None) -> dict:
    """Full record for one work, including its catalog description (what the Book Companion is grounded in)."""
    book = dict(fallback or {"work_id": work_id, "title": "Untitled", "author": "Unknown author",
                             "cover_url": None, "first_publish_year": None, "subjects": []})
    book.setdefault("description", "")
    if work_id.startswith("GB:"):
        return book
    try:
        r = httpx.get(f"{OL}/works/{work_id}.json", headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        w = r.json()
        book["work_id"] = work_id
        if not book.get("title") or book["title"] == "Untitled" or not NON_LATIN.search(w.get("title", "x")):
            book["title"] = w.get("title", book["title"]) if not NON_LATIN.search(w.get("title", "")) else book["title"]
        book["description"] = _clean_description(w.get("description")) or book["description"]
        if not book.get("subjects"):
            book["subjects"] = [s for s in w.get("subjects", []) if ":" not in s][:8]
        if not book.get("cover_url") and w.get("covers"):
            book["cover_url"] = cover_url(next((c for c in w["covers"] if c and c > 0), None))
        if book.get("author") in (None, "Unknown author") and w.get("authors"):
            a = httpx.get(f"{OL}{w['authors'][0]['author']['key']}.json", headers=HEADERS, timeout=TIMEOUT)
            if a.is_success:
                book["author"] = a.json().get("name", book["author"])
    except (httpx.HTTPError, KeyError, ValueError):
        pass
    book["source"] = book.get("source", "openlibrary")
    return book


def english_record(work_id: str) -> dict | None:
    """Look up one work's English title and cover (used to repair records saved before English-only search)."""
    try:
        r = httpx.get(f"{OL}/search.json", params={"q": f"key:/works/{work_id}", "fields": SEARCH_FIELDS, "lang": "en"},
                      headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        docs = r.json().get("docs", [])
        return _from_search_doc(docs[0]) if docs and _english(docs[0]) else None
    except httpx.HTTPError:
        return None
