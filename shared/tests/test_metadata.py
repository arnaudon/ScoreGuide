import pytest

from shared.metadata import (
    FORMS,
    GENRES,
    MIXED_KEY,
    normalize_form,
    normalize_genre,
    normalize_key,
    tidy_style,
)
from shared.scores import ScoreCreate, ScoreUpdate


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Piano Sonata", "Sonata"),
        ("sonatina", "Sonatina"),
        ("Preludes and Fugues", "Prelude and fugue"),
        ("Prélude", "Prelude"),
        ("Études", "Étude"),
        ("Sinfonia", "Invention"),
        ("Gavotte", "Dance"),
        ("Bagatelle", "Character piece"),
        ("6 Klavierstücke", "Character piece"),
        ("Pièces de clavecin", "Collection"),
        ("Variations", "Variations"),
        ("concerto", "Concerto"),
        ("something else", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_form(value, expected):
    assert normalize_form(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Solo keyboard", "Solo keyboard"),
        ("Piano pieces", "Solo keyboard"),
        ("String Quartet", "Chamber"),
        ("Symphony", "Orchestral"),
        ("Mass", "Choral"),
        ("Lieder", "Vocal"),
        ("Classical", ""),
        ("Nocturnes", ""),
        (3, ""),
    ],
)
def test_normalize_genre(value, expected):
    assert normalize_genre(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("D minor", "D minor"),
        (" F-sharp minor ", "F-sharp minor"),
        ("A minor, A major, G minor", MIXED_KEY),
        ("Various", MIXED_KEY),
        ("All 24 major and minor keys", MIXED_KEY),
        ("E minor / D major", MIXED_KEY),
        (["A minor", "A major"], MIXED_KEY),
        (["C major", "C major"], "C major"),
        ([], ""),
        ("unknown", ""),
        (None, ""),
    ],
)
def test_normalize_key(value, expected):
    assert normalize_key(value) == expected


@pytest.mark.parametrize(
    ("style", "period", "expected"),
    [
        ("Baroque", "Baroque", ""),
        ("Classical / Romantic", "", ""),
        ("Late Romantic", "Romantic", ""),
        ("French Baroque", "Baroque", "French Baroque"),
        ("lyrical, virtuosic", "", "lyrical, virtuosic"),
        (None, "", ""),
    ],
)
def test_tidy_style(style, period, expected):
    assert tidy_style(style, period) == expected


def test_every_canonical_value_maps_to_itself():
    assert all(normalize_genre(g) == g for g in GENRES)
    assert all(normalize_form(f) == f for f in FORMS)


def test_score_writes_are_normalized():
    created = ScoreCreate(
        title="t", composer="c", genre="Piano", form="Piano Sonata", key="Various", style="Baroque"
    )
    assert (created.genre, created.form, created.key, created.style) == (
        "Solo keyboard",
        "Sonata",
        MIXED_KEY,
        "",
    )
    assert ScoreCreate(title="t", composer="c").form == ""
    update = ScoreUpdate(form="Nocturnes")
    assert update.form == "Nocturne" and update.genre is None and update.key is None
