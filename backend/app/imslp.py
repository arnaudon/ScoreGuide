"""IMSLP catalogue: a local copy of IMSLP's works, synced politely, and its search.

The sync reads IMSLP's work list (1,000 works per request) and, for every 50
works, one MediaWiki API request returning their pages' wikitext, from which
the work details (key, year, style, instrumentation, tags, files) are parsed.
No AI is involved. A full pass is ~300 + ~5,600 requests.

IMSLP has blocked us before for unusual traffic, so the client is deliberately
gentle: a single request at a time, at least ``IMSLP_SYNC_DELAY`` seconds
apart (default 3), an identifying User-Agent, MediaWiki ``maxlag``, long
backoffs on 429/5xx/maxlag (honouring ``Retry-After``), and it stops outright
on any other 4xx (e.g. 403: possibly blocked) or after repeated failures.

Progress is stored in the ``imslp_sync`` Setting row after every list page, so
an interrupted sync (cancel, error, deploy) resumes where it stopped.
"""

import contextlib
import html
import json
import logging
import os
import re
import threading
import time
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import ColumnElement
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, delete, func, literal, or_, select, text

from app.db import get_session
from app.rate_limit import limiter
from app.users import get_admin_user, get_current_user
from shared.scores import IMSLP, Period, Score
from shared.settings import Setting
from shared.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/imslp", tags=["imslp"])

USER_AGENT = "ScoreGuide/1.0 (+https://scoreguide.ch; IMSLP catalogue sync, one request at a time)"
LIST_URL = (
    "https://imslp.org/imslpscripts/API.ISCR.php?account=worklist/disclaimer=accepted/"
    "sort=id/type=2/start={start}/retformat=json"
)
WIKI_API = "https://imslp.org/api.php"
LIST_PAGE = 1000  # works per work-list request (fixed by IMSLP)
WIKI_BATCH = 50  # MediaWiki's limit of pages per query for non-bot clients
MAX_FAILURES = 6  # consecutive retryable failures before giving up
MAX_BACKOFF = 900.0
STATE_KEY = "imslp_sync"


def _delay() -> float:
    return float(os.getenv("IMSLP_SYNC_DELAY", "3"))


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ImslpUnavailable(Exception):
    """IMSLP refused or kept failing: the sync stops (and can be resumed later)."""


class _Retry(Exception):
    def __init__(self, reason: str, retry_after: str | None = None):
        super().__init__(reason)
        self.retry_after = retry_after


class ImslpClient:
    """Sequential HTTP client: one request at a time, ``interval`` seconds apart."""

    def __init__(
        self,
        interval: float | None = None,
        sleep: Callable[[float], None] = time.sleep,
        http: httpx.Client | None = None,
    ):
        self.interval = _delay() if interval is None else interval
        self.sleep = sleep
        self.http = http or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True
        )
        self._last = 0.0

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET ``url`` as JSON, waiting between requests and backing off on errors."""
        failures = 0
        while True:
            wait = self._last + self.interval - time.monotonic()
            if wait > 0:
                self.sleep(wait)
            self._last = time.monotonic()
            try:
                resp = self.http.get(url, params=params)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise _Retry(f"HTTP {resp.status_code}", resp.headers.get("Retry-After"))
                if resp.status_code >= 400:
                    # 403 & co: possibly blocked. Never insist.
                    raise ImslpUnavailable(f"IMSLP answered HTTP {resp.status_code}; stopped")
                data = resp.json()
                error = data.get("error") if isinstance(data, dict) else None
                if isinstance(error, dict) and error.get("code") == "maxlag":
                    raise _Retry("maxlag", resp.headers.get("Retry-After"))
                return data
            except (_Retry, httpx.TransportError, ValueError) as e:
                failures += 1
                if failures >= MAX_FAILURES:
                    raise ImslpUnavailable(f"IMSLP kept failing ({e}); stopped") from e
                backoff = min(MAX_BACKOFF, 30.0 * 2 ** (failures - 1))
                retry_after = getattr(e, "retry_after", None)
                if retry_after and retry_after.isdigit():
                    backoff = min(MAX_BACKOFF, max(backoff, float(retry_after)))
                logger.warning("IMSLP request failed (%s), retrying in %.0fs", e, backoff)
                self.sleep(backoff)


# --- Parsing ----------------------------------------------------------------

_ASCII = str.maketrans({"ø": "o", "æ": "ae", "œ": "oe", "ß": "ss", "ł": "l", "đ": "d", "ð": "d"})


def normalize(value: str) -> str:
    """Lower-case, accent-free, punctuation-free text for matching."""
    decomposed = unicodedata.normalize("NFKD", value.lower().translate(_ASCII))
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain).split())


_ACCIDENTALS = {"sharp": "♯", "flat": "♭", "natural": "♮"}
_KEY = re.compile(r"([A-Ga-g])(#|b|-sharp|-flat)?")


def _key_name(arg: str) -> str:
    """IMSLP's {{K|bb}} shorthand: upper case is major, lower case minor."""
    m = _KEY.fullmatch(arg.strip())
    if not m:
        return arg
    note, acc = m.groups()
    sign = {"#": "-sharp", "b": "-flat"}.get(acc or "", acc or "")
    return f"{note.upper()}{sign} {'major' if note.isupper() else 'minor'}"


def _template_args(match: re.Match) -> str:
    name, *parts = match.group(1).split("|")
    name = name.strip().lower()
    args = [a.strip() for a in parts if "=" not in a]
    if name.startswith("#subitem"):  # a movement: {{#subitem:id=..|title=Largo}}
        return next((a.split("=", 1)[1] for a in parts if a.startswith("title=")), "")
    if name in _ACCIDENTALS:
        return _ACCIDENTALS[name]
    if name in ("k", "key") and args:
        return _key_name(args[0])
    if name == "tons":  # "in all keys"
        return "Various"
    if name == "linkwork":  # title, catalogue number, composer...
        return ", ".join(a for a in args[:2] if a)
    if name == "wc" and args:  # {{WC|worldcat id|label}}
        return args[-1]
    if name.startswith("link"):  # LinkDed|First|Last, LinkComp...: a person
        return " ".join(args[:2])
    if re.fullmatch(r"[a-z]{2}", name) and not args:  # {{EN}}: language flag
        return ""
    return " ".join(args)


# A field can start mid-line ("organ |Tags=...") or on an indented line.
_INLINE_FIELD = re.compile(r"[ \t]+\|(?=[A-Z][A-Za-z/ ]{1,40}=)")


def clean_wiki(value: str) -> str:
    """Wikitext to plain text: drop markup, keep link labels and template arguments."""
    t = re.sub(r"<!--.*?-->", "", value, flags=re.S)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    for _ in range(3):  # nested templates, innermost first
        t = re.sub(r"\{\{([^{}]*)\}\}", _template_args, t)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[https?://\S+\s*([^\]]*)\]", r"\1", t)
    t = t.replace("'''", "").replace("''", "")
    t = html.unescape(t)
    # One line per list item or <br>: drop list markers (":", "#", "*"), join with commas.
    lines = (re.sub(r"^[\s:#*]+", "", line).strip(" ,") for line in t.splitlines())
    t = ", ".join(line for line in lines if line)
    t = re.sub(r"([;,:])(\s*[;,])+", r"\1", t)
    return " ".join(t.split()).strip(" ,;")


_FIELD = re.compile(r"^\|\s*([^=\n|]+?)\s*=(.*?)(?=^\||\Z)", re.M | re.S)


def parse_work_info(wikitext: str) -> dict[str, str]:
    """The ``|Field=value`` pairs of an IMSLP work page's WORK INFO section."""
    start = wikitext.find("*****WORK INFO*****")
    if start < 0:
        return {}
    body = wikitext[start + len("*****WORK INFO*****") :]
    end = re.search(r"\|\s*\*{5}", body)
    if end:
        body = body[: end.start()]
    body = _INLINE_FIELD.sub("\n|", body)
    return {k.strip(): clean_wiki(v) for k, v in _FIELD.findall(body)}


def parse_files(wikitext: str) -> list[dict[str, str]]:
    """The score files listed on a work page: file name, description, copyright."""
    files = []
    for block in wikitext.split("{{#fte:imslpfile")[1:]:
        names = dict(re.findall(r"^\|\s*File Name (\d+)\s*=([^\n]*)", block, re.M))
        descs = dict(re.findall(r"^\|\s*File Description (\d+)\s*=([^\n]*)", block, re.M))
        rights = re.search(r"^\|\s*Copyright\s*=([^\n]*)", block, re.M)
        for num, name in names.items():
            files.append(
                {
                    "file": name.strip(),
                    "description": clean_wiki(descs.get(num, "")),
                    "copyright": clean_wiki(rights.group(1)) if rights else "",
                }
            )
    return files


def parse_year(*values: str) -> int:
    """First plausible year (1000-2099) in the values, 0 when unknown."""
    for value in values:
        m = re.search(r"(?<!\d)(1\d{3}|20\d{2})(?!\d)", value)
        if m:
            return int(m.group(1))
    return 0


_PERIOD_WORDS = [
    ("postmodern", Period.Postmodernist),
    ("contemporary", Period.Postmodernist),
    ("modern", Period.Modernist),
    ("romantic", Period.Romantic),
    ("classical", Period.Classical),
    ("baroque", Period.Baroque),
    ("renaissance", Period.Renaissance),
    ("medieval", Period.Medieval),
]
_PERIOD_YEARS = [
    (1400, Period.Medieval),
    (1600, Period.Renaissance),
    (1750, Period.Baroque),
    (1820, Period.Classical),
    (1910, Period.Romantic),
    (1975, Period.Modernist),
]


def parse_period(style: str, year: int) -> Period | None:
    """Period from IMSLP's Piece Style, else from the composition year."""
    lowered = style.lower()
    for word, period in _PERIOD_WORDS:
        if word in lowered:
            return period
    if not year:
        return None
    for limit, period in _PERIOD_YEARS:
        if year < limit:
            return period
    return Period.Postmodernist


# IMSLP tag abbreviations for instruments and forces: not genres.
_INSTRUMENT_TAGS = {
    "pf", "org", "hpd", "vn", "va", "vc", "db", "fl", "ob", "cl", "bn", "hn", "tpt", "tbn",
    "tu", "gtr", "hp", "perc", "timp", "ch", "orch", "str", "voice", "voices", "sop", "alt",
    "ten", "bar", "bass", "mez", "rec", "lute", "sax", "acc", "cel", "man", "pic", "ehn",
    "bcl", "kbd", "hmn", "pf4h", "band", "mixed", "unacc", "pf6h", "cbn", "cornet",
}  # fmt: skip


def parse_genre(tags: str) -> str:
    """The first genre-like IMSLP tag ("sonatas ; pf" -> "Sonatas")."""
    for tag in (t.strip() for t in tags.split(";")):
        words = tag.lower().split()
        if not tag or any(c.isdigit() for c in tag) or all(w in _INSTRUMENT_TAGS for w in words):
            continue
        return tag[0].upper() + tag[1:]
    return ""


def build_row(item: dict[str, Any], wikitext: str) -> dict[str, Any]:
    """IMSLP table values for one work-list item and its page's wikitext."""
    intvals = item.get("intvals") or {}
    info = parse_work_info(wikitext)
    title = intvals.get("worktitle") or info.get("Work Title") or str(item.get("id", ""))
    composer = intvals.get("composer", "")
    catalogue = info.get("Opus/Catalogue Number", "")
    year = parse_year(
        info.get("Year/Date of Composition", ""), info.get("Year of First Publication", "")
    )
    style = info.get("Piece Style", "")
    genre = parse_genre(info.get("Tags", ""))
    # "Various (together with 13 Preludes, Op.32...)": the cross-reference is noise here.
    key = re.sub(r"\s*\(together with\b.*", "", info.get("Key", ""), flags=re.S)
    instrumentation = info.get("Instrumentation", "")
    searchable = [title, catalogue, composer, info.get("Alternative Title", ""), key]
    return {
        "title": title[:500],
        "composer": composer[:300],
        "catalogue": catalogue[:200],
        "year": year,
        "period": parse_period(style, year),
        "genre": genre[:200],
        "form": "",
        "style": style[:200],
        "key": key[:200],
        "instrumentation": instrumentation[:500],
        "permlink": item.get("permlink", ""),
        "score_metadata": json.dumps(info, ensure_ascii=False),
        "pdf_urls": json.dumps(parse_files(wikitext), ensure_ascii=False),
        "search_text": normalize(" ".join([*searchable, instrumentation, genre])),
    }


# --- Sync -------------------------------------------------------------------

_running = threading.Lock()
_cancel = threading.Event()


def load_state(session: Session) -> dict[str, Any]:
    """The persisted sync state (status, list position, counters, last error)."""
    row = session.get(Setting, STATE_KEY)
    state: dict[str, Any] = {"status": "idle", "start": 0, "works": 0, "error": ""}
    if row:
        with contextlib.suppress(ValueError):
            state.update(json.loads(row.value))
    return state


def save_state(session: Session, state: dict[str, Any]) -> None:
    """Persist the sync state (commits)."""
    state["updated_at"] = _now().isoformat(timespec="seconds")
    row = session.get(Setting, STATE_KEY) or Setting(key=STATE_KEY, value="")
    row.value = json.dumps(state)
    session.add(row)
    session.commit()


def _wikitexts(client: ImslpClient, pageids: list[int]) -> dict[int, str]:
    data = client.get_json(
        WIKI_API,
        params={
            "action": "query",
            "format": "json",
            "maxlag": 5,
            "prop": "revisions",
            "rvprop": "content",
            "pageids": "|".join(str(p) for p in pageids),
        },
    )
    pages = (data.get("query") or {}).get("pages") or {}
    out = {}
    for page in pages.values() if isinstance(pages, dict) else pages:
        revisions = page.get("revisions") or [{}]
        rev = revisions[0]
        content = rev.get("*") or rev.get("content") or ""
        if "pageid" in page:
            out[int(page["pageid"])] = content
    return out


def _has_pageid(item: Any) -> bool:
    return isinstance(item, dict) and str((item.get("intvals") or {}).get("pageid", "")).isdigit()


def _pages_by_title(client: ImslpClient, titles: list[str]) -> dict[str, tuple[int, str, bool]]:
    """Page id, wikitext and whether it was a redirect, keyed by requested title."""
    found: dict[str, tuple[int, str, bool]] = {}
    for i in range(0, len(titles), WIKI_BATCH):
        batch = titles[i : i + WIKI_BATCH]
        data = client.get_json(
            WIKI_API,
            params={
                "action": "query",
                "format": "json",
                "maxlag": 5,
                "redirects": 1,
                "prop": "revisions",
                "rvprop": "content",
                "titles": "|".join(batch),
            },
        )
        query = data.get("query") or {}
        normalized = {n["from"]: n["to"] for n in query.get("normalized") or []}
        redirects = {r["from"]: r["to"] for r in query.get("redirects") or []}
        pages = query.get("pages") or {}
        by_title = {}
        for page in pages.values() if isinstance(pages, dict) else pages:
            if "pageid" in page and "missing" not in page:
                rev = (page.get("revisions") or [{}])[0]
                by_title[page.get("title")] = (int(page["pageid"]), rev.get("*") or "")
        for title in batch:
            name = normalized.get(title, title)
            target = redirects.get(name, name)
            if target in by_title:
                found[title] = (*by_title[target], target != name)
    return found


def _work_items(client: ImslpClient, data: dict[str, Any]) -> tuple[list[dict], dict[int, str]]:
    """The list page's works with a trustworthy page id, and wikitexts already fetched.

    IMSLP's work list is not always consistent: some works come without a page
    id, and several different titles can share one. Those are looked up by
    title instead (one extra request per 50); titles that turn out to be
    redirects to another work are dropped, since that work has its own entry.
    """
    items = [v for v in data.values() if isinstance(v, dict) and v.get("id")]
    titles: dict[int, set[str]] = {}
    for item in items:
        if _has_pageid(item):
            titles.setdefault(int(item["intvals"]["pageid"]), set()).add(item["id"])
    doubtful = [
        item["id"]
        for item in items
        if not _has_pageid(item) or len(titles[int(item["intvals"]["pageid"])]) > 1
    ]
    resolved = _pages_by_title(client, doubtful) if doubtful else {}
    skip = set(doubtful)  # not found on the wiki (deleted or renamed)
    texts: dict[int, str] = {}
    works = []
    for item in items:
        if item["id"] in resolved:
            pageid, text, redirect = resolved[item["id"]]
            if redirect:
                continue
            item = {**item, "intvals": {**(item.get("intvals") or {}), "pageid": str(pageid)}}
            texts[pageid] = text
        elif item["id"] in skip:
            continue
        works.append(item)
    return works, texts


def _store(session: Session, items: list[dict[str, Any]], wikitexts: dict[int, str]) -> int:
    """Upsert works by IMSLP page id; adopt matching rows from the old scraper."""
    rows = {}
    for item in items:
        pageid = int(item["intvals"]["pageid"])
        rows[pageid] = build_row(item, wikitexts.get(pageid, ""))
    existing = {
        r.pageid: r for r in session.exec(select(IMSLP).where(col(IMSLP.pageid).in_(list(rows))))
    }
    permlinks = [r["permlink"] for p, r in rows.items() if p not in existing]
    legacy = {
        r.permlink: r
        for r in session.exec(
            select(IMSLP).where(col(IMSLP.pageid).is_(None), col(IMSLP.permlink).in_(permlinks))
        )
    }
    now = _now()
    for pageid, values in rows.items():
        # Rows from the old scraper keep their id, so scores linked to them stay linked.
        entry = existing.get(pageid) or legacy.pop(values["permlink"], None) or IMSLP(**values)
        for field, value in values.items():
            setattr(entry, field, value)
        entry.pageid = pageid
        entry.synced_at = now
        session.add(entry)
    session.commit()
    return len(rows)


def _finish(session: Session, run_started: str) -> int:
    """After a complete pass: drop works no longer on IMSLP and old-scraper rows."""
    started = datetime.fromisoformat(run_started)
    stale = or_(col(IMSLP.pageid).is_(None), col(IMSLP.synced_at) < started)
    removed = session.exec(select(func.count()).select_from(IMSLP).where(stale)).one()
    session.exec(delete(IMSLP).where(stale))  # type: ignore[call-overload]
    session.commit()
    return removed


def sync_catalogue(engine: Engine, restart: bool = False, client: ImslpClient | None = None):
    """Background job: (re)sync the IMSLP catalogue, resuming a stopped pass."""
    if not _running.acquire(blocking=False):
        return
    _cancel.clear()
    try:
        with Session(engine) as session:
            state = load_state(session)
            if restart or state["status"] in ("idle", "completed") or not state.get("run_started"):
                state.update(start=0, works=0, run_started=_now().isoformat(timespec="seconds"))
            state.update(status="running", error="")
            save_state(session, state)
            client = client or ImslpClient()
            try:
                while True:
                    if _cancel.is_set():
                        state["status"] = "cancelled"
                        break
                    data = client.get_json(LIST_URL.format(start=state["start"]))
                    meta = data.pop("metadata", {}) if isinstance(data, dict) else {}
                    items, texts = _work_items(client, data or {})
                    missing = [int(it["intvals"]["pageid"]) for it in items]
                    missing = [p for p in missing if p not in texts]
                    for i in range(0, len(missing), WIKI_BATCH):
                        texts.update(_wikitexts(client, missing[i : i + WIKI_BATCH]))
                    state["works"] += _store(session, items, texts)
                    state["start"] += LIST_PAGE
                    if not data or not meta.get("moreresultsavailable"):
                        state["removed"] = _finish(session, state["run_started"])
                        state["status"] = "completed"
                        break
                    save_state(session, state)
            except ImslpUnavailable as e:
                logger.error("IMSLP sync stopped: %s", e)
                state.update(status="error", error=str(e))
            except Exception as e:
                logger.exception("IMSLP sync failed")
                state.update(status="error", error=f"{type(e).__name__}: {e}"[:500])
            session.rollback()  # a failed flush leaves the session unusable
            save_state(session, state)
    finally:
        _running.release()


def resume_interrupted(engine: Engine) -> None:  # pragma: no cover - startup hook
    """Restart a sync that was running when the backend stopped (e.g. a deploy)."""
    with Session(engine) as session:
        if load_state(session)["status"] != "running":
            return
    threading.Thread(target=sync_catalogue, args=(engine,), daemon=True).start()


@router.post("/start", dependencies=[Depends(get_admin_user)])
def start_sync(
    background_tasks: BackgroundTasks,
    restart: bool = False,
    session: Session = Depends(get_session),
):
    """Start the IMSLP sync, resuming a stopped pass unless ``restart``."""
    if _running.locked():
        raise HTTPException(status_code=409, detail="A sync is already running")
    engine = session.get_bind()
    assert isinstance(engine, Engine)
    background_tasks.add_task(sync_catalogue, engine, restart)
    return {"message": "Sync started"}


@router.post("/progress", dependencies=[Depends(get_admin_user)])
def get_progress(session: Session = Depends(get_session)):
    """The sync state, and whether it is running in this process."""
    return {**load_state(session), "running": _running.locked()}


@router.post("/cancel", dependencies=[Depends(get_admin_user)])
def cancel(session: Session = Depends(get_session)):
    """Stop the sync after the current page; it can be resumed later."""
    _cancel.set()
    if not _running.locked():
        state = load_state(session)
        if state["status"] == "running":
            state["status"] = "cancelled"
            save_state(session, state)
    return {"message": "Cancelling"}


@router.get("/stats", dependencies=[Depends(get_admin_user)])
def get_imslp_stats(session: Session = Depends(get_session)):
    """Get IMSLP stats"""
    return {
        "total_works": session.exec(select(func.count()).select_from(IMSLP)).one(),
        "total_composers": session.exec(select(func.count(func.distinct(IMSLP.composer)))).one(),
    }


@router.post("/empty", dependencies=[Depends(get_admin_user)])
def empty(session: Session = Depends(get_session)):
    """Empty the IMSLP table."""
    if _running.locked():
        raise HTTPException(status_code=409, detail="A sync is running")
    if session.bind and session.bind.dialect.name == "postgresql":
        session.execute(text("TRUNCATE TABLE imslp RESTART IDENTITY CASCADE;"))  # pragma: no cover
    else:
        session.execute(text("DELETE FROM imslp;"))
    state = session.get(Setting, STATE_KEY)
    if state:
        session.delete(state)
    session.commit()


# --- Search -----------------------------------------------------------------


class ImslpResult(BaseModel):
    """A catalogue entry as returned by the search."""

    id: int
    title: str
    composer: str
    catalogue: str
    year: int
    period: Period | None
    genre: str
    key: str
    instrumentation: str
    permlink: str
    in_library: bool


class ImslpSearch(BaseModel):
    """One page of search results."""

    total: int
    results: list[ImslpResult]


def solo_forms(instrument: str) -> list[str]:
    """How IMSLP writes a work for that instrument alone ("piano", "piano solo", "1 piano")."""
    name = instrument.strip().lower()
    return [name, f"{name} solo", f"solo {name}", f"1 {name}"]


def _instrument_filter(stmt, instrument: str, solo: bool):
    """Works for that instrument: any scoring that includes it, or (solo) it alone."""
    name = instrument.strip().lower()
    if not name:
        return stmt
    if solo:
        return stmt.where(func.lower(func.trim(IMSLP.instrumentation)).in_(solo_forms(name)))
    return stmt.where(func.lower(IMSLP.instrumentation).contains(name))


@router.get("/search")
@limiter.limit("120/minute")
def search(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    q: Annotated[str, Query(max_length=200)] = "",
    instrument: Annotated[str, Query(max_length=50)] = "",
    solo: bool = False,
    period: Period | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0, le=5000)] = 0,
    session: Session = Depends(get_session),
) -> ImslpSearch:
    """Search the catalogue by title, composer, catalogue number or key.

    ``instrument`` keeps works scored for it; with ``solo``, only works for that
    instrument alone (no duets, accompaniments or ensembles).

    Words match anywhere, ignoring case and accents ("frederic chopin nocturne").
    When nothing matches, Postgres falls back to a typo-tolerant search.
    """
    tokens = normalize(q).split()[:8]
    if not tokens:
        return ImslpSearch(total=0, results=[])
    stmt = select(IMSLP)
    for token in tokens:
        stmt = stmt.where(col(IMSLP.search_text).contains(token))
    stmt = _instrument_filter(stmt, instrument, solo)
    if period:
        stmt = stmt.where(IMSLP.period == period)
    ordered = stmt.order_by(func.length(IMSLP.title), IMSLP.title, IMSLP.id)

    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = list(session.exec(ordered.offset(offset).limit(limit)))
    if not total and session.bind and session.bind.dialect.name == "postgresql":  # pragma: no cover
        # Typo-tolerant: every word must be close to a word of the entry
        # (pg_trgm's indexed <% operator), best matches first.
        fuzzy = select(IMSLP)
        for token in tokens:
            fuzzy = fuzzy.where(literal(token).op("<%")(IMSLP.search_text))
        fuzzy = _instrument_filter(fuzzy, instrument, solo)
        if period:
            fuzzy = fuzzy.where(IMSLP.period == period)
        closeness: ColumnElement[float] = func.word_similarity(tokens[0], IMSLP.search_text)
        for token in tokens[1:]:
            closeness = closeness + func.word_similarity(token, IMSLP.search_text)
        total = session.exec(select(func.count()).select_from(fuzzy.subquery())).one()
        rows = list(session.exec(fuzzy.order_by(closeness.desc()).offset(offset).limit(limit)))

    ids = [r.id for r in rows]
    owned = set(
        session.exec(
            select(Score.imslp_id).where(
                Score.user_id == current_user.id, col(Score.imslp_id).in_(ids)
            )
        )
    )
    return ImslpSearch(
        total=total,
        results=[
            ImslpResult(
                id=r.id,  # type: ignore[arg-type]
                title=r.title,
                composer=r.composer,
                catalogue=r.catalogue,
                year=r.year,
                period=r.period,
                genre=r.genre,
                key=r.key,
                instrumentation=r.instrumentation,
                permlink=r.permlink,
                in_library=r.id in owned,
            )
            for r in rows
        ],
    )


class ImslpFile(BaseModel):
    """One score file of a work, with the IMSLP page where the user downloads it."""

    file: str
    description: str
    copyright: str
    url: str


def file_page_url(name: str) -> str:
    """IMSLP's page for one file (``File:<name>``), which offers the download."""
    return "https://imslp.org/wiki/File:" + quote(name.strip().replace(" ", "_"), safe="()_,-.'!")


@router.get("/{imslp_id}/files", dependencies=[Depends(get_current_user)])
@limiter.limit("120/minute")
def get_files(
    request: Request, imslp_id: int, session: Session = Depends(get_session)
) -> list[ImslpFile]:
    """The score files of a catalogue entry, as listed on its IMSLP page.

    Only links: ScoreGuide never downloads from IMSLP, the user does.
    """
    entry = session.get(IMSLP, imslp_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="IMSLP entry not found")
    try:
        listed = json.loads(entry.pdf_urls or "[]")
    except json.JSONDecodeError:
        listed = []
    if not isinstance(listed, list):
        listed = []
    return [
        ImslpFile(
            file=str(f["file"]).strip(),
            description=str(f.get("description") or ""),
            copyright=str(f.get("copyright") or ""),
            url=file_page_url(str(f["file"])),
        )
        for f in listed
        if isinstance(f, dict) and str(f.get("file") or "").strip()
    ]


@router.get("/scores_by_ids", dependencies=[Depends(get_current_user)])
def get_by_ids(score_ids: str, session: Session = Depends(get_session)):
    """Get scores by ids."""
    detail = "score_ids must be a JSON array of at most 500 integers"
    try:
        ids = json.loads(score_ids)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=detail) from e
    if (
        not isinstance(ids, list)
        or len(ids) > 500
        or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids)
    ):
        raise HTTPException(status_code=422, detail=detail)

    return session.exec(select(IMSLP).where(col(IMSLP.id).in_(ids))).all()
