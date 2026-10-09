"""Deterministic table-of-contents extraction for score PDFs.

Finds where each piece / movement starts in a (possibly multi-piece) PDF and
crops the first system of each as an incipit image:

1. The PDF's own outline (bookmarks), when it is a real one (scanners often
   add one junk bookmark per page, which is ignored).
2. Otherwise, per page: staff systems are located on a low-res render, and a
   system opens a section when the text above it is a heading — read from the
   text layer on engraved PDFs, or with Tesseract OCR on scans.

Pages without staves (title pages, prefaces) are skipped, and the first
system with music always opens a section.
"""

import io
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field

import numpy as np
import pypdfium2 as pdfium
from PIL import Image
from pypdf import PdfReader

RENDER_DPI = 100
# Darkness threshold (0-255 grayscale) below which a pixel counts as ink.
INK = 140
# Fraction of the page width a pixel row must be inked to be a staff line.
STAFF_LINE_FILL = 0.35

TEMPO_RE = re.compile(
    r"\b(allegr\w*|adagi\w*|andant\w*|prest\w*|larg\w*|lento|moderato|vivace|grave|"
    r"menuett?o?|minuet\w*|menuet|scherz\w*|rond\w*|finale|tempo di \w+|maestoso|"
    r"sarabande|courante|gigue|allemande|gavotte|bourr[ée]e|air|aria|polonaise)\b",
    re.IGNORECASE,
)
# Plain tempo words: unlike dance/form names they also mark tempo changes
# inside a movement, so on their own they need more evidence (see _find_starts).
TEMPO_ONLY_RE = re.compile(
    r"\b(allegr\w*|adagi\w*|andant\w*|prest\w*|larg\w*|lento|moderato|vivace|grave|"
    r"maestoso|tempo di \w+)\b",
    re.IGNORECASE,
)
PIECE_RE = re.compile(
    r"\b(sonat\w*|partita|suite|pr[ée]lud\w*|pr[äa]ludium|fug\w*|invention\w*|[ée]tude\w*|"
    r"nocturne|mazurka|waltz|valse|impromptu|variat\w*|var\.\s*\d+|movement|satz|ballade|"
    r"fantasi\w*|toccata|concerto|op\.\s*\d+|no\.\s*\d+|nr\.\s*\d+|bwv\s*\d+|k\.\s*\d+)",
    re.IGNORECASE,
)
# Dynamics / expression marks that are lettered but never headings.
NOT_HEADING_RE = re.compile(
    r"^(p+|f+|m[pf]|s?fz?p?|rf|cresc\.?|dim\.?|decresc\.?|dolce|legato|staccato|"
    r"rit\.?|ritard\.?|a tempo|sempre|poco|pi[uù]|ped\.?|\d+)$",
    re.IGNORECASE,
)


@dataclass
class TextLine:
    """A line of text from the PDF text layer, in page-fraction coordinates."""

    text: str
    top: float  # 0 = top of page
    height: float  # glyph box height in PDF points (≈ font size)


@dataclass
class Staff:
    """A detected 5-line staff, in rendered-image pixel coordinates."""

    top: int
    bottom: int
    left: int
    right: int


@dataclass
class System:
    """A group of staves played together (e.g. the two staves of a piano part)."""

    staves: list[Staff]

    @property
    def top(self) -> int:
        return self.staves[0].top

    @property
    def bottom(self) -> int:
        return self.staves[-1].bottom

    @property
    def left(self) -> int:
        return min(s.left for s in self.staves)

    @property
    def right(self) -> int:
        return max(s.right for s in self.staves)


@dataclass
class DetectedSection:
    """A section start found in the PDF."""

    title: str
    page: int  # 1-based
    source: str  # "outline" | "text" | "ocr" | "layout"
    incipit_png: bytes | None = field(default=None, repr=False)


# --- staff detection -------------------------------------------------------


def _row_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Return (start, end) inclusive index runs where ``mask`` is True."""
    runs: list[tuple[int, int]] = []
    start = None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(mask) - 1))
    return runs


def find_staves(gray: np.ndarray) -> list[Staff]:
    """Locate 5-line staves via the horizontal ink projection."""
    ink = gray < INK
    _, w = ink.shape
    fill = ink.sum(axis=1) / w
    lines = [((a + b) / 2, a, b) for a, b in _row_runs(fill > STAFF_LINE_FILL)]

    staves: list[Staff] = []
    i = 0
    while i + 4 < len(lines):
        group = lines[i : i + 5]
        gaps = np.diff([c for c, _, _ in group])
        # Five evenly spaced lines → a staff.
        if gaps.min() > 2 and gaps.max() <= gaps.min() * 1.5 + 1:
            top, bottom = int(group[0][1]), int(group[-1][2])
            row_xs = np.flatnonzero(ink[int(group[2][0])])
            left = int(row_xs.min()) if row_xs.size else 0
            right = int(row_xs.max()) if row_xs.size else w - 1
            staves.append(Staff(top, bottom, left, right))
            i += 5
        else:
            i += 1
    return staves


def _joined(ink: np.ndarray, a: Staff, b: Staff) -> bool:
    """True when a vertical line at the left edge connects staff ``a`` to ``b``.

    Staves of one system (e.g. a piano grand staff) share a system barline
    and brace on the left; consecutive systems don't.
    """
    if b.top <= a.bottom + 1:
        return True
    left = min(a.left, b.left)
    x0, x1 = max(0, left - 6), min(ink.shape[1], left + 10)
    gap = ink[a.bottom + 1 : b.top, x0:x1]
    # Best single column's coverage of the gap.
    return bool(gap.size) and float(gap.mean(axis=0).max()) > 0.85


def group_systems(staves: list[Staff], ink: np.ndarray | None = None) -> list[System]:
    """Group staves into systems, using the left system barline/brace."""
    if not staves:
        return []
    if ink is None:
        return [System([s]) for s in staves]
    systems = [System([staves[0]])]
    for prev, staff in zip(staves, staves[1:], strict=False):
        if _joined(ink, prev, staff):
            systems[-1].staves.append(staff)
        else:
            systems.append(System([staff]))
    return systems


def page_systems(gray: np.ndarray) -> list[System]:
    """Detect the systems on a rendered page."""
    return group_systems(find_staves(gray), gray < INK)


def ends_with_double_bar(ink: np.ndarray, system: System) -> bool:
    """Does the system end with a double or final barline (‖ or thin+thick)?

    A movement or piece ends with one; an ordinary system ends with a single
    thin barline. Looks at full-height ink columns in the last few pixels.
    """
    w = ink.shape[1]
    x0, x1 = max(0, system.right - 10), min(w, system.right + 4)
    cov = ink[system.top : system.bottom + 1, x0:x1].mean(axis=0)
    runs = _row_runs(cov > 0.8)
    return len(runs) >= 2 or any(b - a + 1 >= 3 for a, b in runs)


def crop_incipit(gray: np.ndarray, system: System) -> bytes:
    """Crop one system (with room for ledger lines / tempo marks) as PNG."""
    h, w = gray.shape
    staff_h = system.staves[0].bottom - system.staves[0].top
    top = max(0, system.top - staff_h)
    bottom = min(h, system.bottom + staff_h)
    left = max(0, system.left - 4)
    right = min(w, system.right + 4)
    buf = io.BytesIO()
    Image.fromarray(gray[top:bottom, left:right]).save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# --- text layer ------------------------------------------------------------


def text_lines(page: pdfium.PdfPage) -> list[TextLine]:
    """Lettered text lines of a page (music-font glyphs filtered out)."""
    _, height = page.get_size()
    tp = page.get_textpage()
    out: list[TextLine] = []
    for r in range(tp.count_rects()):
        left, bottom, right, top = tp.get_rect(r)
        text = " ".join(tp.get_text_bounded(left, bottom, right, top).split())
        letters = re.findall(r"[^\W\d_]", text)
        printable = re.findall(r"[\w .,:;'()\-–—&/°«»\"]", text)
        if len(letters) < 3 or len(printable) < 0.8 * len(text):
            continue
        out.append(TextLine(text=text, top=1 - top / height, height=top - bottom))
    return out


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def heading_for(lines: list[TextLine], header_bottom: float) -> str | None:
    """Build a section title from the heading-area lines of a page, if any.

    ``header_bottom`` is the page-fraction y of the first system's top: text
    above it is where titles and the opening tempo marking live.
    """
    head = [ln for ln in lines if ln.top < header_bottom and not NOT_HEADING_RE.match(ln.text)]
    titled = [ln for ln in head if PIECE_RE.search(ln.text)]
    tempo = [ln for ln in head if TEMPO_RE.search(ln.text) and len(ln.text) < 40]
    if not titled and not tempo:
        return None
    parts: list[str] = []
    if titled:
        parts.append(max(titled, key=lambda ln: ln.height).text)
    if tempo:
        t = min(tempo, key=lambda ln: ln.top).text.rstrip(".")
        if not parts or _norm(t) not in _norm(parts[0]):
            parts.append(t)
    return " — ".join(parts)


# --- OCR of the heading area above each system ----------------------------

# Command used to run Tesseract; overridable so dev can use a container.
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")
OCR_LANGS = os.getenv("TOC_OCR_LANGS", "eng+deu+fra+ita")
OCR_UPSCALE = 2
OCR_MIN_CONF = 55
# A page with this many OCR headings is an index/contents page (see _find_starts).
INDEX_PAGE_MIN_HEADINGS = 4
# A tempo-only heading must start within this fraction of the system width.
TEMPO_START_FRACTION = 0.3
ROMAN_RE = re.compile(r"^(?=[IVXL])(X{0,3})(IX|IV|V?I{0,3})\.?$")
TOKEN_RE = re.compile(r"^[^\W_][\w'’.,()\-]*$")


def _heading_band(system: System, prev_bottom: int) -> tuple[int, int]:
    """Vertical pixel range above a system where its heading would be printed."""
    staff_h = system.staves[0].bottom - system.staves[0].top
    top = max(prev_bottom + 2, system.top - int(2.5 * staff_h))
    return top, max(top, system.top - int(0.15 * staff_h))


@dataclass
class OcrText:
    """OCR'd text above a system and where it starts horizontally (pixels)."""

    text: str = ""
    left: int = 0


def ocr_headings(gray: np.ndarray, systems: list[System]) -> list[OcrText]:
    """OCR the band above every system of a page in one Tesseract call.

    The bands are stacked into a single image (one process per page instead
    of per system) and the recognised words are mapped back by y position.
    Returns one entry per system (empty text when nothing legible).
    """
    if not systems:
        return []
    _, w = gray.shape
    strips: list[np.ndarray] = []
    offsets: list[tuple[int, int]] = []
    y = prev = 0
    spacer = np.full((20, w), 255, dtype=np.uint8)
    for s in systems:
        top, bottom = _heading_band(s, prev)
        prev = s.bottom
        strip = gray[top:bottom] if bottom > top else np.full((1, w), 255, dtype=np.uint8)
        offsets.append((y, y + strip.shape[0]))
        strips += [strip, spacer]
        y += strip.shape[0] + spacer.shape[0]
    img = Image.fromarray(np.vstack(strips))
    img = img.resize((img.width * OCR_UPSCALE, img.height * OCR_UPSCALE), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    try:
        out = subprocess.run(
            [*shlex.split(TESSERACT_CMD), "stdin", "stdout", "--psm", "11", "-l", OCR_LANGS, "tsv"],
            input=buf.getvalue(),
            capture_output=True,
            timeout=60,
            check=True,
            # One thread at the lowest priority: TOC generation is a background
            # job and must never compete with serving the site.
            env={**os.environ, "OMP_THREAD_LIMIT": "1"},
            preexec_fn=lambda: os.nice(19),
        ).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - no tesseract
        return [OcrText() for _ in systems]

    words: list[list[tuple[int, int, str]]] = [[] for _ in systems]
    for row in out.splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) < 12 or not cols[11].strip() or float(cols[10]) < OCR_MIN_CONF:
            continue
        left, top = int(cols[6]) // OCR_UPSCALE, int(cols[7]) // OCR_UPSCALE
        for k, (a, b) in enumerate(offsets):
            if a <= top < b:
                words[k].append((top // 8, left, cols[11].strip()))
                break
    return [
        OcrText(" ".join(t for _, _, t in sorted(ws)), min((x for _, x, _ in ws), default=0))
        for ws in words
    ]


def _known(word: str) -> bool:
    return bool(TEMPO_RE.fullmatch(word) or PIECE_RE.fullmatch(word))


def _noise(tok: str) -> bool:
    """OCR debris: punctuation runs, single letters, letters mixed with digits."""
    if not TOKEN_RE.match(tok):
        return True
    core = tok.strip(".,()'’")
    if len(core) == 1 and not core.isdigit() and not ROMAN_RE.match(core):
        return True
    mixed = re.search(r"[^\W\d_]", core) and re.search(r"\d", core)
    return bool(mixed and not PIECE_RE.fullmatch(core))


def clean_title(text: str) -> str:
    """Turn OCR'd heading text into a readable title.

    Re-joins words OCR split in two ("Anda nte"), drops debris tokens and
    stray numbers (fingerings, bar numbers) at either end.
    """
    merged: list[str] = []
    for tok in text.split():
        joined = merged[-1] + tok if merged else ""
        if merged and not _known(merged[-1]) and not _known(tok) and _known(joined):
            merged[-1] = joined
        else:
            merged.append(tok)
    kept = [t for t in merged if not _noise(t)]
    while kept and kept[0].rstrip(".").isdigit():
        kept.pop(0)
    while len(kept) > 1 and kept[-1].rstrip(".").isdigit() and not PIECE_RE.search(kept[-2]):
        kept.pop()
    return " ".join(kept).strip(" .,")


def is_heading(text: str) -> bool:
    """Does OCR'd text above a system look like a piece/movement heading?

    Only real heading vocabulary counts: bare numbers or Roman numerals are
    too often OCR debris from stems, barlines and fingerings.
    """
    return bool(text and (PIECE_RE.search(text) or TEMPO_RE.search(text)))


def is_tempo_only(text: str) -> bool:
    """A heading that is just a tempo word (no piece/dance/form name)."""
    stripped = TEMPO_ONLY_RE.sub("", text)
    return bool(TEMPO_ONLY_RE.search(text)) and not (
        PIECE_RE.search(stripped) or TEMPO_RE.search(stripped)
    )


# --- outline ---------------------------------------------------------------

JUNK_TITLE_RE = re.compile(
    r"(\.(tiff?|jpe?g|png)$|_page_\d+|[-_ ]\d{2,4}$|^page \d+$)", re.IGNORECASE
)


def _meaningful_outline(sections: list[DetectedSection], n_pages: int) -> bool:
    """Reject scanner-made outlines: one bookmark per page, or file-name titles."""
    if not sections:
        return False
    junk = sum(1 for s in sections if JUNK_TITLE_RE.search(s.title))
    if junk > len(sections) / 2:
        return False
    return not (n_pages > 3 and len(sections) >= 0.9 * n_pages)


def outline_sections(data: bytes) -> list[DetectedSection]:
    """Flatten the PDF outline (bookmarks) into sections, in page order."""
    reader = PdfReader(io.BytesIO(data))
    out: list[DetectedSection] = []

    def walk(items, depth: int) -> None:
        for item in items:
            if isinstance(item, list):
                # Only one level of nesting: pieces → movements is plenty for
                # a navigation list; deeper levels are usually noise.
                if depth < 1:
                    walk(item, depth + 1)
                continue
            try:
                index = reader.get_destination_page_number(item)
            except Exception:  # pragma: no cover - malformed destinations
                continue
            if index is None:  # pragma: no cover - destination without a page
                continue
            title = " ".join(str(item.title or "").split())
            if title:
                out.append(DetectedSection(title=title, page=index + 1, source="outline"))

    try:
        walk(reader.outline, 0)
    except Exception:  # pragma: no cover - malformed outlines
        return []
    out.sort(key=lambda s: s.page)
    return out if _meaningful_outline(out, len(reader.pages)) else []


# --- main entry ------------------------------------------------------------


def _render_gray(page: pdfium.PdfPage) -> np.ndarray:
    bitmap = page.render(scale=RENDER_DPI / 72, grayscale=True)
    return np.asarray(bitmap.to_pil().convert("L"))


@dataclass
class _PageInfo:
    number: int  # 1-based
    shape: tuple[int, ...]
    systems: list[System]
    lines: list[TextLine]
    ocr: list[OcrText] = field(default_factory=list)  # heading text above each system
    # Per system: does it end with a double/final barline?
    final_bar: list[bool] = field(default_factory=list)


def _tempo_opens(ocr: OcrText, system: System, prev_final: bool) -> bool:
    """Can a bare tempo word above ``system`` open a new movement?

    Only when the previous system closed with a double/final barline and the
    word sits above the start of this system: tempo changes inside a
    movement are printed over a later bar, usually without a final barline.
    """
    return prev_final and ocr.left - system.left < TEMPO_START_FRACTION * (
        system.right - system.left
    )


def _find_starts(pages: list[_PageInfo]) -> list[tuple[_PageInfo, int, str, str]]:
    """Pick (page, system index, title, source) for every section start."""
    n = len(pages)
    counts: dict[str, int] = {}
    for info in pages:
        for key in {_norm(ln.text) for ln in info.lines}:
            counts[key] = counts.get(key, 0) + 1
    # Running headers / footers repeat on many pages: never headings.
    repeated = {k for k, c in counts.items() if n >= 4 and c > n * 0.4}

    starts: list[tuple[_PageInfo, int, str, str]] = []
    # Whether the previous system (in reading order) ended a piece; the very
    # first system of the document trivially follows "an end".
    prev_final = True
    for info in (p for p in pages if p.systems):
        h, _ = info.shape
        ends = info.final_bar or [False] * len(info.systems)
        lines = [ln for ln in info.lines if _norm(ln.text) not in repeated]
        title = heading_for(lines, info.systems[0].top / h)
        if title:
            starts.append((info, 0, title, "text"))
            prev_final = ends[-1]
            continue
        page_starts = []
        for j, ocr in enumerate(info.ocr):
            title = clean_title(ocr.text)
            if is_heading(title) and (
                not is_tempo_only(title) or _tempo_opens(ocr, info.systems[j], prev_final)
            ):
                page_starts.append((j, title))
            prev_final = ends[j]
        prev_final = ends[-1]
        if len(page_starts) >= INDEX_PAGE_MIN_HEADINGS:
            # A page where nearly every system has a heading is an edition's
            # index of incipits / contents page, not music to navigate to.
            continue
        for j, cleaned in page_starts:
            starts.append((info, j, cleaned, "ocr"))
        if not page_starts and not starts:
            # The first system with music always opens a section, even when
            # its heading isn't legible.
            starts.append((info, 0, "", "layout"))
    return starts


def extract_sections(data: bytes, max_pages: int = 1000) -> list[DetectedSection]:
    """Detect section starts (with incipits) in a score PDF."""
    outline = outline_sections(data)
    pdf = pdfium.PdfDocument(data)
    try:
        n = min(len(pdf), max_pages)

        if outline:
            for sec in outline:
                if sec.page <= n:
                    gray = _render_gray(pdf[sec.page - 1])
                    systems = page_systems(gray)
                    if systems:
                        sec.incipit_png = crop_incipit(gray, systems[0])
            return outline

        # Pass 1: per-page features only (rendered pages are ~1 MB each, so a
        # 600-page volume must not keep them all in memory).
        pages: list[_PageInfo] = []
        for i in range(n):
            page = pdf[i]
            gray = _render_gray(page)
            systems = page_systems(gray)
            lines = text_lines(page)
            # Scans have no text layer: read the headings with OCR instead.
            ocr = ocr_headings(gray, systems) if systems and not lines else []
            ink = gray < INK
            final_bar = [ends_with_double_bar(ink, s) for s in systems]
            pages.append(_PageInfo(i + 1, gray.shape, systems, lines, ocr, final_bar))

        # Pass 2: re-render only the pages that need an incipit crop.
        sections: list[DetectedSection] = []
        for info, sys_idx, title, source in _find_starts(pages):
            gray = _render_gray(pdf[info.number - 1])
            sections.append(
                DetectedSection(
                    title=title,
                    page=info.number,
                    source=source,
                    incipit_png=crop_incipit(gray, info.systems[sys_idx]),
                )
            )
        for k, sec in enumerate(sections, start=1):
            if not sec.title:
                sec.title = str(k)
        return sections
    finally:
        pdf.close()
