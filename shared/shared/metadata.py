"""A small, fixed vocabulary for a score's genre, form and key.

The completion agent picks from these lists and every write goes through the
``normalize_*`` helpers, so the library can be filtered and shown consistently:
"Piano Sonata" is the form "Sonata", a collection in many keys has the key
"Mixed", and a style that only repeats the period is dropped.
"""

import re
import unicodedata

# What kind of work, by its forces (instrumentation keeps the details).
GENRES = (
    "Solo keyboard",
    "Solo instrument",
    "Chamber",
    "Concerto",
    "Orchestral",
    "Vocal",
    "Choral",
    "Opera",
    "Other",
)

# The form of the piece; a set of pieces sharing one form takes that form,
# a set mixing forms is a "Collection".
FORMS = (
    "Sonata",
    "Sonatina",
    "Suite",
    "Variations",
    "Prelude",
    "Fugue",
    "Prelude and fugue",
    "Invention",
    "Étude",
    "Nocturne",
    "Waltz",
    "Mazurka",
    "Polonaise",
    "Ballade",
    "Scherzo",
    "Impromptu",
    "Rondo",
    "Fantasia",
    "Toccata",
    "Dance",
    "Character piece",
    "Concerto",
    "Symphony",
    "Song",
    "Collection",
    "Other",
)

MIXED_KEY = "Mixed"

# Words that point to a canonical value (accents and case ignored, matched at
# the start of a word, so "Sonatas" needs no entry of its own).
_GENRE_WORDS: dict[str, tuple[str, ...]] = {
    "Solo keyboard": (
        "solo keyboard",
        "keyboard",
        "piano",
        "klavier",
        "clavier",
        "harpsichord",
        "clavecin",
        "organ",
        "orgue",
    ),
    "Solo instrument": ("solo instrument",),
    "Chamber": ("chamber", "duo", "trio", "quartet", "quintet", "sextet", "septet", "octet"),
    "Concerto": ("concert",),
    "Orchestral": ("orchest", "symphon"),
    "Vocal": ("vocal", "song", "lied", "melodie", "aria"),
    "Choral": (
        "choral",
        "choir",
        "chorus",
        "mass",
        "messe",
        "motet",
        "requiem",
        "cantata",
        "oratorio",
    ),
    "Opera": ("opera",),
    "Other": ("other",),
}

_FORM_WORDS: dict[str, tuple[str, ...]] = {
    # Longer names first: "prelude and fugue" before "prelude", "sonatina" before "sonata".
    "Prelude and fugue": (
        "prelude and fugue",
        "preludes and fugues",
        "prelude & fugue",
        "preludes & fugues",
        "praeludium und fuge",
    ),
    "Character piece": (
        "character piece",
        "charakterstuck",
        "lyric piece",
        "song without words",
        "lieder ohne worte",
        "intermezz",
        "romance",
        "bagatelle",
        "moment musical",
        "album leaf",
        "gymnoped",
        "albumblatt",
        "klavierstuck",
        "piano piece",
    ),
    "Sonatina": ("sonatin",),
    "Sonata": ("sonat",),
    "Suite": ("suite", "partita", "ordre", "english suite", "french suite"),
    "Variations": ("variation", "chaconne", "passacaglia", "doubles"),
    "Prelude": ("prelud", "praelud"),
    "Fugue": ("fugue", "fuga", "fuge"),
    "Invention": ("invention", "sinfonia"),
    "Étude": ("etude", "study", "studies"),
    "Nocturne": ("nocturne", "notturno"),
    "Waltz": ("waltz", "valse", "walzer"),
    "Mazurka": ("mazurka",),
    "Polonaise": ("polonaise",),
    "Ballade": ("ballad",),
    "Scherzo": ("scherz",),
    "Impromptu": ("impromptu",),
    "Rondo": ("rondo",),
    "Fantasia": ("fantas", "phantas"),
    "Toccata": ("toccata",),
    "Dance": (
        "dance",
        "gavotte",
        "minuet",
        "menuet",
        "sarabande",
        "gigue",
        "allemande",
        "courante",
        "bourree",
        "pavane",
        "galliard",
        "tango",
        "ecossaise",
        "landler",
    ),
    "Concerto": ("concert",),
    "Symphony": ("symphon",),
    "Song": ("song", "lied", "melodie"),
    "Collection": ("collection", "set of", "album", "cycle", "pieces", "stucke"),
    "Other": ("other",),
}

_PERIOD_WORDS = {
    "medieval",
    "renaissance",
    "baroque",
    "classical",
    "classic",
    "romantic",
    "late",
    "early",
    "high",
    "modern",
    "modernist",
    "postmodernist",
    "contemporary",
    "20th",
    "century",
    "and",
}


def _plain(text: str) -> str:
    """Lowercase, accents removed, spaces collapsed."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def _match(value: object, words: dict[str, tuple[str, ...]], canonical: tuple[str, ...]) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    plain = _plain(value)
    for name in canonical:
        if plain == _plain(name):
            return name
    for name, stems in words.items():
        if any(re.search(rf"(?<![a-z]){re.escape(stem)}", plain) for stem in stems):
            return name
    return ""


def normalize_genre(value: object) -> str:
    """One of ``GENRES``, or "" when the value names none of them."""
    return _match(value, _GENRE_WORDS, GENRES)


def normalize_form(value: object) -> str:
    """One of ``FORMS``, or "" when the value names none of them."""
    return _match(value, _FORM_WORDS, FORMS)


def normalize_key(value: object) -> str:
    """A single key, ``MIXED_KEY`` for a set of pieces in several keys, or ""."""
    if isinstance(value, list | tuple):
        keys = {str(v).strip() for v in value if str(v).strip()}
        if len(keys) > 1:
            return MIXED_KEY
        value = next(iter(keys), "")
    if not isinstance(value, str):
        return ""
    value = value.strip()
    plain = _plain(value)
    if not plain or plain in {"unknown", "n/a", "none", "-"}:
        return ""
    if re.search(r"[,;/]| and | et |various|varied|mixed|divers|all |\d+ keys", plain):
        return MIXED_KEY
    return value


def tidy_style(style: object, period: object = "") -> str:
    """The style, or "" when it only repeats a period ("Classical / Romantic")."""
    if not isinstance(style, str):
        return ""
    style = style.strip()
    words = {w for w in re.split(r"[\s/,&+-]+", _plain(style)) if w}
    if period and isinstance(period, str):
        words.discard(_plain(period))
    return "" if words <= _PERIOD_WORDS else style
