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


def _page(systems: int = 2, staves_per_system: int = 2, width: int = 800, height: int = 1000):
    """A white page with ``systems`` systems of joined 5-line staves."""
    img = np.full((height, width), 255, dtype=np.uint8)
    y = 120
    for _ in range(systems):
        sys_top = y
        for _ in range(staves_per_system):
            for line in range(5):
                img[y + line * 10, 60:740] = 0
            y += 80
        # Left system barline joining the staves of this system.
        img[sys_top : y - 40, 60] = 0
        y += 80
    return img


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
    assert toc.ocr_headings(gray, systems) == ["Allegro", "Menuetto"]
    assert len(calls) == 1
    assert toc.ocr_headings(gray, []) == []


def test_extract_sections_scanned(monkeypatch):
    """Scans: title/blank pages are skipped, OCR headings open sections."""
    blank = np.full((1000, 800), 255, dtype=np.uint8)
    data = _pdf_from_pages(blank, _page(), _page(), _page())
    page_heads = iter([["", "garbage"], ["Menuetto", ""], ["", ""]])
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
    page_heads = iter([["Allegro", "Vivace", "Adagio", "Presto"], ["Menuetto", ""]])
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

    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: ["" for _ in systems])
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
