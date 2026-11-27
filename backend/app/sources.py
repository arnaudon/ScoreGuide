"""Keep an AI-written description's links honest.

The completion agent may cite sources, but a model can invent plausible URLs.
:func:`found_urls` collects every URL the agent's web searches actually
returned, and :func:`keep_found_sources` drops any link not among them (a list
item citing an unknown URL is removed whole; a section left empty loses its
heading).
"""

import asyncio
import ipaddress
import re
from collections.abc import Iterable
from html.parser import HTMLParser
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit

import httpx

URL_RE = re.compile(r"https?://[^\s<>\"']+")
_TRAILING = ".,;:!?]"


def _clean(url: str) -> str:
    """Strip trailing punctuation, keeping a ")" that closes a "(" in the URL."""
    while url and (url[-1] in _TRAILING or (url[-1] == ")" and url.count("(") < url.count(")"))):
        url = url[:-1]
    return url


def _key(url: str) -> str:
    """Compare URLs loosely: decoded, case-insensitive, no trailing slash."""
    return unquote(_clean(url)).rstrip("/").lower()


def found_urls(messages: Iterable[Any]) -> set[str]:
    """Normalized URLs that appear in the tool results of an agent run."""
    seen: set[str] = set()
    for message in messages:
        for part in getattr(message, "parts", ()):
            if getattr(part, "part_kind", None) == "tool-return":
                seen.update(_key(u) for u in URL_RE.findall(str(part.content)))
    return seen


def is_found(url: str, seen: set[str]) -> bool:
    return _key(url) in seen


def keep_found_sources(text: str, seen: set[str]) -> str:
    """Remove links from ``text`` that the searches never returned."""
    lines: list[str] = []
    removed: set[int] = set()  # positions in ``lines`` where a source line was dropped
    for line in text.splitlines():
        urls = [_clean(u) for u in URL_RE.findall(line)]
        unknown = [u for u in urls if not is_found(u, seen)]
        if unknown and line.lstrip().startswith("- "):
            removed.add(len(lines))
            continue
        for url in unknown:
            line = line.replace(url, "").rstrip(" :—-")
        lines.append(line)
    # Drop the headings of sections emptied by the removal (and only those: a
    # heading line with the text on it is kept).
    kept: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            end = next(
                (j for j in range(i + 1, len(lines)) if lines[j].startswith("## ")), len(lines)
            )
            empty = not any(n.strip() for n in lines[i + 1 : end])
            if empty and any(i < r <= end for r in removed):
                continue
        kept.append(line)
    return "\n".join(kept).strip()


# --- Reading pages (detailed descriptions) ------------------------------------

PAGE_MAX_BYTES = 2_000_000
_SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "header", "svg", "form"}
_BLOCK_TAGS = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section"}


class _TextExtractor(HTMLParser):
    """Visible text of an HTML page, one block per line."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)


async def _is_public(host: str) -> bool:
    """Whether every address ``host`` resolves to is a public one (no SSRF)."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None)
    except OSError:
        return False
    return bool(infos) and all(ipaddress.ip_address(i[4][0]).is_global for i in infos)


async def fetch_page_text(url: str, max_chars: int, client: httpx.AsyncClient) -> str:
    """The readable text of a public web page, cut to ``max_chars``.

    Follows at most 3 redirects, re-checking each host; reads at most
    ``PAGE_MAX_BYTES``; only HTML or plain text. Raises ``ValueError`` with a
    short reason the agent can read.
    """
    for _ in range(4):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("not an http(s) URL")
        if not await _is_public(parts.hostname):
            raise ValueError("host not allowed")
        async with client.stream("GET", url, follow_redirects=False) as res:
            if res.is_redirect and res.headers.get("location"):
                url = urljoin(url, res.headers["location"])
                continue
            if res.status_code != 200:
                raise ValueError(f"HTTP {res.status_code}")
            kind = res.headers.get("content-type", "")
            if "html" not in kind and "text/plain" not in kind:
                raise ValueError("not a web page")
            body = b""
            async for chunk in res.aiter_bytes():
                body += chunk
                if len(body) > PAGE_MAX_BYTES:
                    break
            text = body.decode(res.encoding or "utf-8", errors="replace")
            return (html_to_text(text) if "html" in kind else text)[:max_chars]
    raise ValueError("too many redirects")
