"""Tests for the deterministic table-of-contents extraction (app/toc.py)."""

import io
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from pypdf import PdfWriter

from app import toc

DATA = Path(__file__).parent / "data" / "toc"


def _page(
    systems: int = 2,
    staves_per_system: int = 2,
    width: int = 800,
    height: int = 1000,
    final: tuple[int, ...] = (),
):
    """A white page with ``systems`` systems of joined 5-line staves.

    Systems whose index is in ``final`` end with a thin+thick final barline.
    """
    img = np.full((height, width), 255, dtype=np.uint8)
    y = 120
    for k in range(systems):
        sys_top = y
        for _ in range(staves_per_system):
            for line in range(5):
                img[y + line * 10, 60:740] = 0
            y += 80
        # Left system barline joining the staves of this system.
        img[sys_top : y - 40, 60] = 0
        if k in final:
            img[sys_top : y - 40, 733] = 0
            img[sys_top : y - 40, 736:740] = 0
        y += 80
    return img


def _ocr(*texts: str, left: int = 60):
    """Fake ocr_headings result: one entry per system, at the system start."""
    return [toc.OcrText(t, left) for t in texts]


def _pdf_from_pages(*arrays: np.ndarray) -> bytes:
    images = [Image.fromarray(a).convert("RGB") for a in arrays]
    buf = io.BytesIO()
    images[0].save(buf, format="PDF", save_all=True, append_images=images[1:], resolution=100)
    return buf.getvalue()


def _tsv(*words: tuple[int, str]) -> bytes:
    """Fake Tesseract TSV output: (top px in the upscaled strip image, text)."""
    header = "\t".join(
        ["level", "page_num", "block_num", "par_num", "line_num", "word_num"]
        + ["left", "top", "width", "height", "conf", "text"]
    )
    rows = [
        f"5\t1\t1\t1\t1\t{i}\t{10 * i}\t{top}\t10\t10\t90\t{text}"
        for i, (top, text) in enumerate(words)
    ]
    rows.append("5\t1\t1\t1\t1\t9\t0\t0\t10\t10\t20\tlowconf")  # dropped: confidence
    rows.append("5\t1\t1\t1\t1\t9\t0\t0\t10\t10\t-1\t")  # dropped: empty
    return ("\n".join([header, *rows]) + "\n").encode()


def test_find_staves_and_systems():
    """Staves are found and grouped into systems via the left barline."""
    gray = _page(systems=2, staves_per_system=2)
    assert len(toc.find_staves(gray)) == 4
    systems = toc.page_systems(gray)
    assert [len(s.staves) for s in systems] == [2, 2]
    assert systems[0].top < systems[0].bottom < systems[1].top
    assert systems[0].left <= 60 <= systems[0].right


def test_group_systems_without_ink_and_empty():
    """Without the ink mask every staff is its own system; no staves → none."""
    staves = toc.find_staves(_page(systems=1, staves_per_system=2))
    assert len(toc.group_systems(staves)) == 2
    assert toc.group_systems([]) == []


def test_row_runs_open_at_end():
    assert toc._row_runs(np.array([False, True, True])) == [(1, 2)]


def test_joined_touching_staves():
    """Overlapping/touching staves are always the same system."""
    a = toc.Staff(top=0, bottom=50, left=10, right=100)
    b = toc.Staff(top=50, bottom=90, left=10, right=100)
    assert toc._joined(np.zeros((100, 120), dtype=bool), a, b)


def test_crop_incipit_is_png():
    gray = _page()
    img = Image.open(io.BytesIO(toc.crop_incipit(gray, toc.page_systems(gray)[0])))
    assert img.format == "PNG"
    assert img.height < gray.shape[0] / 2


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Anda nte a 2", "Andante"),
        ("4 4 4 4 Adagio. Largo. 5 5 1", "Adagio. Largo"),
        ("316 Allegro", "Allegro"),
        ("Variatio 3. Canone all’ Unisuono. 1 a", "Variatio 3. Canone all’ Unisuono"),
        ("II. Adagio", "II. Adagio"),
        ("Allegro T8 —", "Allegro"),
    ],
)
def test_clean_title(raw, expected):
    assert toc.clean_title(raw) == expected


@pytest.mark.parametrize(
    ("text", "heading"),
    [
        ("Menuetto", True),
        ("Variatio 1. a 1 Clav", True),
        ("Sonata No. 3", True),
        ("no 5 he", False),
        ("I", False),
        ("cha 2 RL", False),
        ("", False),
    ],
)
def test_is_heading(text, heading):
    assert toc.is_heading(text) is heading


def test_heading_for():
    """Title lines above the first system build the heading; dynamics don't."""
    lines = [
        toc.TextLine("Piano Sonata No.1", top=0.05, height=14),
        toc.TextLine("Adagio.", top=0.1, height=9),
        toc.TextLine("dolce", top=0.12, height=7),
        toc.TextLine("Allegro", top=0.6, height=9),  # below the first system
    ]
    assert toc.heading_for(lines, header_bottom=0.15) == "Piano Sonata No.1 — Adagio"
    assert toc.heading_for([toc.TextLine("p", 0.05, 9)], 0.15) is None
    # Tempo already part of the title isn't repeated.
    assert toc.heading_for([toc.TextLine("Menuetto", 0.05, 9)], 0.15) == "Menuetto"


def test_ocr_headings_maps_words_to_systems(monkeypatch):
    """One Tesseract call per page; words land on the system below them."""
    gray = _page(systems=2)
    systems = toc.page_systems(gray)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        strip = Image.open(io.BytesIO(kwargs["input"]))
        # Inside the second band: the stacked image ends with that band and a
        # 20 px spacer, both upscaled.
        second = strip.height - (20 + 2) * toc.OCR_UPSCALE
        return subprocess.CompletedProcess(
            cmd, 0, stdout=_tsv((0, "Allegro"), (second, "Menuetto"))
        )

    monkeypatch.setattr(toc.subprocess, "run", fake_run)
    heads = toc.ocr_headings(gray, systems)
    assert [h.text for h in heads] == ["Allegro", "Menuetto"]
    assert heads[0].left == 0 and heads[1].left == 5  # word x / upscale
    assert len(calls) == 1
    assert toc.ocr_headings(gray, []) == []


def test_extract_sections_scanned(monkeypatch):
    """Scans: title/blank pages are skipped, OCR headings open sections."""
    blank = np.full((1000, 800), 255, dtype=np.uint8)
    data = _pdf_from_pages(blank, _page(), _page(), _page())
    page_heads = iter([_ocr("", "garbage"), _ocr("Menuetto", ""), _ocr("", "")])
    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: next(page_heads))

    sections = toc.extract_sections(data)
    # First music page always opens a section; page 3 has a heading.
    assert [(s.page, s.source, s.title) for s in sections] == [
        (2, "layout", "1"),
        (3, "ocr", "Menuetto"),
    ]
    assert all(s.incipit_png for s in sections)


def test_index_pages_are_skipped(monkeypatch):
    """A page where (almost) every system has a heading is an incipit index."""
    data = _pdf_from_pages(_page(systems=4, staves_per_system=1), _page())
    page_heads = iter([_ocr("Sonata", "Aria", "Rondo", "Menuetto"), _ocr("Menuetto", "")])
    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: next(page_heads))
    sections = toc.extract_sections(data)
    assert [(s.page, s.title) for s in sections] == [(2, "Menuetto")]


def test_extract_sections_outline():
    """A meaningful PDF outline is used as-is, with incipits."""
    writer = PdfWriter(clone_from=io.BytesIO(_pdf_from_pages(_page(), _page(), _page())))
    writer.add_outline_item("Sonata No. 2", 2)
    parent = writer.add_outline_item("Sonata No. 1", 0)
    writer.add_outline_item("I. Allegro", 0, parent=parent)
    buf = io.BytesIO()
    writer.write(buf)

    sections = toc.extract_sections(buf.getvalue())
    assert [(s.page, s.title) for s in sections] == [
        (1, "Sonata No. 1"),
        (1, "I. Allegro"),
        (3, "Sonata No. 2"),
    ]
    assert all(s.source == "outline" and s.incipit_png for s in sections)


def test_junk_outline_is_ignored(monkeypatch):
    """Scanner outlines (one file-name bookmark per page) are discarded."""
    writer = PdfWriter(clone_from=io.BytesIO(_pdf_from_pages(*[_page() for _ in range(4)])))
    for i in range(4):
        writer.add_outline_item(f"Binder1_Page_0{i + 1}_Image_0001.tif", i)
    buf = io.BytesIO()
    writer.write(buf)
    assert toc.outline_sections(buf.getvalue()) == []

    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: _ocr(*["" for _ in systems]))
    assert [s.source for s in toc.extract_sections(buf.getvalue())] == ["layout"]


def test_meaningful_outline_rules():
    sec = toc.DetectedSection
    assert not toc._meaningful_outline([], 10)
    # One bookmark per page → scanner-made.
    assert not toc._meaningful_outline([sec(f"Sonata {i}", i, "outline") for i in range(10)], 10)
    assert toc._meaningful_outline([sec("Sonata No. 1", 1, "outline")], 10)


def test_extract_sections_engraved_text_layer():
    """Engraved PDFs: headings come from the text layer, no OCR needed."""
    sections = toc.extract_sections((DATA / "engraved.pdf").read_bytes())
    assert sections
    assert sections[0].page == 1
    assert sections[0].source == "text"
    assert "Movement" in sections[0].title


def test_ends_with_double_bar():
    gray = _page(systems=2, final=(1,))
    ink = gray < toc.INK
    first, second = toc.page_systems(gray)
    assert not toc.ends_with_double_bar(ink, first)
    assert toc.ends_with_double_bar(ink, second)


@pytest.mark.parametrize(
    ("text", "tempo_only"),
    [
        ("Allegro", True),
        ("Adagio. Largo", True),
        ("Allegro moderato", True),
        ("Menuetto. Allegretto", False),
        ("Variatio 3. Allegro", False),
        ("Sonata No. 2 — Presto", False),
        ("Rondo", False),
    ],
)
def test_is_tempo_only(text, tempo_only):
    assert toc.is_tempo_only(text) is tempo_only


def test_tempo_heading_needs_final_barline(monkeypatch):
    """Bare tempo words open a movement only after a double/final barline."""
    # Page 1: first system opens the piece; second ends with a final barline.
    # Page 2: "Adagio" after the final barline → new movement; "Allegro"
    #         after a plain barline → just a tempo change.
    data = _pdf_from_pages(_page(systems=2, final=(1,)), _page(systems=3))
    page_heads = iter([_ocr("", ""), _ocr("Adagio", "Allegro", "")])
    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: next(page_heads))
    sections = toc.extract_sections(data)
    assert [(s.page, s.title) for s in sections] == [(1, "1"), (2, "Adagio")]


def test_tempo_printed_mid_system_is_a_tempo_change():
    system = toc.page_systems(_page(systems=1))[0]
    assert toc._tempo_opens(toc.OcrText("Adagio", system.left), system, True)
    assert not toc._tempo_opens(toc.OcrText("Adagio", system.left + 400), system, True)
    assert not toc._tempo_opens(toc.OcrText("Adagio", system.left), system, False)


def test_final_barline_opens_next_system_without_heading(monkeypatch):
    """After a final barline the next system opens a piece even without a
    legible heading — but not the other half of a split system."""
    data = _pdf_from_pages(_page(systems=3, staves_per_system=1, final=(0,)))
    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: _ocr(*["" for _ in systems]))
    assert [(s.page, s.source) for s in toc.extract_sections(data)] == [
        (1, "layout"),
        (1, "layout"),
    ]
    staff = toc.Staff(top=100, bottom=140, left=0, right=10)
    assert toc._split_half(toc.System([staff]), prev_bottom=90)
    assert not toc._split_half(toc.System([staff]), prev_bottom=None)


def test_barline_kinds():
    """Single, final (thin+thick), double (thin+thin) and repeat (dots)."""
    gray = _page(systems=4, staves_per_system=1, final=(1, 2, 3))
    staves = toc.find_staves(gray)
    # system 2: make it a thin double bar; system 3: add repeat dots.
    s2, s3 = staves[2], staves[3]
    gray[s2.top : s2.bottom, 736:740] = 255
    gray[s2.top : s2.bottom, 737] = 0
    for st in (s3,):
        for k in (1.5, 2.5):
            y = int(st.top + k * 10)
            gray[y - 1 : y + 1, 728:730] = 0
    ink = gray < toc.INK
    kinds = [toc.barline_kind(ink, s) for s in toc.page_systems(gray)]
    assert kinds == ["single", "final", "double", "repeat"]
    assert toc.ends_with_double_bar(ink, toc.page_systems(gray)[1])


def test_staff_with_stray_line_is_still_found():
    """A beam drawn across a staff adds a stray 'line'; the staff survives."""
    gray = _page(systems=2, staves_per_system=2)
    clean = toc.find_staves(gray)
    s = clean[0]
    gray[s.top + 5, 60:740] = 0  # stray row between lines 1 and 2
    assert len(toc.find_staves(gray)) == len(clean)


def test_stray_lines_without_page_spacing():
    """With no clean staff on the page there is no spacing to search with."""
    gray = np.full((300, 800), 255, dtype=np.uint8)
    for y in (100, 104, 116, 120, 136, 140):  # uneven: never a plain staff
        gray[y, 60:740] = 0
    assert toc.find_staves(gray) == []


def test_long_horizontal_on_narrow_image():
    ink = np.ones((3, 5), dtype=bool)
    assert toc._long_horizontal(ink, length=10) is ink


def test_first_system_opens_even_when_heading_is_rejected(monkeypatch):
    """A tempo word printed mid-system on the first music page is rejected,
    but the first system still opens a section."""
    data = _pdf_from_pages(_page(systems=1))
    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: [toc.OcrText("Allegro", 600)])
    assert [(s.page, s.source) for s in toc.extract_sections(data)] == [(1, "layout")]
