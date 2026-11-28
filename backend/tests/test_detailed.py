"""Detailed descriptions: the preference, the page reader and its safety checks."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelRequest, ToolReturnPart

from app import agent, sources
from app.rate_limit import limiter
from shared.scores import Score

WIKI = "https://en.wikipedia.org/wiki/Gymnop%C3%A9dies"
PAGE = (
    "<html><head><style>x{}</style><script>evil()</script></head><body><nav>menu</nav>"
    "<h1>Gymnopédies</h1><p>Composed   in 1888.</p></body></html>"
)


@pytest.fixture(autouse=True)
def _no_rate_limit():
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture
def public(monkeypatch):
    """Every host counts as public (no DNS in tests)."""
    monkeypatch.setattr(sources, "_is_public", AsyncMock(return_value=True))


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_account_toggles_the_preference(client: TestClient):
    assert client.get("/user").json()["detailed_descriptions"] is False
    assert client.put("/user", json={"detailed_descriptions": True}).json()["detailed_descriptions"]
    assert client.put("/user", json={"instrument": "piano"}).json()["detailed_descriptions"]
    assert not client.put("/user", json={"detailed_descriptions": False}).json()[
        "detailed_descriptions"
    ]


def test_html_to_text_keeps_visible_text():
    assert sources.html_to_text(PAGE) == "Gymnopédies\nComposed in 1888."


@pytest.mark.asyncio
async def test_is_public():
    assert await sources._is_public("8.8.8.8")
    assert not await sources._is_public("127.0.0.1")
    assert not await sources._is_public("10.0.0.5")
    assert not await sources._is_public("no-such-host.invalid")


@pytest.mark.asyncio
async def test_fetch_follows_a_redirect_and_cuts(public):
    def handler(request):
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return httpx.Response(200, html=PAGE)

    async with _client(handler) as client:
        text = await sources.fetch_page_text("https://example.org/old", 11, client)
    assert text == "Gymnopédies"


@pytest.mark.asyncio
async def test_fetch_plain_text_and_size_cap(public, monkeypatch):
    monkeypatch.setattr(sources, "PAGE_MAX_BYTES", 5)
    async with _client(lambda r: httpx.Response(200, text="abcdefghij")) as client:
        assert await sources.fetch_page_text("https://example.org/t", 100, client) == ("abcdefghij")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "response", "reason"),
    [
        ("ftp://example.org/x", None, "not an http"),
        ("https://example.org/x", httpx.Response(404), "HTTP 404"),
        (
            "https://example.org/x",
            httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"}),
            "not a web page",
        ),
        (
            "https://example.org/x",
            httpx.Response(302, headers={"location": "/x"}),
            "too many redirects",
        ),
    ],
)
async def test_fetch_refusals(public, url, response, reason):
    async with _client(lambda r: response) as client:
        with pytest.raises(ValueError, match=reason):
            await sources.fetch_page_text(url, 100, client)


@pytest.mark.asyncio
async def test_fetch_refuses_private_hosts(monkeypatch):
    monkeypatch.setattr(sources, "_is_public", AsyncMock(return_value=False))
    async with _client(lambda r: httpx.Response(200, html=PAGE)) as client:
        with pytest.raises(ValueError, match="host not allowed"):
            await sources.fetch_page_text("https://example.org/x", 100, client)


def _ctx(*urls, deps=None):
    part = ToolReturnPart(tool_name="search", content=[{"href": u} for u in urls], tool_call_id="1")
    return SimpleNamespace(
        messages=[ModelRequest(parts=[part])], deps=deps or agent.CompleteDeps(effort="detailed")
    )


@pytest.mark.asyncio
async def test_read_page_only_reads_found_pages_up_to_the_limit(monkeypatch):
    fetch = AsyncMock(return_value="Composed in 1888.")
    monkeypatch.setattr(sources, "fetch_page_text", fetch)
    monkeypatch.setattr(agent.config, "DETAILED_MAX_PAGES", 1)
    read_page = agent.read_page
    ctx = _ctx(WIKI, "https://example.org/b")

    assert (await read_page(ctx, "https://invented.example")).startswith("Refused: only")
    assert await read_page(ctx, WIKI) == "Composed in 1888."
    assert await read_page(ctx, WIKI) == "Composed in 1888."  # same page again is fine
    assert "already read 1 pages" in await read_page(ctx, "https://example.org/b")
    assert fetch.await_count == 2


@pytest.mark.asyncio
async def test_read_page_reports_failures(monkeypatch):
    monkeypatch.setattr(sources, "fetch_page_text", AsyncMock(side_effect=ValueError("HTTP 500")))
    read_page = agent.read_page
    assert await read_page(_ctx(WIKI), WIKI) == "Could not read the page: HTTP 500"
    monkeypatch.setattr(sources, "fetch_page_text", AsyncMock(return_value=""))
    assert await read_page(_ctx(WIKI), WIKI) == "(empty page)"


@pytest.mark.asyncio
@pytest.mark.parametrize("effort", ["quick", "standard", "detailed"])
async def test_effort_sets_tools_brief_and_thinking(effort):
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    seen = {}

    def answer(_messages, info: AgentInfo):
        seen["tools"] = [t.name for t in info.function_tools]
        seen["instructions"] = info.instructions or ""
        seen["settings"] = info.model_settings or {}
        args = {"title": "t", "composer": "c"} | dict.fromkeys(agent.DESCRIPTION_FIELDS, "x")
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])

    await agent.run_complete_agent(
        Score(title="t", composer="c"), model=FunctionModel(answer), effort=effort
    )
    assert ("read_page" in seen["tools"]) is (effort == "detailed")
    assert ("DETAILED MODE" in seen["instructions"]) is (effort == "detailed")
    assert ("QUICK MODE" in seen["instructions"]) is (effort == "quick")
    assert "duckduckgo_search" in seen["tools"]
    assert (seen["settings"].get("openai_reasoning_effort") == "none") is (effort == "quick")


@pytest.mark.asyncio
@pytest.mark.parametrize(("effort", "rounds"), list(agent.SEARCH_ROUNDS.items()))
async def test_search_is_withdrawn_after_its_rounds(monkeypatch, effort, rounds):
    """Each step may search (several at once); after the effort's rounds the
    tool goes away and the agent has to answer."""
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    queries = []

    async def fake_search(query):
        queries.append(query)
        return [{"title": "t", "href": "https://example.org", "body": "b"}]

    monkeypatch.setattr(agent, "_ddg", fake_search)
    offered = []

    def answer(_messages, info: AgentInfo):
        tools = [t.name for t in info.function_tools]
        offered.append("duckduckgo_search" in tools)
        if "duckduckgo_search" in tools:
            return ModelResponse(
                parts=[ToolCallPart("duckduckgo_search", {"query": f"q{i}"}) for i in range(2)]
            )
        args = {"title": "t", "composer": "c"} | dict.fromkeys(agent.DESCRIPTION_FIELDS, "x")
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])

    await agent.run_complete_agent(
        Score(title="t", composer="c"), model=FunctionModel(answer), effort=effort
    )
    assert offered == [True] * rounds + [False]
    assert len(queries) == 2 * rounds


@pytest.mark.asyncio
async def test_a_failed_search_returns_nothing_instead_of_failing_the_run(monkeypatch):
    """ddgs raises 'No results found': the agent gets an empty list and goes on."""
    from ddgs.exceptions import DDGSException

    async def no_results(_query):
        raise DDGSException("No results found.")

    monkeypatch.setattr(agent, "_ddg", no_results)
    ctx = MagicMock(deps=agent.CompleteDeps(), run_step=1)
    assert await agent.duckduckgo_search(ctx, "obscure piece") == []
    assert ctx.deps.search_steps == {1}
