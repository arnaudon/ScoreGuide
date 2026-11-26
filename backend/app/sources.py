"""Keep an AI-written description's links honest.

The completion agent may cite sources, but a model can invent plausible URLs.
:func:`found_urls` collects every URL the agent's web searches actually
returned, and :func:`keep_found_sources` drops any link not among them (a list
item citing an unknown URL is removed whole; a section left empty loses its
heading).
"""

import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import unquote

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
    for line in text.splitlines():
        urls = [_clean(u) for u in URL_RE.findall(line)]
        unknown = [u for u in urls if not is_found(u, seen)]
        if unknown and line.lstrip().startswith("- "):
            continue
        for url in unknown:
            line = line.replace(url, "").rstrip(" :—-")
        lines.append(line)
    # Drop headings whose section ended up empty.
    kept: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            rest = next((n for n in lines[i + 1 :] if n.strip()), "")
            if not rest or rest.startswith("## "):
                continue
        kept.append(line)
    return "\n".join(kept).strip()
