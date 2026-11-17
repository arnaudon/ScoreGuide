"""Deterministic table-of-contents extraction for score PDFs.

Finds where each piece / movement starts in a (possibly multi-piece) PDF and
crops the first system of each as an incipit image:

1. The PDF's own outline (bookmarks), when it is a real one (scanners often
   add one junk bookmark per page, which is ignored).
2. Otherwise, per page: staff systems are located on a low-res render, and a
   system opens a section when the text above it is a heading — read from the
   text layer on engraved PDFs, or with Tesseract OCR on scans.
3. Barlines give context: a bare tempo word only opens a movement after a
   double/final barline (tempo changes inside a movement don't), and a final
   barline (thin + thick, not a repeat) opens the next system even when its
   heading isn't legible.

Pages without staves (title pages, prefaces) and incipit index pages are
skipped, and the first system with music always opens a section.
"""

import io
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import Image
from pypdf import PdfReader

# Bump when detection improves enough that existing tables of contents are
# worth rebuilding: entries store the version that produced them, and the
# reader offers a rebuild when it is older than this.
TOC_VERSION = 1

RENDER_DPI = 100
# Darkness threshold (0-255 grayscale) below which a pixel counts as ink.
INK = 140
# Fraction of the page width a pixel row must be inked to be a staff line.
STAFF_LINE_FILL = 0.25
# Extra thresholds, as fractions of the fullest row, for dense pages.
DENSE_FILL_FRACTIONS = (0.6, 0.75)
# Minimum horizontal run (px) for ink to count as part of a staff line.
LINE_RUN_MIN = 24
# Share of the gap between two staves a left barline/brace must cover for
# them to be one system (scans break thin lines, so not 100%).
JOIN_MIN_COVERAGE = 0.7
# Share of a system's height a column must be inked to be part of a barline.
BARLINE_MIN_COVERAGE = 0.6
# Minimum width of a lone thick (final) barline, in staff spaces.
THICK_BAR_SPACES = 0.4

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
    r"\b(sonat\w*|partita|suite|pr(?:[ée]|ae|æ|ee|[äa])lud\w*|pr(?:ae|æ|[äe])ambul\w*|fug\w*|puga|invention\w*|[ée]tude\w*|"
    r"nocturne|mazurka|waltz|valse|impromptu|variat\w*|var\.(?:\s*(?:\d+|[ivxl]+\b))?|double|movement|satz|ballade|"
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


def _plain_staff(centers: list[float], i: int) -> bool:
    """Five consecutive, roughly evenly spaced lines starting at ``i``."""
    five = centers[i : i + 5]
    if len(five) < 5:
        return False
    gaps = np.diff(five)
    return bool(gaps.min() > 2 and gaps.max() <= gaps.min() * 1.5 + 1)


def _staff_with_strays(centers: list[float], i: int, spacing: float) -> int | None:
    """Index of the 5th line of a staff at ``i`` with the page's line spacing.

    Beams and slurs can add stray "lines" (rows above the fill threshold)
    inside a staff; the four other staff lines are looked for at multiples
    of the page's known spacing, skipping strays.
    """
    tol = max(1.5, 0.2 * spacing)
    last = i
    for m in range(1, 5):
        target = centers[i] + m * spacing
        hits = [
            k for k in range(last + 1, min(len(centers), i + 9)) if abs(centers[k] - target) <= tol
        ]
        if not hits:
            return None
        last = hits[0]
    return last


def _long_horizontal(ink: np.ndarray, length: int = LINE_RUN_MIN) -> np.ndarray:
    """Ink pixels that are part of a horizontal run of at least ~``length``.

    Staff lines are long horizontal runs; note heads, stems and accidentals
    are short. Filtering them out keeps the five lines distinct in the row
    projection even on dense, heavily inked scans.
    """
    h, w = ink.shape
    if w <= length:
        return ink
    padded = np.pad(ink.astype(np.int32), ((0, 0), (1, 0)))
    window = np.cumsum(padded, axis=1)
    sums = window[:, length:] - window[:, :-length]  # window starting at x
    full = np.pad((sums >= 0.9 * length).astype(np.int32), ((0, 0), (1, 0)))
    starts = np.cumsum(full, axis=1)
    x = np.arange(w)
    lo = np.clip(x - length + 1, 0, sums.shape[1])
    hi = np.clip(x + 1, 0, sums.shape[1])
    # Pixel x is covered when any full window starting in [x-length+1, x] exists.
    return ((starts[:, hi] - starts[:, lo]) > 0) & ink


def find_staves(gray: np.ndarray) -> list[Staff]:
    """Locate 5-line staves on a page.

    Two row projections are tried and the one finding more staves wins:
    all ink (robust to scans whose staff lines are broken into short
    pieces) and only long horizontal runs (keeps the lines distinct on
    dense, heavily inked pages). False staves are rare either way thanks
    to the five-evenly-spaced-lines check. On dense pages (fast passages,
    slightly skewed scans) many rows besides the staff lines pass the base
    fill threshold and the lines merge into bands, so higher thresholds
    relative to the page's fullest row are tried too.
    """
    ink = gray < INK
    _, w = ink.shape
    best: list[Staff] = []
    for fill in (ink.sum(axis=1) / w, _long_horizontal(ink).sum(axis=1) / w):
        for threshold in (STAFF_LINE_FILL, *(f * float(fill.max()) for f in DENSE_FILL_FRACTIONS)):
            staves = _staves_from_fill(ink, fill, max(threshold, STAFF_LINE_FILL))
            if len(staves) > len(best):
                best = staves
    return best


def _staves_from_fill(
    ink: np.ndarray, fill: np.ndarray, threshold: float = STAFF_LINE_FILL
) -> list[Staff]:
    """Staves from a row projection (fraction of each row that is ink)."""
    _, w = ink.shape
    runs = _row_runs(fill > threshold)
    centers = [(a + b) / 2 for a, b in runs]

    # Staff-line spacing of this page, from the cleanly detected staves.
    spacings = [
        (centers[i + 4] - centers[i]) / 4 for i in range(len(centers)) if _plain_staff(centers, i)
    ]
    spacing = float(np.median(spacings)) if spacings else 0.0

    staves: list[Staff] = []
    i = 0
    while i + 4 < len(runs):
        if _plain_staff(centers, i):
            end: int | None = i + 4
        elif spacing:
            end = _staff_with_strays(centers, i, spacing)
        else:
            end = None
        if end is None:
            i += 1
            continue
        top, bottom = runs[i][0], runs[end][1]
        row_xs = np.flatnonzero(ink[int((centers[i] + centers[end]) / 2)])
        left = int(row_xs.min()) if row_xs.size else 0
        right = int(row_xs.max()) if row_xs.size else w - 1
        staves.append(Staff(int(top), int(bottom), left, right))
        i = end + 1
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
    return bool(gap.size) and float(gap.mean(axis=0).max()) > JOIN_MIN_COVERAGE


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


def barline_kind(ink: np.ndarray, system: System) -> str:
    """Classify the barline that closes a system.

    ``"final"`` (thin + thick: a piece ends), ``"repeat"`` (thick with repeat
    dots before it: a section of a piece ends), ``"double"`` (two thin
    lines) or ``"single"`` (an ordinary barline). Uses full-height ink
    columns in the last few pixels and ink in the staff spaces just before
    them (where repeat dots sit).
    """
    w = ink.shape[1]
    x0, x1 = max(0, system.right - 10), min(w, system.right + 4)
    cov = ink[system.top : system.bottom + 1, x0:x1].mean(axis=0)
    # Scanned barlines are broken and slightly skewed: 60% of the system
    # height still rules out stems and beams, which cover one staff at most.
    runs = _row_runs(cov > BARLINE_MIN_COVERAGE)
    # Engraved PDFs render even thin barlines ~3 px wide (anti-aliasing):
    # a lone line is thick only when it is about half a staff space wide;
    # next to another line, when it is the wider of the two (thin + thick).
    widths = [b - a + 1 for a, b in runs]
    space = min((st.bottom - st.top) / 4 for st in system.staves)
    thick = any(w >= max(4, THICK_BAR_SPACES * space) for w in widths) or (
        len(widths) >= 2 and widths[-1] > widths[0]
    )
    if not runs or (len(runs) < 2 and not thick):
        return "single"
    # Repeat dots: ink in the 2nd and 3rd staff spaces, left of the barline.
    bar_x = x0 + runs[0][0]
    dots = 0
    for st in system.staves:
        space = (st.bottom - st.top) / 4
        for k in (1.5, 2.5):
            y = int(st.top + k * space)
            box = ink[y - 1 : y + 2, max(0, bar_x - int(2 * space)) : max(0, bar_x - 1)]
            # A dot is only ~2x2 px at the render resolution.
            dots += int(box.sum()) >= 3
    if dots >= max(2, len(system.staves)):
        return "repeat"
    return "final" if thick else "double"


def ends_with_double_bar(ink: np.ndarray, system: System) -> bool:
    """Does the system end with a double, final or repeat barline?"""
    return barline_kind(ink, system) != "single"


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


def heading_for(lines: list[TextLine], header_bottom: float, header_top: float = 0.0) -> str | None:
    """Build a section title from the heading-area lines of a page, if any.

    ``header_bottom`` is the page-fraction y of a system's top and
    ``header_top`` that of the top of its heading band: text in between is
    where titles and the opening tempo marking live.
    """
    head = [
        ln
        for ln in lines
        if header_top <= ln.top < header_bottom and not NOT_HEADING_RE.match(ln.text)
    ]
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
# A page with at least this many OCR headings, on at least half its systems,
# is an index/contents page (see _find_starts).
INDEX_PAGE_MIN_HEADINGS = 3
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


# Words that qualify a tempo / form heading ("Allegro ma non troppo",
# "Canone alla Quinta", "Andante con moto"): kept inside a title.
QUALIFIER_RE = re.compile(
    r"(molto|assai|ma|non|troppo|con|moto|poco|più|piu|quasi|sostenuto|cantabile|espressivo|"
    r"grazioso|giocoso|tranquillo|mosso|meno|sempre|vivo|brio|spirito|fuoco|un|e|ed|di|del|"
    r"della|alla|all[’']?|al|il|lo|la|sehr|mässig|massig|nicht|zu|schnell|langsam|lebhaft|"
    r"et|très|tres|un|peu|gai|gracieusement|tendrement|lentement|vivement|modéré|"
    r"canon[ei]?|unisono|unisuono|seconda|terza|quarta|quinta|sexta|sesta|settima|ottava|"
    r"nona|giga|fug[h]?etta|ouverture|quodlibet|delicatezza|tempo|primo)",
    re.IGNORECASE,
)
# Catalogue / opus tokens: metadata, not part of a section title on
# their own ("Kéchel Nr.545", "BWV873"); kept only right after a piece
# word ("Sonata No. 3", "Var. 2").
CATALOGUE_RE = re.compile(r"(op|no|nr|n°|bwv|k|kv|hob|d)\.?\s*[\dIVXL]", re.IGNORECASE)
# "No." / "Op." in "Sonata No. 3": the number follows as its own token.
NUMBER_PREFIX_RE = re.compile(r"(no|nr|op|n°)\.?", re.IGNORECASE)
# French character-piece names: "La Joyeuse", "Les Tendres Plaintes",
# "L'Enharmonique" (Rameau, Couperin...).
NAMED_PIECE_RE = re.compile(
    r"\b(?:L[ae]s?\s+|L[’'])[A-ZÀ-Ý][\w’'-]{3,}(?:\s+[A-ZÀ-Ýa-zà-ÿ][\w’'-]{2,}){0,2}"
)


def _core(token: str) -> str:
    return token.strip(".,;:()’'\"«»")


def _is_vocab(token: str) -> bool:
    core = _core(token)
    return bool(core) and bool(
        TEMPO_RE.fullmatch(core)
        or PIECE_RE.fullmatch(core)
        or PIECE_RE.fullmatch(token.rstrip(","))
    )


def _title_word(token: str, names: bool) -> bool:
    """Can ``token`` precede a heading word as part of the title?

    Qualifiers ("Molto moderato", "Canone alla Quinta. Variatio 15") and,
    before a piece/form word (``names``), capitalised names ("La Follette
    Rondeau"); not footnote/metronome debris (ends with ")" or holds
    digits) nor abbreviations ("Clav.", "Op.").
    """
    core = _core(token)
    abbreviation = token.endswith(".") and len(core) <= 4 and not QUALIFIER_RE.fullmatch(core)
    if not core or token.endswith(")") or re.search(r"\d", token) or abbreviation:
        return False
    if QUALIFIER_RE.fullmatch(core):
        return True
    return names and bool(re.fullmatch(r"(?:L[ae]s?|L[’']\w+|[A-ZÀ-Ý][a-zà-ÿ’'-]{2,})", core))


def _bare_piece_word(token: str) -> bool:
    """A piece word without its own number ("Variatio", not "Var.II")."""
    core = _core(token)
    piece = PIECE_RE.fullmatch(core) or PIECE_RE.fullmatch(core + ".")
    return bool(core.isalpha() and piece and not TEMPO_RE.fullmatch(core))


def tidy_title(text: str) -> str:
    """Cut a heading down to its title phrase, dropping OCR debris.

    OCR'd bands also catch footnotes ("im September 1828.)", "parts of
    movement in song-form"), metronome marks ("108.)"), fingerings,
    editor names and catalogue numbers. The title is the run of heading
    vocabulary (tempo / form words and their qualifiers, a number right
    after a piece word) from the first capitalised tempo or piece word,
    plus a name just before a piece word ("La Follette Rondeau"). Text
    without heading vocabulary is returned unchanged.
    """
    named = NAMED_PIECE_RE.search(text)
    tokens = text.split()
    anchors = [k for k, t in enumerate(tokens) if _is_vocab(t) and not CATALOGUE_RE.match(t)]
    if not anchors:
        return named.group(0) if named else text
    # Headings are capitalised; footnote prose ("parts of movement") isn't.
    start = end = next((k for k in anchors if _core(tokens[k])[:1].isupper()), anchors[0])
    names = not TEMPO_ONLY_RE.search(tokens[start])
    while start > 0 and _title_word(tokens[start - 1], names):
        start -= 1
    k = end + 1
    while k < len(tokens):
        tok, core = tokens[k], _core(tokens[k])
        prev = tokens[k - 1]
        after_piece = _bare_piece_word(prev) or NUMBER_PREFIX_RE.fullmatch(_core(prev))
        number = re.fullmatch(r"\d{1,2}|[IVXL]+", core) or NUMBER_PREFIX_RE.fullmatch(core)
        if (
            _is_vocab(tok)
            or (core and QUALIFIER_RE.fullmatch(core))
            or (after_piece and (number or CATALOGUE_RE.match(tok)))
        ):
            end = k
        else:
            break
        k += 1
    # Trailing connectors ("Allegro ma") aren't part of the title.
    while (
        end > start and len(_core(tokens[end])) <= 3 and QUALIFIER_RE.fullmatch(_core(tokens[end]))
    ):
        end -= 1
    # Nor are leading ones ("la Allegro" from stray OCR letters).
    while (
        start < end
        and len(_core(tokens[start])) <= 2
        and QUALIFIER_RE.fullmatch(_core(tokens[start]))
    ):
        start += 1
    title = " ".join(tokens[start : end + 1]).strip(" .,;:")
    if named and named.group(0) not in title:
        name = named.group(0)
        title = name if title in name else f"{name} {title}"
    return title


def is_heading(text: str) -> bool:
    """Does OCR'd text above a system look like a piece/movement heading?

    Only real heading vocabulary counts: bare numbers or Roman numerals are
    too often OCR debris from stems, barlines and fingerings. Directions
    like "Segue la Fuga" end a piece rather than open one.
    """
    return bool(
        text
        and (PIECE_RE.search(text) or TEMPO_RE.search(text) or NAMED_PIECE_RE.search(text))
        and not CONTINUATION_RE.search(text)
    )


def is_tempo_only(text: str) -> bool:
    """A heading that is just a tempo word (no piece/dance/form name)."""
    stripped = TEMPO_ONLY_RE.sub("", text)
    return bool(TEMPO_ONLY_RE.search(text)) and not (
        PIECE_RE.search(stripped) or TEMPO_RE.search(stripped)
    )


# --- title normalisation -----------------------------------------------------

# Pieces of numbered prelude & fugue collections (WTC, Shostakovich op. 87,
# ...): OCR'd headings around them are noisy ("BWV873 Prelude Cisb av I"),
# so their titles are rebuilt as "<Kind> <number>".
PRELUDE_RE = re.compile(
    r"\b(pr(?:ae|æ|ä|a|ee)lud\w*|pr[ée]lud[ei]\w*|pr(?:ae|æ|ä|e)ambul\w*)", re.I
)
FUGUE_RE = re.compile(r"\b(fughett\w*|fug(?:a|ue|e)\b|puga\b)", re.I)
# Directions to carry on into the next piece ("Segue la Fuga", "attacca
# subito la Fuga"): printed at the end of a piece, never a heading.
CONTINUATION_RE = re.compile(r"\b(segue|attacca|volti|folgt|suivez|suit)\b", re.I)
# A piece number printed right after the kind word: "Fuga 2", "Fuga II.",
# "Prelude No. 3" (not "Fuga à 3", which counts voices).
_NUMBER_AFTER = r"\s*(?:no\.?|nr\.?|n°)?\s*(\d{1,2}|[IVXL]{1,6})\b\.?"
MAX_PIECE_NUMBER = 48
# A printed number may skip at most this many pieces ahead of the sequence.
MAX_NUMBER_SKIP = 2
_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}


def _roman_value(text: str) -> int | None:
    if not ROMAN_RE.match(text):
        return None
    total = 0
    for a, b in zip(text, text[1:] + " ", strict=True):
        v = _ROMAN[a]
        total += -v if b in _ROMAN and _ROMAN[b] > v else v
    return total


def _canonical_kind(word: str) -> str:
    """Clean, consistent spelling of a prelude/fugue word from a heading."""
    low = word.lower()
    if low.startswith("fughett"):
        return "Fughetta"
    if low.startswith(("fug", "pug")):
        return {"fugue": "Fugue", "fuge": "Fuge"}.get(low, "Fuga")
    if "ambul" in low:
        return "Praeambulum"
    if re.match(r"pr[ée]lud", low):
        return {"preludio": "Preludio", "prélude": "Prélude"}.get(low, "Prelude")
    return "Praeludium"


def _piece_number(title: str, match: re.Match[str]) -> int | None:
    """The piece number printed after the kind word, if plausible."""
    m = re.match(_NUMBER_AFTER, title[match.end() :], re.I)
    if not m:
        return None
    raw = m.group(1)
    n = int(raw) if raw.isdigit() else _roman_value(raw.upper())
    return n if n and 1 <= n <= MAX_PIECE_NUMBER else None


def _prelude_or_fugue(title: str) -> tuple[str, str, int | None] | None:
    """("prelude" | "fugue", canonical kind word, number) of a heading.

    A combined heading ("Praeludium und Fuga 2, c-Moll") opens with the
    prelude; its number is the first one after either word.
    """
    pre, fug = PRELUDE_RE.search(title), FUGUE_RE.search(title)
    first = min((m for m in (pre, fug) if m), key=lambda m: m.start(), default=None)
    if first is None:
        return None
    number = next((n for m in (pre, fug) if m and (n := _piece_number(title, m))), None)
    family = "prelude" if first is pre else "fugue"
    return family, _canonical_kind(first.group(1)), number


def _number_pieces(parsed: list[tuple[str, str, int | None] | None]) -> list[int | None]:
    """Piece number of every prelude/fugue, consistent with its neighbours.

    A fugue takes the number of the prelude just before it (its own printed
    number is often misread, e.g. "Fuga 2 à 3" → "2443", or absent). Other
    numbers follow the sequence unless printed close ahead of it (a piece
    may have been missed) or printed as 1 (an appendix restarts). Leading
    unnumbered pieces are numbered back from the first known number.
    """
    numbers: list[int | None] = []
    current: int | None = None
    last_family = ""
    for p in parsed:
        if p is None:
            numbers.append(None)
            continue
        family, _, number = p
        following = current + 1 if current is not None else None
        if family == "fugue" and last_family == "prelude" and current is not None:
            number = current
        elif following is not None and (
            number is None
            or not (number == 1 or following <= number <= following + MAX_NUMBER_SKIP)
        ):
            number = following
        current, last_family = number, family
        numbers.append(number)
    nxt: tuple[str, int] | None = None
    for k in range(len(parsed) - 1, -1, -1):
        p = parsed[k]
        if p is None:
            continue
        if numbers[k] is None and nxt is not None:
            same_pair = p[0] == "prelude" and nxt[0] == "fugue"
            guess = nxt[1] if same_pair else nxt[1] - 1
            numbers[k] = guess if guess >= 1 else None
        n = numbers[k]
        nxt = (p[0], n) if n is not None else None
    return numbers


def _most_common_word(parsed: list[tuple[str, str, int | None] | None], family: str) -> str:
    words = [p[1] for p in parsed if p and p[0] == family]
    default = "Praeludium" if family == "prelude" else "Fuga"
    return max(words, key=words.count) if words else default


def normalize_titles(titles: list[str]) -> list[str | None]:
    """Rebuild prelude/fugue titles as "<Kind> <n>", dropping OCR debris.

    Each family gets one spelling (the document's most common one), so the
    list reads consistently. Untitled starts (from final barlines) between
    two numbered pieces are checked against the prelude/fugue alternation:
    one in place of a missing piece takes its title, the others are
    misdetections (e.g. an unreadable repeat barline inside a prelude) and
    come back as None, to be dropped. Other titles are left untouched.
    """
    parsed = [_prelude_or_fugue(t) if t else None for t in titles]
    numbers = _number_pieces(parsed)
    words = {f: _most_common_word(parsed, f) for f in ("prelude", "fugue")}
    out: list[str | None] = list(titles)
    for k, p in enumerate(parsed):
        if p is not None:
            out[k] = f"{words[p[0]]} {numbers[k]}" if numbers[k] else words[p[0]]

    known = [k for k, p in enumerate(parsed) if p is not None and numbers[k] is not None]
    for a, b in zip(known, known[1:], strict=False):
        gap = [k for k in range(a + 1, b) if not titles[k]]
        if not gap or len(gap) != b - a - 1:
            continue
        fam_a, fam_b = parsed[a][0], parsed[b][0]  # type: ignore[index]
        n_a, n_b = numbers[a], numbers[b]
        assert n_a is not None and n_b is not None
        missing = ("fugue", n_a) if fam_a == "prelude" else ("prelude", n_a + 1)
        after_missing = ("prelude", n_a + 1) if fam_a == "prelude" else ("fugue", n_a + 1)
        if (fam_b, n_b) == missing:
            labels: list[str | None] = [None] * len(gap)
        elif (fam_b, n_b) == after_missing:
            labels = [f"{words[missing[0]]} {missing[1]}"] + [None] * (len(gap) - 1)
        else:
            continue
        for k, label in zip(gap, labels, strict=True):
            out[k] = label
    return out


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


# An image covering at least this share of the page makes it a scan.
SCAN_IMAGE_COVERAGE = 0.5


def is_scanned(page: pdfium.PdfPage) -> bool:
    """Is the page a scanned image (possibly with an invisible OCR text layer)?

    Scanners and archives (e.g. the Internet Archive) add a hidden OCR text
    layer that is mostly garbage on music: it may still hold a legible
    heading, but where it doesn't, Tesseract on the heading band is tried.
    """
    width, height = page.get_size()
    for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE], max_depth=2):
        left, bottom, right, top = obj.get_bounds()
        if (right - left) * (top - bottom) >= SCAN_IMAGE_COVERAGE * width * height:
            return True
    return False


# Skew angles (degrees) tried when straightening scanned pages.
SKEW_ANGLES = np.linspace(-2.0, 2.0, 17)


def skew_angle(gray: np.ndarray) -> float:
    """Rotation (degrees) that makes the page's staff lines horizontal.

    Scans are often a degree or two off: each staff line then spreads over
    several pixel rows and no row is inked enough to be found. The angle
    whose row projection is the most peaked (sum of squares) wins.
    """
    small = Image.fromarray(((gray[::2, ::2] < INK) * 255).astype(np.uint8))

    def peakedness(angle: float) -> float:
        rows = np.asarray(small.rotate(angle, resample=Image.Resampling.NEAREST)).sum(axis=1)
        return float((rows.astype(np.float64) ** 2).sum())

    def score(angle: float) -> tuple[float, float]:
        # Tiny rotations change nothing at this resolution: prefer the
        # smallest angle among equally good ones.
        return peakedness(angle), -abs(angle)

    coarse = float(max(SKEW_ANGLES, key=score))
    step = float(SKEW_ANGLES[1] - SKEW_ANGLES[0])
    return float(max(np.linspace(coarse - step, coarse + step, 11), key=score))


def _render_gray(page: pdfium.PdfPage) -> np.ndarray:
    bitmap = page.render(scale=RENDER_DPI / 72, grayscale=True)
    gray = np.asarray(bitmap.to_pil().convert("L"))
    angle = skew_angle(gray)
    if abs(angle) < 0.05:
        return gray
    rotated = np.asarray(
        Image.fromarray(gray).rotate(angle, resample=Image.Resampling.BILINEAR, fillcolor=255)
    )
    # Rotating blurs thin lines a little: keep it only when it finds more staves.
    return rotated if len(find_staves(rotated)) > len(find_staves(gray)) else gray


@dataclass
class _PageInfo:
    number: int  # 1-based
    shape: tuple[int, ...]
    systems: list[System]
    lines: list[TextLine]
    ocr: list[OcrText] = field(default_factory=list)  # heading text above each system
    # Per system: barline_kind() of its closing barline.
    bar_kinds: list[str] = field(default_factory=list)


def _tempo_opens(ocr: OcrText, system: System, prev_final: bool) -> bool:
    """Can a bare tempo word above ``system`` open a new movement?

    Only when the previous system closed with a double/final barline and the
    word sits above the start of this system: tempo changes inside a
    movement are printed over a later bar, usually without a final barline.
    """
    return prev_final and ocr.left - system.left < TEMPO_START_FRACTION * (
        system.right - system.left
    )


def _split_half(system: System, prev_bottom: int | None) -> bool:
    """Is ``system`` really the lower half of the previous one, split apart?

    Staves of one system sit much closer together than consecutive systems;
    when detection fails to join them, both halves end with the same final
    barline, which must not count as a piece ending inside the system.
    """
    if prev_bottom is None:
        return False
    staff_h = system.staves[0].bottom - system.staves[0].top
    return system.top - prev_bottom < 1.5 * staff_h


def _text_headings(info: _PageInfo, lines: list[TextLine]) -> list[OcrText]:
    """Heading text above every system of a page, from its text layer.

    The first system's heading area is everything above it (titles,
    composer, opening tempo); later systems use the band just above them,
    like OCR, so a piece starting mid-page (a fugue after its prelude) is
    found too. ``left`` is the system's own left: text-layer lines are
    whole lines, so their horizontal position isn't meaningful.
    """
    h = info.shape[0]
    out: list[OcrText] = []
    prev: int | None = None
    for system in info.systems:
        top, bottom = (
            (0, system.top) if prev is None else (_heading_band(system, prev)[0], system.top)
        )
        out.append(OcrText(heading_for(lines, bottom / h, top / h) or "", system.left))
        prev = system.bottom
    return out


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
    # Closing barline of the previous system in reading order. The first
    # system of the document (and the first after front matter) follows "an
    # end", so it always opens a section even without a legible heading.
    prev_kind = "final"
    prev_bottom: int | None = None  # previous system's bottom, same page only
    for info in pages:
        if not info.systems:
            # Title/preface page: the music after it starts fresh.
            prev_kind, prev_bottom = "final", None
            continue
        kinds = info.bar_kinds or ["single"] * len(info.systems)
        lines = [ln for ln in info.lines if _norm(ln.text) not in repeated]
        if info.lines:
            # Engraved PDF: headings from the text layer, already clean.
            heads, source = _text_headings(info, lines), "text"
        else:
            heads, source = info.ocr, "ocr"
        page_starts = []
        headed = 0
        for j, head in enumerate(heads):
            src = source
            if src == "text" and not head.text and info.ocr:
                # Scan with a hidden text layer that has no heading here.
                head, src = info.ocr[j], "ocr"
            title = head.text if src == "text" else clean_title(head.text)
            headed += is_heading(title)
            if CONTINUATION_RE.search(title):
                # "Segue la Fuga" closes a piece: what follows on this
                # page (an ossia, a variant) doesn't open one.
                prev_kind = kinds[j]
                prev_bottom = info.systems[j].bottom
                continue
            if is_heading(title) and (
                not is_tempo_only(title)
                # A tempo heading at the very top of a text page is the
                # page's title area, not a tempo change over a later bar.
                or (src == "text" and j == 0)
                or _tempo_opens(head, info.systems[j], prev_kind != "single")
            ):
                # Text-layer headings are clean already; OCR'd ones carry
                # debris from the whole band.
                page_starts.append((j, title if src == "text" else tidy_title(title), src))
            elif prev_kind == "final" and not _split_half(info.systems[j], prev_bottom):
                # A final barline (thin + thick) closed the previous piece:
                # this system opens the next one even if its heading (e.g. a
                # bare number) wasn't legible.
                page_starts.append((j, "", "layout"))
            prev_kind = kinds[j]
            prev_bottom = info.systems[j].bottom
        prev_kind, prev_bottom = kinds[-1], None
        if headed >= INDEX_PAGE_MIN_HEADINGS and headed * 2 >= len(info.systems):
            # A page where most systems have a heading is an edition's index
            # of incipits / contents page, not music to navigate to; what
            # follows it starts fresh, like after a title page.
            prev_kind = "final"
            continue
        for j, cleaned, src in page_starts:
            starts.append((info, j, cleaned, src))
    return starts


# An outline with fewer entries than one per this many pages lists whole
# works only (e.g. "Sonata No. 1", "Sonata No. 2"...): their movements are
# detected too and listed under each entry.
OUTLINE_SPARSE_PAGES = 8


def _sparse_outline(outline: list[DetectedSection], n_pages: int) -> bool:
    return n_pages >= OUTLINE_SPARSE_PAGES * len(outline)


def _merge_outline(
    outline: list[DetectedSection], detected: list[tuple[int, int, DetectedSection]]
) -> list[DetectedSection]:
    """Outline entries plus the titled sections detected inside them.

    A detection at the top of an outline entry's page is that entry itself;
    untitled (barline-only) detections would be meaningless numbers next to
    the outline's titles, so they are left out.
    """
    first_pages = {sec.page for sec in outline}
    keyed = [((sec.page, -1), sec) for sec in outline]
    for page, sys_idx, sec in detected:
        if sec.source == "layout" or (page in first_pages and sys_idx == 0):
            continue
        keyed.append(((page, sys_idx), sec))
    return [sec for _, sec in sorted(keyed, key=lambda item: item[0])]


def extract_sections(data: bytes, max_pages: int = 1000) -> list[DetectedSection]:
    """Detect section starts (with incipits) in a score PDF."""
    outline = outline_sections(data)
    pdf = pdfium.PdfDocument(data)
    try:
        n = min(len(pdf), max_pages)

        for sec in outline:
            if sec.page <= n:
                gray = _render_gray(pdf[sec.page - 1])
                systems = page_systems(gray)
                if systems:
                    sec.incipit_png = crop_incipit(gray, systems[0])
        if outline and not _sparse_outline(outline, n):
            return outline

        # Pass 1: per-page features only (rendered pages are ~1 MB each, so a
        # 600-page volume must not keep them all in memory).
        pages: list[_PageInfo] = []
        for i in range(n):
            page = pdf[i]
            gray = _render_gray(page)
            systems = page_systems(gray)
            lines = text_lines(page)
            # Scans have no text layer, or a hidden OCR one that is mostly
            # garbage on music: read the headings with Tesseract too.
            ocr = ocr_headings(gray, systems) if systems and (not lines or is_scanned(page)) else []
            ink = gray < INK
            kinds = [barline_kind(ink, s) for s in systems]
            pages.append(_PageInfo(i + 1, gray.shape, systems, lines, ocr, kinds))

        # Pass 2: re-render only the pages that need an incipit crop.
        starts = _find_starts(pages)
        titles = normalize_titles([title for _, _, title, _ in starts])
        detected: list[tuple[int, int, DetectedSection]] = []
        for (info, sys_idx, _, source), title in zip(starts, titles, strict=True):
            if title is None:
                continue
            gray = _render_gray(pdf[info.number - 1])
            sec = DetectedSection(
                title=title or str(len(detected) + 1),
                page=info.number,
                source=source,
                incipit_png=crop_incipit(gray, info.systems[sys_idx]),
            )
            detected.append((info.number, sys_idx, sec))
        if outline:
            return _merge_outline(outline, detected)
        return [sec for _, _, sec in detected]
    finally:
        pdf.close()
