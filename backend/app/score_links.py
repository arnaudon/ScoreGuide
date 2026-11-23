"""Attach the library scores an assistant answer talks about, so the UI can link them.

Smaller models often name a piece ("la Sonate K. 545") or even write its id in
the text without filling ``score_id`` / ``score_ids``. This keeps only ids
that exist in the user's library and, when the model gave none, finds the
scores the answer mentions by catalogue number (BWV 846, K. 545, Op. 28
No. 4: language-independent) or by full title, or a library id written as
the answer's only number.
"""

import re
import unicodedata

from shared.responses import Response
from shared.scores import Score, Scores

MAX_LINKED = 20
# Catalogues tied to one composer: a number alone identifies the piece.
_OWN_CATALOGUES = {"bwv", "k", "hob", "rv", "hwv", "d", "woo", "sz", "l"}
_CATALOGUE = re.compile(
    r"\b(bwv|kv|k|op|opus|hob|rv|hwv|d|woo|sz|l)\s*(\d+[a-z]?)"
    r"(?:\s*(?:no|nr|n|num)\s*(\d+))?\b"
)


def normalize(text: str) -> str:
    """Lowercase, accents and punctuation removed, single spaces."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def catalogue_numbers(text: str) -> set[tuple[str, str, str | None]]:
    """(catalogue, number, sub-number) found in already-normalized text."""
    found = set()
    for prefix, number, sub in _CATALOGUE.findall(text):
        prefix = {"kv": "k", "opus": "op"}.get(prefix, prefix)
        found.add((prefix, number, sub or None))
    return found


def _surname(score: Score) -> str:
    words = normalize(score.composer).split()
    # "Mozart, Wolfgang Amadeus" or "Wolfgang Amadeus Mozart".
    if "," in score.composer:
        return normalize(score.composer.split(",")[0]).split()[-1] if words else ""
    return words[-1] if words else ""


def _mentioned(score: Score, text: str, numbers: set[tuple[str, str, str | None]]) -> bool:
    title = normalize(score.title)
    if len(title) >= 8 and f" {title} " in f" {text} ":
        return True
    surname = _surname(score)
    for prefix, number, sub in catalogue_numbers(title):
        for p, n, s in numbers:
            if (p, n) != (prefix, number) or (sub and s and sub != s):
                continue
            if prefix in _OWN_CATALOGUES or (surname and f" {surname} " in f" {text} "):
                return True
    return False


def link_scores(response: Response, scores: Scores) -> Response:
    """The response with valid ``score_id``/``score_ids``, found from the text if missing."""
    library = {s.id: s for s in scores.scores if s.id is not None}
    score_id = response.score_id if response.score_id in library else None
    score_ids = [i for i in (response.score_ids or []) if i in library][:MAX_LINKED]
    if score_id is None and not score_ids:
        text = normalize(response.response)
        numbers = catalogue_numbers(text)
        found = [i for i, s in library.items() if _mentioned(s, text, numbers)][:MAX_LINKED]
        if not found:
            # "Here is the score: 17" — the model wrote the id instead of setting it.
            # Only when it is the answer's one and only number.
            integers = re.findall(r"\b\d+\b", text)
            if len(integers) == 1 and int(integers[0]) in library:
                found = [int(integers[0])]
        if len(found) == 1:
            score_id = found[0]
        elif found:
            score_ids = found
    return response.model_copy(update={"score_id": score_id, "score_ids": score_ids or None})
