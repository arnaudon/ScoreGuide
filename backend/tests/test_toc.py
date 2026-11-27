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
    indent: tuple[int, ...] = (),
):
    """A white page with ``systems`` systems of joined 5-line staves.

    Systems whose index is in ``final`` end with a thin+thick final barline;
    those in ``indent`` start 60 px further right (a piece's first system).
    """
    img = np.full((height, width), 255, dtype=np.uint8)
    y = 120
    for k in range(systems):
        sys_top = y
        left = 120 if k in indent else 60
        for _ in range(staves_per_system):
            for line in range(5):
                img[y + line * 10, left:740] = 0
            y += 80
        # Left system barline joining the staves of this system.
        img[sys_top : y - 40, left] = 0
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
        ("N O C T U R N E No. 1", "NOCTURNE No.1"),
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
    assert [s.level for s in sections] == [0, 1, 0]
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


def test_final_barline_is_detected():
    gray = _page(systems=2, final=(1,))
    ink = gray < toc.INK
    first, second = toc.page_systems(gray)
    assert toc.barline_kind(ink, first) == "single"
    assert toc.barline_kind(ink, second) != "single"


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


@pytest.mark.parametrize(
    "title",
    ["Praeludium I", "Præludium II", "Präludium", "Praludium", "Prelude", "Prélude", "Preludio"]
    + ["Praeambulum", "Fuga I", "Fughetta"],
)
def test_prelude_spellings_are_piece_titles(title):
    """German editions spell it Praeludium (Peters, Bach-Gesellschaft, Henle)."""
    assert toc.PIECE_RE.search(title)
    assert toc.is_heading(title) and not toc.is_tempo_only(title)


def test_is_scanned():
    """A page that is one big image is a scan; engraved vector pages aren't."""
    import pypdfium2 as pdfium

    scan = pdfium.PdfDocument(_pdf_from_pages(_page()))
    engraved = pdfium.PdfDocument((DATA / "engraved.pdf").read_bytes())
    try:
        assert toc.is_scanned(scan[0])
        assert not toc.is_scanned(engraved[0])
    finally:
        scan.close()
        engraved.close()


def test_scan_hidden_text_layer_falls_back_to_ocr(monkeypatch):
    """Scans with an invisible OCR text layer (Internet Archive, scanners):
    the layer's heading is used when legible, Tesseract's otherwise."""
    data = _pdf_from_pages(_page(), _page())
    layers = iter(
        [
            [toc.TextLine("Edition Peters", 0.02, 9), toc.TextLine("Praeludium", 0.05, 14)],
            [toc.TextLine("Edition Peters", 0.02, 9), toc.TextLine("Fnqa ЕШ", 0.05, 14)],
        ]
    )
    monkeypatch.setattr(toc, "text_lines", lambda page: next(layers))
    page_heads = iter([_ocr("Praeludium I.", ""), _ocr("Fuga II", "")])
    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: next(page_heads))
    sections = toc.extract_sections(data)
    assert [(s.page, s.source, s.title) for s in sections] == [
        (1, "text", "Praeludium 2"),
        (2, "ocr", "Fuga 2"),
    ]


def _text_page(number: int, lines: list[toc.TextLine], final: tuple[int, ...] = ()):
    gray = _page(systems=3, final=final)
    systems = toc.page_systems(gray)
    kinds = [toc.barline_kind(gray < toc.INK, s) for s in systems]
    return toc._PageInfo(number, gray.shape, systems, lines, bar_kinds=kinds)


def _above(gray_h: int, system: toc.System, offset: int = 15) -> float:
    return (system.top - offset) / gray_h


def test_text_heading_mid_page_opens_section():
    """Engraved pages: a fugue starting below its prelude's last system is
    found from the text in the band above that system."""
    probe = _text_page(1, [])
    h = probe.shape[0]
    second, third = probe.systems[1], probe.systems[2]
    page = _text_page(
        1,
        [
            toc.TextLine("Praeludium I", 0.02, 14),
            toc.TextLine("Fuga I", _above(h, third), 14),
        ],
    )
    assert [(j, title, src) for _, j, title, src, _ in toc._find_starts([page])] == [
        (0, "Praeludium I", "text"),
        (2, "Fuga I", "text"),
    ]
    # A tempo change above a later system (no final barline) isn't a piece.
    page.lines = [
        toc.TextLine("Praeludium I", 0.02, 14),
        toc.TextLine("Adagio", _above(h, second), 9),
    ]
    assert [j for _, j, _, _, _ in toc._find_starts([page])] == [0]


def test_text_page_final_barline_and_tempo():
    """On text pages too, a final barline opens the next system and a bare
    tempo word after it is a new movement's heading."""
    probe = _text_page(1, [])
    h = probe.shape[0]
    first = _text_page(1, [toc.TextLine("Sonata No. 1", 0.02, 14)], final=(0, 1))
    second = _text_page(2, [toc.TextLine("Presto", _above(h, probe.systems[2]), 9)], final=(1,))
    starts = [(p.number, j, t, s) for p, j, t, s, _ in toc._find_starts([first, second])]
    assert starts == [
        (1, 0, "Sonata No. 1", "text"),
        (1, 1, "", "layout"),
        (1, 2, "", "layout"),
        (2, 2, "Presto", "text"),
    ]


def test_text_index_page_is_skipped():
    """An engraved incipit index (a heading above most systems) is skipped."""
    probe = _text_page(1, [])
    h = probe.shape[0]
    lines = [toc.TextLine("Praeludium I", 0.02, 14)] + [
        toc.TextLine(f"Fuga {k}", _above(h, s), 14) for k, s in enumerate(probe.systems[1:])
    ]
    assert toc._find_starts([_text_page(1, lines)]) == []


def test_normalize_titles_prelude_and_fugue():
    """Noisy OCR headings become "<Kind> <n>" with one spelling per kind;
    fugues take their prelude's number; untitled starts are checked
    against the prelude/fugue alternation."""
    titles = [
        "BWV870 Prelude",  # numbered back from the next piece
        "Fuga",
        "BWV di Bach Præludium 2. pp",
        "Fuga 43 LN LS",  # "à 3" misread as part of the number
        "",  # a missing piece: Prelude 3
        "",  # misdetection after it
        "Fuga 3 à 3",
        "YU, BWV873 Prelude",
        "",  # inside a complete pair: misdetection
        "Fughetta",
        "BWV874 Fassung di Bach Preeludium 6",  # skipped a piece: kept
        "Prélude XXI",  # far off the sequence: continued instead
        "Puga 2443",
        "Prelude et Fugue 1.",  # an appendix restarts at 1
        "Sonata No. 1",
        "",
    ]
    assert toc.normalize_titles(titles) == [
        "Prelude 1",
        "Fuga 1",
        "Prelude 2",
        "Fuga 2",
        "Prelude 3",
        None,
        "Fuga 3",
        "Prelude 4",
        None,
        "Fuga 4",
        "Prelude 6",
        "Prelude 7",
        "Fuga 7",
        "Prelude 1",
        "Sonata No. 1",
        "",
    ]


@pytest.mark.parametrize(
    ("titles", "expected"),
    [
        (["Preludio", "Fuge"], ["Preludio", "Fuge"]),
        (["Fugue No. 2", "Fuga"], ["Fugue 2", "Fugue"]),  # no preludes: as printed
        # An unconfirmed jump (nothing printed after it) is a misread.
        (
            ["Prelude 1", "Fuga", "Prelude 9", "Fuga"],
            ["Prelude 1", "Fuga 1", "Prelude 2", "Fuga 2"],
        ),
        (["Praeambulum I"], ["Praeambulum 1"]),
        (["Fuga IIII"], ["Fuga"]),  # not a Roman numeral
        (["Fuga XIV"], ["Fuga 14"]),
        (["Praelud j"], ["Praeludium"]),
        (["Fuga 1", "Praeludium", "Fuga II"], ["Fuga 1", "Praeludium 2", "Fuga 2"]),
        (["Fuga 8", "", "Fuga 10"], ["Fuga 8", "", "Fuga 10"]),  # not a clear gap
        (["Fuga 8", "", "Sonata", "Fuga 9"], ["Fuga 8", "", "Sonata", "Fuga 9"]),
        (["Praeludium 1", "", "Praeludium 2"], ["Praeludium 1", "Fuga 1", "Praeludium 2"]),
        (["Fuga", "Prelude 1"], ["Fuga", "Prelude 1"]),
        (["", "Fuga 1"], ["", "Fuga 1"]),
        # A jump confirmed by the next printed number re-anchors the sequence
        # (pieces were missed), instead of overriding every later number.
        (
            ["Prelude 1", "Fuga", "Prelude 7", "", "Fuga", "Prelude 8"],
            ["Prelude 1", "Fuga 1", "Prelude 7", None, "Fuga 7", "Prelude 8"],
        ),
    ],
)
def test_normalize_titles_cases(titles, expected):
    assert toc.normalize_titles(titles) == expected


def test_extract_sections_drops_misdetections(monkeypatch):
    """A final barline misread inside a prelude doesn't add an entry, and a
    'Segue la Fuga' direction doesn't open the system below it."""
    data = _pdf_from_pages(_page(systems=2, final=(1,)), _page(systems=2), _page(systems=2))
    page_heads = iter(
        [
            _ocr("Praeludium 1.", "Segue la Fuga"),
            _ocr("", ""),  # after the (misread) final barline
            _ocr("Fuga à 3", ""),
        ]
    )
    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: next(page_heads))
    sections = toc.extract_sections(data)
    assert [(s.page, s.title) for s in sections] == [(1, "Praeludium 1"), (3, "Fuga 1")]


def test_continuation_notes_are_not_headings():
    """'Segue la Fuga' ends a prelude: it must not open a section."""
    assert not toc.is_heading("Segue la Fuga")
    assert not toc.is_heading("attacca subito la Fuga")
    assert toc.is_heading("Fuga 3")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("als Op. 120.) Jahre 1825.) Allegro moderato im TTT IS 7 Auk I", "Allegro moderato"),
        ("Kéchel Nr.545 24 Allegro", "Allegro"),
        ("4-96. Allegro moderato. 25 all", "Allegro moderato"),
        ("noto. Andante con moto. 66.) 2 di", "Andante con moto"),
        ("im September 1528.) Molto moderato I I", "Molto moderato"),
        ("Allegro troppo. ma non", "Allegro troppo"),
        ("la Allegro", "Allegro"),
        ("LUDWIG KLEE JOSEPH HAYDN. Allegro moderato", "Allegro moderato"),
        ("parts of movement in song-form. Moderato. JOSEPH HAYDN", "Moderato"),
        ("Variatio 3. Canone all’ Unisuono. 1 Clav. TZ", "Variatio 3. Canone all’ Unisuono"),
        ("Clav. Variatio 5. vero", "Variatio 5"),
        ("I 1 Var. IV", "Var. IV"),
        ("Var.I 2", "Var.I"),
        ("Sonata No. 3 Allegro", "Sonata No. 3 Allegro"),
        ("ua Joyeuse RONDEAU", "Joyeuse RONDEAU"),
        ("La Follette RONDEAU au ar", "La Follette RONDEAU"),
        ("Mr A La Boiteuse", "La Boiteuse"),
        ("Les Soupirs Tendrement", "Les Soupirs Tendrement"),
        ("Gigue. Les Cyclopes", "Les Cyclopes — Gigue"),
        ("LA VIRGINITE Sous le Domino. Modéré", "La Virginite — Modéré"),
        ("LES COUCOUS BÉNÉVOLES Allegretto", "Les Coucous Bénévoles — Allegretto"),
        ("La Folle Allegro", "La Folle Allegro"),
        ("no heading here", "no heading here"),
    ],
)
def test_tidy_title(raw, expected):
    assert toc.tidy_title(raw) == expected


def test_named_pieces_and_roman_variations_are_headings():
    assert toc.is_heading("La Boiteuse")
    assert toc.is_heading("VAR. III")
    assert toc.is_heading("Double")
    assert not toc.is_heading("La Csi")


def test_ocr_titles_are_tidied(monkeypatch):
    data = _pdf_from_pages(_page())
    heads = [_ocr("im September 1828.) Allegro. Aud", "")]
    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: heads[0])
    assert [s.title for s in toc.extract_sections(data)] == ["Allegro"]


def _barline_system(img: np.ndarray, ink_cols: list[tuple[int, int]], gaps: bool = False):
    """A one-system page whose right end has the given inked column ranges."""
    for a, b in ink_cols:
        img[120:330, a:b] = 0
        if gaps:  # scanned: the line is broken in places
            img[150:175, a:b] = 255
    systems = toc.page_systems(img)
    return img < toc.INK, systems[0]


def test_engraved_thin_barline_is_single():
    """Anti-aliased engraved barlines render ~3 px wide: still a single bar."""
    ink, system = _barline_system(_page(systems=1), [(737, 740)])
    assert toc.barline_kind(ink, system) == "single"


def test_scanned_broken_final_barline():
    """Scans break barlines; thin + thick still reads as a final barline."""
    ink, system = _barline_system(_page(systems=1), [(733, 734), (736, 740)], gaps=True)
    assert toc.barline_kind(ink, system) == "final"


def test_skewed_scan_is_straightened():
    """A page scanned 1.5° off still has its staves found."""
    gray = _page(systems=3)
    skewed = np.asarray(Image.fromarray(gray).rotate(1.5, fillcolor=255))
    assert toc.find_staves(skewed) == [] or len(toc.find_staves(skewed)) < 6
    assert abs(toc.skew_angle(skewed) + 1.5) <= 0.25
    data = _pdf_from_pages(skewed)
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        assert len(toc.page_systems(toc._render_gray(pdf[0]))) == 3
    finally:
        pdf.close()


def test_dense_page_staff_threshold():
    """Busy music fills many rows past the base threshold; a threshold
    relative to the fullest row still separates the five lines."""
    gray = _page(systems=2)
    lines = np.flatnonzero((gray < toc.INK).mean(axis=1) > 0.5)
    # Dense notes: every row inside each staff inked over ~35% of the width,
    # so at the base threshold each staff is one solid band.
    for y in lines:
        if y + 10 in lines:
            gray[y + 1 : y + 10, 100:380] = 0
    assert toc._staves_from_fill(gray < toc.INK, (gray < toc.INK).mean(axis=1)) == []
    assert len(toc.find_staves(gray)) == 4


def test_sparse_outline_gets_detected_movements(monkeypatch):
    """An outline listing whole works only (one entry per many pages) keeps
    its entries and gains the titled movements detected inside them."""
    pages = [_page(systems=2, final=(1,) if k == 2 else ()) for k in range(8)]
    writer = PdfWriter(clone_from=io.BytesIO(_pdf_from_pages(*pages)))
    writer.add_outline_item("Sonata No. 1", 0)
    buf = io.BytesIO()
    writer.write(buf)
    heads = {1: ("Sonata I", ""), 5: ("Menuetto", "")}
    calls = iter(range(1, 9))
    monkeypatch.setattr(
        toc, "ocr_headings", lambda gray, systems: _ocr(*heads.get(next(calls), ("", "")))
    )
    sections = toc.extract_sections(buf.getvalue())
    # Page 1's own heading is the outline entry; page 4's barline-only start
    # is left out; page 5's Menuetto is added.
    assert [(s.page, s.title, s.source) for s in sections] == [
        (1, "Sonata No. 1", "outline"),
        (5, "Menuetto", "ocr"),
    ]
    assert [s.level for s in sections] == [0, 1]
    assert all(s.incipit_png for s in sections)


def test_indented_first_systems_open_sections(monkeypatch):
    """Editions indent each piece's first system: an indented system opens a
    section (even under a bare tempo word after a misread barline), and
    once the edition is known to do so, a final barline alone doesn't."""
    data = _pdf_from_pages(
        _page(systems=2, indent=(0,), final=(1,)),
        _page(systems=2, indent=(1,), final=(1,)),
        _page(systems=2),
        _page(systems=2, indent=(0,)),
    )
    heads = iter([_ocr("", ""), _ocr("", ""), _ocr("", ""), _ocr("Allegro", "")])
    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: next(heads))
    sections = toc.extract_sections(data)
    assert [(s.page, s.source, s.title) for s in sections] == [
        (1, "layout", "1"),
        (2, "layout", "2"),
        (4, "ocr", "Allegro"),
    ]


def test_partial_system_is_not_an_indent():
    """A system starting far right (a line continued after a page turn) is
    not a piece's indented first system."""
    gray = _page(systems=2)
    info = toc._PageInfo(1, gray.shape, toc.page_systems(gray), [])
    info.systems[1].staves[0].left = 400
    assert toc._indented([info]) == set()
    assert toc._indented([toc._PageInfo(1, gray.shape, [], [])]) == set()


def test_stray_and_prose_titles_are_dropped(monkeypatch):
    """A lone lowercase word ("air" inside the music) or a footnote is no
    title: the start, if any, is barline-only."""
    data = _pdf_from_pages(_page(systems=1), _page(systems=1))
    long_note = "In case the character of the instrument permits, the soft pedal may be used"
    heads = iter([_ocr("air"), _ocr(long_note + " sonatas")])
    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: next(heads))
    assert [(s.page, s.source) for s in toc.extract_sections(data)] == [(1, "layout")]
    assert toc.tidy_title(long_note) == ""


# --- pieces and their movements ---------------------------------------------


def test_ocr_title_reads_the_area_above_the_first_heading(monkeypatch):
    """The title area is read only when the music starts low on the page."""
    margin = np.vstack([np.full((300, 800), 255, dtype=np.uint8), _page(systems=2)])
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(Image.open(io.BytesIO(kwargs["input"])).height)
        return subprocess.CompletedProcess(cmd, 0, stdout=_tsv((40, "SONATA."), (0, "3")))

    monkeypatch.setattr(toc.subprocess, "run", fake_run)
    title = toc.ocr_title(margin, toc.page_systems(margin))
    assert title.text == "3 SONATA."
    # Up to the first system's heading band (420 - 2.5 staff heights), upscaled.
    assert calls == [(420 - 100) * toc.OCR_UPSCALE]

    gray = _page(systems=2)  # music right at the top: nothing to read
    assert toc.ocr_title(gray, toc.page_systems(gray)) == toc.OcrText()
    assert toc.ocr_title(gray, []) == toc.OcrText()
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SONATA. 19 Abbreviations: M.T. signifies Main Theme; Ep.", "Sonata"),
        ("SONATA 50 Abbreviations M.T. signifies", "Sonata 50"),
        ("11 NOCTURNE No 2 Andantino espressivo cantando Op. 33, No. 2", "Nocturne No. 2"),
        ("N O C T U R N E No.7 lento", "Nocturne No. 7"),
        ("Partita II Allemande", "Partita II"),
        ("Sonata in C", "Sonata"),
        ("Sonata", "Sonata"),
        ("Index. Vol.I.", ""),
        ("parts of a sonata", ""),
        ("Rondo Brillante, Op. 29. 52 Sonatinas Op. 55", ""),
        ("", ""),
    ],
)
def test_title_piece(raw, expected):
    assert toc.title_piece(raw) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Sonata No. 1 — Allegro", ("Sonata No. 1", "Allegro")),
        ("Fuga 2", ("Fuga 2", "")),
        ("Allegro", ("", "Allegro")),
        ("La Follette — Rondeau", ("", "La Follette — Rondeau")),
        ("", ("", "")),
    ],
)
def test_split_piece(title, expected):
    assert toc.split_piece(title) == expected


@pytest.mark.parametrize(
    ("pieces", "expected"),
    [
        # Bare titles are counted; "19" (a page number) doesn't follow on.
        (["Sonata", "", "Sonata 19", "Sonata"], ["Sonata 1", "", "Sonata 2", "Sonata 3"]),
        (["Sonata No. 17", "Sonata No. 18"], ["Sonata No. 17", "Sonata No. 18"]),
        (["Sonata No. 3", "Sonata"], ["Sonata No. 3", "Sonata 4"]),
        (["Partita I", "Partita II"], ["Partita I", "Partita II"]),
        (["Sonata", "Fuga"], ["Sonata", "Fuga"]),
        (
            ["Sonata No. 8 “Pathétique”", "Sonata No. 9"],
            ["Sonata No. 8 “Pathétique”", "Sonata No. 9"],
        ),
    ],
)
def test_number_pieces(pieces, expected):
    assert toc.number_pieces(pieces) == expected


def _nested(heads):
    return [(e.start, e.title, e.level, e.incipit) for e in toc.nest_entries(heads)]


def test_nest_entries_flat_without_pieces():
    assert _nested([("", "Allegro"), ("", ""), ("", "Var. 2")]) == [
        (0, "Allegro", 0, True),
        (1, "", 0, True),
        (2, "Var. 2", 0, True),
    ]


def test_nest_entries_sonatas_and_movements():
    """Sonatas list their movements; untitled starts and variations under a
    piece are dropped, a heading before the first piece title stays."""
    heads = [
        ("", ""),
        ("", "Rondo"),
        ("Sonata", "Allegro"),
        ("", "Adagio"),
        ("", ""),
        ("", "var. 4"),
        ("", "Var.I"),
        ("Sonata 19", "Presto"),
        ("", "Sonata — Menuetto"),
    ]
    assert _nested(heads) == [
        (1, "Rondo", 0, True),
        (2, "Sonata 1", 0, True),
        (2, "Allegro", 1, False),
        (3, "Adagio", 1, True),
        (7, "Sonata 2", 0, True),
        (7, "Presto", 1, False),
        (8, "Sonata 3", 0, True),
        (8, "Menuetto", 1, False),
    ]


def test_nest_entries_one_work_titled_over_each_movement():
    """The Pathétique's title tops all three movements: one sonata, three
    movements (quote styles differ between pages)."""
    heads = [
        ("", "Sonata No. 8 “Pathétique” — Grave"),
        ("", 'Sonata No. 8 "Pathétique" — Adagio cantabile'),
        ("", 'Sonata No. 8 "Pathétique" — Rondo'),
        ("", "Sonata No. 9 — Allegro"),
    ]
    assert _nested(heads) == [
        (0, "Sonata No. 8 “Pathétique”", 0, True),
        (0, "Grave", 1, False),
        (1, "Adagio cantabile", 1, True),
        (2, "Rondo", 1, True),
        (3, "Sonata No. 9", 0, True),
        (3, "Allegro", 1, False),
    ]


def test_nest_entries_single_movement_pieces():
    """A nocturne's opening tempo is not a movement; a sonata's is, even alone."""
    heads = [
        ("Nocturne No. 1", "Lento"),
        ("Nocturne No. 2", "Nocturne No. 2"),
        ("", "Fuga 3"),
        ("Sonata", "Moderato"),
    ]
    assert _nested(heads) == [
        (0, "Nocturne No. 1", 0, True),
        (1, "Nocturne No. 2", 0, True),
        (2, "Fuga 3", 0, True),
        (3, "Sonata", 0, True),
        (3, "Moderato", 1, False),
    ]


def test_extract_sections_nests_movements_under_pieces(monkeypatch):
    """A volume of sonatas: each "SONATA." title area opens a piece, its
    tempo headings are its movements; a running title over music that
    carries on (single barline before it) opens nothing."""
    data = _pdf_from_pages(
        _page(systems=2),
        _page(systems=2, final=(1,)),
        _page(systems=2, final=(1,)),
        _page(systems=2),
        _page(systems=2),
    )
    heads = iter(
        [_ocr("Allegro", ""), _ocr("", ""), _ocr("Adagio", ""), _ocr("", ""), _ocr("", "")]
    )
    titles = iter(["SONATA. 3 Abbreviations", "SONATA.", "", "SONATA.", "SONATA. 5"])
    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: next(heads))
    monkeypatch.setattr(toc, "ocr_title", lambda gray, systems: toc.OcrText(next(titles)))
    sections = toc.extract_sections(data)
    assert [(s.page, s.title, s.level, s.source, bool(s.incipit_png)) for s in sections] == [
        (1, "Sonata 1", 0, "ocr", True),
        (1, "Allegro", 1, "ocr", False),
        (3, "Adagio", 1, "ocr", True),
        (4, "Sonata 2", 0, "ocr", True),
    ]


def test_render_scale_is_capped_and_absurd_pages_skipped():
    """A page's render stays under MAX_RENDER_PX; giant or empty MediaBoxes
    aren't rendered at all."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument.new()
    for size in ((595, 842), (10000, 5000), (20000, 800)):
        pdf.new_page(*size)
    try:
        assert toc.render_scale(pdf[0]) == toc.RENDER_DPI / 72
        assert toc.render_scale(pdf[1]) == toc.MAX_RENDER_PX / 10000
        assert toc.render_scale(pdf[2]) is None
        assert max(toc._render_gray(pdf[1]).shape) <= toc.MAX_RENDER_PX
        assert toc.page_systems(toc._render_gray(pdf[2])) == []
    finally:
        pdf.close()


def test_extract_sections_page_and_time_limits():
    """Past the page cap or the time budget, the job stops with what it found."""
    data = (DATA / "engraved.pdf").read_bytes()
    assert toc.extract_sections(data)
    assert toc.extract_sections(data, max_pages=0) == []
    assert toc.extract_sections(data, time_budget=-1) == []


def test_outline_volumes_get_a_larger_page_cap(monkeypatch):
    """A PDF with a real outline is scanned up to OUTLINE_MAX_PAGES, others
    up to MAX_PAGES; outline entries are kept either way."""
    pages = [_page(systems=2) for _ in range(8)]
    writer = PdfWriter(clone_from=io.BytesIO(_pdf_from_pages(*pages)))
    writer.add_outline_item("Sonata No. 1", 0)
    buf = io.BytesIO()
    writer.write(buf)
    seen = []
    monkeypatch.setattr(toc, "ocr_headings", lambda gray, systems: seen.append(1) or _ocr("", ""))
    sections = toc.extract_sections(buf.getvalue(), max_pages=0, outline_max_pages=8)
    assert [s.title for s in sections] == ["Sonata No. 1"]
    assert len(seen) == 8  # max_pages=0 is for PDFs without an outline
    # Out of time: the outline is still listed, just without incipits.
    sections = toc.extract_sections(buf.getvalue(), time_budget=-1)
    assert [(s.title, s.incipit_png) for s in sections] == [("Sonata No. 1", None)]
