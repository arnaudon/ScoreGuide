import * as m from '#lib/paraglide/messages.js';

// The fixed vocabulary of the backend's shared/metadata.py (same values, same
// order): the stored values are English, shown here in the user's language.
const GENRE_LABELS: Record<string, () => string> = {
	'Solo keyboard': m.genre_solo_keyboard,
	'Solo instrument': m.genre_solo_instrument,
	Chamber: m.genre_chamber,
	Concerto: m.genre_concerto,
	Orchestral: m.genre_orchestral,
	Vocal: m.genre_vocal,
	Choral: m.genre_choral,
	Opera: m.genre_opera,
	Other: m.genre_other
};

const FORM_LABELS: Record<string, () => string> = {
	Sonata: m.form_sonata,
	Sonatina: m.form_sonatina,
	Suite: m.form_suite,
	Variations: m.form_variations,
	Prelude: m.form_prelude,
	Fugue: m.form_fugue,
	'Prelude and fugue': m.form_prelude_fugue,
	Invention: m.form_invention,
	Étude: m.form_etude,
	Nocturne: m.form_nocturne,
	Waltz: m.form_waltz,
	Mazurka: m.form_mazurka,
	Polonaise: m.form_polonaise,
	Ballade: m.form_ballade,
	Scherzo: m.form_scherzo,
	Impromptu: m.form_impromptu,
	Rondo: m.form_rondo,
	Fantasia: m.form_fantasia,
	Toccata: m.form_toccata,
	Dance: m.form_dance,
	'Character piece': m.form_character_piece,
	Concerto: m.form_concerto,
	Symphony: m.form_symphony,
	Song: m.form_song,
	Collection: m.form_collection,
	Other: m.form_other
};

export const GENRES = Object.keys(GENRE_LABELS);
export const FORMS = Object.keys(FORM_LABELS);
export const MIXED_KEY = 'Mixed';

/** A stored value outside the vocabulary (older data) is shown as is. */
export const genreLabel = (value: string) => GENRE_LABELS[value]?.() ?? value;
export const formLabel = (value: string) => FORM_LABELS[value]?.() ?? value;
export const keyLabel = (value: string) => (value === MIXED_KEY ? m.key_mixed() : value);
