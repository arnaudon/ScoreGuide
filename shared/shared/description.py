"""Score descriptions: plain text, one heading, paragraph or list item per line."""

import re

# The section headings the completion prompt asks for (English and French).
HEADINGS = (
    "History",
    "Playing it",
    "Did you know?",
    "Sources",
    "Histoire",
    "Conseils de jeu",
    "Le saviez-vous ?",
)
_HEADING = re.compile(
    r"\s*##\s*(" + "|".join(re.escape(h) for h in sorted(HEADINGS, key=len, reverse=True)) + r")"
)
_ANY_HEADING = re.compile(r"\s+(?=## )")
_ITEM = re.compile(r"\s+-\s+")


def reflow(text: str) -> str:
    """Put a sectioned description written on one line back on separate lines.

    Some models write the whole text on one line ("## History Beethoven… ##
    Playing it - Voice… - Pedal…"): the card then shows a wall of text. Known
    headings and any other "## " start a line, and a section whose body is a
    list ("- …") gets one item per line. Text that already has line breaks,
    or no headings, is left alone.
    """
    if "\n" in text or "## " not in text:
        return text
    text = _HEADING.sub(lambda m: f"\n\n## {m.group(1)}\n", text)
    text = _ANY_HEADING.sub("\n\n", text).strip()
    lines: list[str] = []
    for line in text.split("\n"):
        body = line.strip()
        if body.startswith("- "):
            lines.extend(f"- {item}" for item in _ITEM.split(body[2:]) if item.strip())
        else:
            lines.append(body)
    return "\n".join(lines)
