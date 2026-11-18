"""Tests for the IMSLP catalogue: parsing, polite client, resumable sync, search."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import imslp
from app.main import app
from app.rate_limit import limiter
from app.users import get_admin_user
from shared.scores import IMSLP, Period, Score
from shared.settings import Setting

WIKITEXT = """{{#fte:imslppage

| *****FILES***** =
{{#fte:imslpfile
|File Name 1=PMLP01-Chopin-Op38.pdf
|File Description 1=Complete Score
|File Name 2=PMLP01-Chopin-Op38-parts.pdf
|File Description 2=[[Parts|All parts]]
|Copyright=Public Domain
}}
{{#fte:imslpfile
|File Name 1=PMLP01-Mikuli.pdf
|File Description 1=Complete Score {{LinkEd|Karol|Mikuli}}
|Copyright=Public Domain
}}
| *****WORK INFO*****

|Work Title=Ballade No.2
|Alternative Title=Ballade in F major
|Opus/Catalogue Number=Op.38 <!-- B.102 -->
|Key=F major
|Number of Movements/Sections=1
#Andantino
|Year/Date of Composition=1836–39
|Piece Style=Romantic
|Instrumentation=[[piano]]
|Tags=ballades ; pf

|A free comment line, not a field.

| *****COMMENTS***** =
| *****END OF TEMPLATE***** }}"""


def _item(pageid: int, title: str, composer: str = "Chopin, Frédéric") -> dict:
    return {
        "id": f"{title} ({composer})",
        "intvals": {"composer": composer, "worktitle": title, "pageid": str(pageid)},
        "permlink": f"https://imslp.org/wiki/{title}",
    }


# --- Parsing ------------------------------------------------------------------


def test_parse_work_info():
    info = imslp.parse_work_info(WIKITEXT)
    assert info["Work Title"] == "Ballade No.2"
    assert info["Opus/Catalogue Number"] == "Op.38"
    assert info["Instrumentation"] == "piano"
    assert info["Tags"] == "ballades ; pf"
    assert info["Number of Movements/Sections"] == "1, Andantino"
    assert "COMMENTS" not in json.dumps(info)
    assert imslp.parse_work_info("no template") == {}


def test_parse_files():
    files = imslp.parse_files(WIKITEXT)
    assert [(f["file"], f["description"]) for f in files] == [
        ("PMLP01-Chopin-Op38.pdf", "Complete Score"),
        ("PMLP01-Chopin-Op38-parts.pdf", "All parts"),
        ("PMLP01-Mikuli.pdf", "Complete Score Karol Mikuli"),
    ]
    assert {f["copyright"] for f in files} == {"Public Domain"}
    assert imslp.parse_files("|File Name 1=a.pdf") == []


def test_clean_wiki():
    assert imslp.clean_wiki("''Allegro''<br/>[[Presto]] [http://x.org site] {{a|{{b|c}}|k=v}}") == (
        "Allegro, Presto site c"
    )


@pytest.mark.parametrize(
    ("values", "year"),
    [(("1836–39",), 1836), (("ca. 1720?",), 1720), (("", "Pub. 2022"), 2022), (("Op.38",), 0)],
)
def test_parse_year(values, year):
    assert imslp.parse_year(*values) == year


@pytest.mark.parametrize(
    ("style", "year", "period"),
    [
        ("Early Romantic", 0, Period.Romantic),
        ("Modern", 0, Period.Modernist),
        ("Postmodern", 1950, Period.Postmodernist),
        ("", 1720, Period.Baroque),
        ("", 1300, Period.Medieval),
        ("", 1990, Period.Postmodernist),
        ("", 0, None),
    ],
)
def test_parse_period(style, year, period):
    assert imslp.parse_period(style, year) == period


def test_parse_genre():
    assert imslp.parse_genre("ballades ; pf") == "Ballades"
    assert imslp.parse_genre("pf ; for 2 players ; chorale preludes") == "Chorale preludes"
    assert imslp.parse_genre("vn pf ; org") == ""


def test_normalize():
    assert (
        imslp.normalize("Dvořák: Słowiańskie Tańce, Op.46 — Ø")
        == "dvorak slowianskie tance op 46 o"
    )


def test_build_row():
    row = imslp.build_row(_item(7, "Ballade No.2, Op.38"), WIKITEXT)
    assert row["title"] == "Ballade No.2, Op.38"
    assert row["catalogue"] == "Op.38"
    assert (row["year"], row["period"], row["genre"], row["key"]) == (
        1836,
        Period.Romantic,
        "Ballades",
        "F major",
    )
    assert row["search_text"].startswith("ballade no 2 op 38 op 38 chopin frederic")
    assert len(json.loads(row["pdf_urls"])) == 3
    # A page we couldn't read still gets the work list's title and composer.
    bare = imslp.build_row({"id": "X (Y)", "intvals": {}, "permlink": "p"}, "")
    assert (bare["title"], bare["composer"], bare["period"], bare["year"]) == ("X (Y)", "", None, 0)


# --- Client -------------------------------------------------------------------


def _client(responses: list, sleeps: list, interval: float = 0.0) -> imslp.ImslpClient:
    queue = list(responses)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        nxt = queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    client = imslp.ImslpClient(
        interval=interval,
        sleep=sleeps.append,
        http=httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": "t"}),
    )
    client.seen = seen  # type: ignore[attr-defined]
    return client


def test_client_backs_off_and_retries():
    sleeps: list[float] = []
    client = _client(
        [
            httpx.Response(503),
            httpx.Response(429, headers={"Retry-After": "120"}),
            httpx.Response(200, json={"error": {"code": "maxlag"}}),
            httpx.Response(200, text="<html>not json</html>"),
            httpx.ConnectError("down"),
            httpx.Response(200, json={"ok": 1}),
        ],
        sleeps,
    )
    assert client.get_json("https://imslp.org/x") == {"ok": 1}
    assert sleeps == [30.0, 120.0, 120.0, 240.0, 480.0]


def test_client_stops_on_client_errors_and_repeated_failures():
    with pytest.raises(imslp.ImslpUnavailable, match="HTTP 403"):
        _client([httpx.Response(403)], []).get_json("https://imslp.org/x")
    sleeps: list[float] = []
    failing = _client([httpx.Response(502)] * imslp.MAX_FAILURES, sleeps)
    with pytest.raises(imslp.ImslpUnavailable, match="kept failing"):
        failing.get_json("https://imslp.org/x")
    assert len(sleeps) == imslp.MAX_FAILURES - 1
    assert max(sleeps) <= imslp.MAX_BACKOFF


def test_client_spaces_requests():
    sleeps: list[float] = []
    client = _client([httpx.Response(200, json={})] * 2, sleeps, interval=60)
    client.get_json("https://imslp.org/a")
    client.get_json("https://imslp.org/b")
    assert len(sleeps) == 1 and 59 < sleeps[0] <= 60
    assert client.seen[0].headers["User-Agent"] == "t"  # type: ignore[attr-defined]


def test_default_client_identifies_itself(monkeypatch):
    monkeypatch.setenv("IMSLP_SYNC_DELAY", "7")
    client = imslp.ImslpClient()
    assert client.interval == 7
    assert "ScoreGuide" in client.http.headers["User-Agent"]


# --- Sync ---------------------------------------------------------------------


class FakeImslp:
    """Serves work-list pages and wiki batches; records requests."""

    def __init__(
        self, pages: list[dict], fail_at: int | None = None, on_list=None, wiki: dict | None = None
    ):
        self.pages = pages
        self.wiki = wiki or {}  # page title -> page id, or redirect target title
        self.fail_at = fail_at
        self.on_list = on_list
        self.calls: list[tuple[str, dict | None]] = []

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        if params is None:
            start = int(url.split("start=")[1].split("/")[0])
            index = start // imslp.LIST_PAGE
            if index == self.fail_at:
                raise imslp.ImslpUnavailable("IMSLP answered HTTP 403; stopped")
            if self.on_list:
                self.on_list()
            return json.loads(json.dumps(self.pages[index]))
        if "titles" in params:
            return self._by_title(params["titles"].split("|"))
        ids = params["pageids"].split("|")
        return {
            "query": {"pages": {i: {"pageid": int(i), "revisions": [{"*": WIKITEXT}]} for i in ids}}
        }

    def _by_title(self, titles: list[str]) -> dict:
        """Mimics MediaWiki: normalizes titles, follows redirects, flags missing pages."""
        normalized = [{"from": t, "to": t[0].upper() + t[1:]} for t in titles if t[0].islower()]
        names = [t[0].upper() + t[1:] for t in titles]
        redirects = [
            {"from": n, "to": self.wiki[n]} for n in names if isinstance(self.wiki.get(n), str)
        ]
        targets = {self.wiki[n] if isinstance(self.wiki.get(n), str) else n for n in names}
        pages = {}
        for n, title in enumerate(sorted(targets)):
            pageid = self.wiki.get(title)
            if isinstance(pageid, int):
                pages[str(pageid)] = {
                    "pageid": pageid,
                    "title": title,
                    "revisions": [{"*": WIKITEXT}],
                }
            else:
                pages[str(-n - 1)] = {"title": title, "missing": ""}
        return {"query": {"pages": pages, "redirects": redirects, "normalized": normalized}}


def _list_page(items: list[dict], more: bool) -> dict:
    page: dict = {str(i): item for i, item in enumerate(items)}
    page["metadata"] = {"moreresultsavailable": more}
    return page


def _engine(session: Session):
    return session.get_bind()


def test_sync_full_pass(session: Session, test_user):
    """Upserts by page id, adopts old-scraper rows (keeping links), drops stale ones."""
    session.add(test_user)
    legacy = IMSLP(id=5, title="Old", composer="C", permlink="https://imslp.org/wiki/Ballade")
    gone = IMSLP(id=6, title="Gone", composer="C", permlink="https://imslp.org/wiki/Gone")
    session.add_all([legacy, gone])
    session.commit()
    session.add(Score(title="Mine", composer="C", user_id=test_user.id, imslp_id=5))
    session.commit()

    fake = FakeImslp(
        [
            _list_page([_item(11, "Ballade"), _item(12, "Nocturne"), {"bad": 1}], more=True),
            _list_page([_item(13, "Etude")], more=False),
        ]
    )
    imslp.sync_catalogue(_engine(session), client=fake)  # type: ignore[arg-type]

    session.expire_all()
    rows = {r.pageid: r for r in session.exec(select(IMSLP))}
    assert set(rows) == {11, 12, 13}
    assert rows[11].id == 5  # adopted: the score's link survives
    assert rows[11].title == "Ballade" and rows[11].genre == "Ballades"
    state = imslp.load_state(session)
    assert (state["status"], state["works"], state["removed"]) == ("completed", 3, 1)
    wiki_calls = [p for _, p in fake.calls if p]
    assert wiki_calls[0]["maxlag"] == 5 and wiki_calls[0]["pageids"] == "11|12"

    # A second pass updates rows in place.
    imslp.sync_catalogue(_engine(session), client=fake)  # type: ignore[arg-type]
    session.expire_all()
    assert session.exec(select(IMSLP.id).where(IMSLP.pageid == 11)).one() == 5
    assert len(session.exec(select(IMSLP)).all()) == 3


def test_sync_stops_and_resumes(session: Session):
    pages = [_list_page([_item(1, "A")], more=True), _list_page([_item(2, "B")], more=False)]
    imslp.sync_catalogue(_engine(session), client=FakeImslp(pages, fail_at=1))  # type: ignore[arg-type]
    state = imslp.load_state(session)
    assert (state["status"], state["start"], state["works"]) == ("error", 1000, 1)
    assert "403" in state["error"]

    resumed = FakeImslp(pages)
    imslp.sync_catalogue(_engine(session), client=resumed)  # type: ignore[arg-type]
    assert "start=1000/" in resumed.calls[0][0]
    session.expire_all()
    state = imslp.load_state(session)
    assert (state["status"], state["works"], state["removed"]) == ("completed", 2, 0)

    restarted = FakeImslp(pages)
    imslp.sync_catalogue(_engine(session), restart=True, client=restarted)  # type: ignore[arg-type]
    assert "start=0/" in restarted.calls[0][0]


def test_sync_cancel_and_failures(session: Session, monkeypatch):
    pages = [_list_page([_item(1, "A")], more=True), _list_page([], more=False)]
    cancelling = FakeImslp(pages, on_list=imslp._cancel.set)
    imslp.sync_catalogue(_engine(session), client=cancelling)  # type: ignore[arg-type]
    assert imslp.load_state(session)["status"] == "cancelled"

    class Broken:
        def get_json(self, url, params=None):
            raise RuntimeError("boom")

    imslp.sync_catalogue(_engine(session), client=Broken())  # type: ignore[arg-type]
    session.expire_all()
    state = imslp.load_state(session)
    assert (state["status"], state["error"]) == ("error", "RuntimeError: boom")

    # A database error mid-pass is still recorded.
    def bad_store(session, items, wikitexts):
        session.add(IMSLP(title=None, composer="C", permlink="p"))  # type: ignore[arg-type]
        session.flush()

    monkeypatch.setattr(imslp, "_store", bad_store)
    pages = [_list_page([_item(1, "A")], more=False)]
    imslp.sync_catalogue(_engine(session), restart=True, client=FakeImslp(pages))  # type: ignore[arg-type]
    session.expire_all()
    state = imslp.load_state(session)
    assert state["status"] == "error" and state["error"].startswith("IntegrityError")

    # Only one sync at a time.
    with imslp._running:
        imslp.sync_catalogue(_engine(session), client=Broken())  # type: ignore[arg-type]
    session.expire_all()
    assert imslp.load_state(session)["error"].startswith("IntegrityError")

    session.add(Setting(key="unrelated", value="x"))
    row = session.get(Setting, imslp.STATE_KEY)
    assert row is not None
    row.value = "not json"
    session.commit()
    assert imslp.load_state(session)["status"] == "idle"


# --- Endpoints ----------------------------------------------------------------


@pytest.fixture(name="admin")
def admin_fixture(client: TestClient):
    app.dependency_overrides[get_admin_user] = lambda: True
    limiter.enabled = False
    yield client
    limiter.enabled = True
    app.dependency_overrides.pop(get_admin_user, None)


def test_admin_endpoints(admin: TestClient, session: Session, monkeypatch):
    started = []
    monkeypatch.setattr(imslp, "sync_catalogue", lambda engine, restart: started.append(restart))
    assert admin.post("/imslp/start?restart=true").status_code == 200
    assert started == [True]
    with imslp._running:
        assert admin.post("/imslp/start").status_code == 409
        assert admin.post("/imslp/progress").json()["running"] is True
        assert admin.post("/imslp/empty").status_code == 409

    imslp.save_state(session, {"status": "running", "start": 3000, "works": 10, "error": ""})
    assert admin.post("/imslp/progress").json()["start"] == 3000
    assert admin.post("/imslp/cancel").status_code == 200  # stale "running": marked cancelled
    session.expire_all()
    assert imslp.load_state(session)["status"] == "cancelled"
    assert admin.post("/imslp/cancel").status_code == 200

    session.add(IMSLP(title="T", composer="C", permlink="p"))
    session.commit()
    assert admin.get("/imslp/stats").json() == {"total_works": 1, "total_composers": 1}
    assert admin.post("/imslp/empty").status_code == 200
    session.expire_all()
    assert session.exec(select(IMSLP)).all() == []
    assert session.get(Setting, imslp.STATE_KEY) is None
    assert admin.post("/imslp/empty").status_code == 200


def _add_work(session: Session, title: str, composer: str, **kw) -> IMSLP:
    values = {"title": title, "composer": composer, "permlink": f"p/{title}", **kw}
    values["search_text"] = imslp.normalize(" ".join([title, composer, kw.get("key", "")]))
    entry = IMSLP(**values)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def test_search(admin: TestClient, session: Session, test_scores):
    nocturne = _add_work(
        session, "Nocturnes, Op.9", "Chopin, Frédéric", instrumentation="piano",
        period=Period.Romantic, key="B-flat minor",
    )  # fmt: skip
    _add_work(session, "Nocturne", "Field, John", instrumentation="piano", period=Period.Romantic)
    _add_work(session, "Nocturnes (arr. guitar)", "Chopin, Frédéric", instrumentation="guitar")
    mine = test_scores.scores[0]
    mine.imslp_id = nocturne.id
    session.add(mine)
    session.commit()

    def search(**params):
        return admin.get("/imslp/search", params=params).json()

    found = search(q="frederic CHOPIN nocturne")
    assert found["total"] == 2
    assert [r["title"] for r in found["results"]] == ["Nocturnes, Op.9", "Nocturnes (arr. guitar)"]
    assert [r["in_library"] for r in found["results"]] == [True, False]
    assert search(q="nocturne", instrument="Piano")["total"] == 2
    assert search(q="nocturne", period="Romantic")["total"] == 2
    assert search(q="b flat minor")["results"][0]["id"] == nocturne.id
    page = search(q="nocturne", limit=1, offset=1)
    assert (page["total"], len(page["results"])) == (3, 1)
    assert search(q="  ;; ") == {"total": 0, "results": []}
    assert search(q="debussy")["total"] == 0
    assert admin.get("/imslp/search", params={"q": "x", "limit": 500}).status_code == 422


def test_get_by_ids(admin: TestClient, session: Session):
    a = _add_work(session, "T1", "C1")
    b = _add_work(session, "T2", "C2")
    data = admin.get("/imslp/scores_by_ids", params={"score_ids": f"[{a.id}, {b.id}]"}).json()
    assert [d["title"] for d in data] == ["T1", "T2"]


@pytest.mark.parametrize(
    "score_ids",
    ["not-json", '{"a": 1}', '["x"]', "[true]", "[" + ",".join(["1"] * 501) + "]"],
)
def test_get_by_ids_rejects_invalid_input(admin: TestClient, score_ids):
    response = admin.get("/imslp/scores_by_ids", params={"score_ids": score_ids})
    assert response.status_code == 422


def test_sync_checks_doubtful_list_entries_by_title(session: Session):
    """Works without a page id, or sharing one, are looked up by their title."""
    no_id = {**_item(0, "Etude"), "intvals": {"composer": "Chopin, Frédéric", "worktitle": "Etude"}}
    old_spelling = _item(31, "Ballade", "Chopin, Fryderyk")
    gone = {**_item(0, "Gone"), "intvals": {}}
    lower = {**_item(0, "x"), "id": "lower case title", "intvals": {}}
    page = [_item(31, "Ballade"), old_spelling, _item(31, "Wrong id"), no_id, gone, lower]
    wiki = {
        "Ballade (Chopin, Frédéric)": 31,
        "Ballade (Chopin, Fryderyk)": "Ballade (Chopin, Frédéric)",  # a redirect: dropped
        "Wrong id (Chopin, Frédéric)": 32,
        "Etude (Chopin, Frédéric)": 33,
        "Lower case title": 34,
    }
    fake = FakeImslp([_list_page(page, more=False)], wiki=wiki)
    imslp.sync_catalogue(_engine(session), restart=True, client=fake)  # type: ignore[arg-type]

    session.expire_all()
    rows = {r.pageid: r for r in session.exec(select(IMSLP))}
    assert {p: r.title for p, r in rows.items()} == {
        31: "Ballade",
        32: "Wrong id",
        33: "Etude",
        34: "Ballade No.2",  # no list title: the page's own
    }
    assert rows[31].composer == "Chopin, Frédéric"
    assert imslp.load_state(session)["works"] == 4
    # Everything came with the title lookup: no extra page-id request.
    assert [p and ("titles" in p) for _, p in fake.calls] == [None, True]


def test_parse_work_info_messy_fields():
    wikitext = """*****WORK INFO*****
|Key={{Tons}} (together with {{LinkWork|13 Preludes|Op.32|Rachmaninoff|Sergei|0}})
 |Movements Header=10 preludes
|Number of Movements/Sections=10 preludes:
:1. Largo ({{Key|f#}})
:2. Maestoso ({{K|Bb}}) in C{{Sharp}}
{{#subitem:id=x|level=1|title=Presto ({{K|c}})}}
{{#subitem:id=y}}
|Instrumentation=Orchestra &mdash; :2 flutes &amp; strings;<br>, voice |Tags=preludes ; org
|Dedication={{LinkDed|Alexander|Siloti}} {{EN}} {{Other|a}} {{WC|123|Paris}}
| *****COMMENTS*****"""
    info = imslp.parse_work_info(wikitext)
    assert info["Key"] == "Various (together with 13 Preludes, Op.32)"
    assert info["Movements Header"] == "10 preludes"
    assert info["Number of Movements/Sections"] == (
        "10 preludes: 1. Largo (F-sharp minor), 2. Maestoso (B-flat major) in C♯, Presto (C minor)"
    )
    assert info["Instrumentation"] == "Orchestra — :2 flutes & strings; voice"
    assert info["Tags"] == "preludes ; org"
    assert info["Dedication"] == "Alexander Siloti a Paris"
    assert imslp.clean_wiki("{{K|H}}") == "H"
    row = imslp.build_row(_item(1, "Preludes"), wikitext)
    assert row["key"] == "Various" and row["genre"] == "Preludes"
