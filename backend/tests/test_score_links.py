"""Linking the library scores an assistant answer mentions."""

from app.score_links import catalogue_numbers, link_scores, normalize
from shared.responses import Response
from shared.scores import Score, Scores

LIBRARY = Scores(
    scores=[
        Score(
            id=17, title="Piano Sonata No.16 in C major, K.545", composer="Mozart, Wolfgang Amadeus"
        ),
        Score(id=3, title="Prelude in E minor, Op.28 No.4", composer="Frédéric Chopin"),
        Score(id=4, title="Nocturne, Op.9 No.2", composer="Chopin, Frédéric"),
        Score(id=5, title="Gymnopédie No.1", composer="Erik Satie"),
        Score(id=6, title="Prelude and Fugue in C major, BWV 846", composer="J.S. Bach"),
        Score(id=7, title="Sonata", composer="Someone, Else"),
    ]
)


def _link(text: str, **ids) -> Response:
    return link_scores(Response(response=text, **ids), LIBRARY)


def test_normalize_and_catalogue_numbers():
    assert normalize("Sonate n° 16 en ut majeur, K. 545 — Gymnopédie") == (
        "sonate n 16 en ut majeur k 545 gymnopedie"
    )
    assert catalogue_numbers(normalize("Op. 28 No. 4, KV 545, BWV846, opus 9")) == {
        ("op", "28", "4"), ("k", "545", None), ("bwv", "846", None), ("op", "9", None),
    }  # fmt: skip


def test_valid_ids_are_kept_and_invented_ones_dropped():
    assert _link("here", score_id=17).score_id == 17
    out = _link("here", score_id=999, score_ids=[3, 999, 4])
    assert (out.score_id, out.score_ids) == (None, [3, 4])


def test_finds_a_piece_named_in_another_language():
    out = _link("Voici un Mozart facile : la Sonate pour piano n° 16 en ut majeur, K. 545.")
    assert (out.score_id, out.score_ids) == (17, None)


def test_opus_numbers_need_the_composer_and_matching_sub_number():
    assert _link("Le Prélude op. 28 n° 4 de Chopin").score_id == 3
    assert _link("Le Prélude op. 28 n° 4").score_id is None  # opus alone is ambiguous
    assert _link("Chopin, op. 28 no. 7").score_id is None  # another prelude


def test_several_mentions_and_full_titles():
    out = _link("Try Gymnopédie No.1 or BWV 846.")
    assert (out.score_id, sorted(out.score_ids or [])) == (None, [5, 6])
    assert _link("A sonata, maybe?").score_ids is None  # short titles don't match


def test_an_id_written_in_the_text():
    assert _link("Voici le score que tu peux jouer : 17.").score_id == 17
    assert _link("Voici le score : 999.").score_id is None
    assert _link("Ids 17 and 3").score_id is None  # several numbers: don't guess
