import type { Period, Score } from '#lib/types.js';

export interface Tally {
	name: string;
	count: number;
}

export interface LibrarySummary {
	total: number;
	composers: number;
	plays: number;
	/** Composers with the most plays (or the most scores before any play). */
	topComposers: Tally[];
	/** Number of scores per period, in historical order. */
	periods: { name: Period; count: number }[];
	/** Last opened first; falls back to the latest additions. */
	continue: Score[];
	continueIsRecent: boolean;
	mostPlayed: Score[];
}

const PERIOD_ORDER: Period[] = [
	'Medieval',
	'Renaissance',
	'Baroque',
	'Classical',
	'Romantic',
	'Modernist',
	'Postmodernist'
];

/** "Chopin, Frédéric" -> "Frédéric Chopin". */
export function composerName(composer: string): string {
	const [last, first] = composer.split(',').map((p) => p.trim());
	return first ? `${first} ${last}` : (last ?? '');
}

function top(counts: Map<string, number>, n: number): Tally[] {
	return [...counts]
		.map(([name, count]) => ({ name, count }))
		.filter((t) => t.count > 0)
		.sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
		.slice(0, n);
}

/** What the home page says about the user's library and playing habits. */
export function summarizeLibrary(scores: Score[], limit = 4): LibrarySummary {
	const plays = scores.reduce((sum, s) => sum + (s.number_of_plays || 0), 0);
	const byComposer = new Map<string, number>();
	const byPeriod = new Map<Period, number>();
	for (const score of scores) {
		const name = composerName(score.composer);
		if (name) {
			const weight = plays ? score.number_of_plays || 0 : 1;
			byComposer.set(name, (byComposer.get(name) ?? 0) + weight);
		}
		if (score.period) byPeriod.set(score.period, (byPeriod.get(score.period) ?? 0) + 1);
	}
	const played = scores
		.filter((s) => s.last_played_at)
		.sort((a, b) => String(b.last_played_at).localeCompare(String(a.last_played_at)));
	const recent = [...scores].sort((a, b) => b.id - a.id);
	return {
		total: scores.length,
		composers: new Set(scores.map((s) => composerName(s.composer)).filter(Boolean)).size,
		plays,
		topComposers: top(byComposer, 5),
		periods: PERIOD_ORDER.filter((p) => byPeriod.has(p)).map((name) => ({
			name,
			count: byPeriod.get(name)!
		})),
		continue: (played.length ? played : recent).slice(0, limit),
		continueIsRecent: played.length === 0,
		mostPlayed: scores
			.filter((s) => s.number_of_plays > 0)
			.sort((a, b) => b.number_of_plays - a.number_of_plays || a.title.localeCompare(b.title))
			.slice(0, 3)
	};
}

// --- Browsing the library (/db-viewer) ----------------------------------------

/** The facets the library can be narrowed by (each a set of chosen values). */
export const FACETS = ['composer', 'period', 'genre', 'form', 'key'] as const;
export type Facet = (typeof FACETS)[number];

export interface LibraryFilters {
	query: string;
	composer: string[];
	period: string[];
	genre: string[];
	form: string[];
	key: string[];
	yearMin: number | null;
	yearMax: number | null;
	favorites: boolean;
}

export const emptyFilters = (): LibraryFilters => ({
	query: '',
	composer: [],
	period: [],
	genre: [],
	form: [],
	key: [],
	yearMin: null,
	yearMax: null,
	favorites: false
});

export function hasFilters(f: LibraryFilters): boolean {
	return (
		f.query.trim() !== '' ||
		FACETS.some((k) => f[k].length > 0) ||
		f.yearMin !== null ||
		f.yearMax !== null ||
		f.favorites
	);
}

export const SORTS = ['composer', 'title', 'year', 'plays', 'played', 'added'] as const;
export type SortKey = (typeof SORTS)[number];
export interface LibrarySort {
	key: SortKey;
	desc: boolean;
}
/** The natural direction of each sort: names A→Z, the rest newest / most first. */
export const SORT_DESC: Record<SortKey, boolean> = {
	composer: false,
	title: false,
	year: false,
	plays: true,
	played: true,
	added: true
};

/** Lower case, accents dropped: "Étude" matches "etude". */
export function fold(text: string): string {
	return text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
}

/** The facet value a score is filed under ("" when it has none). */
export function facetValue(score: Score, facet: Facet): string {
	return facet === 'composer' ? composerName(score.composer) : String(score[facet] ?? '');
}

const haystacks = new WeakMap<Score, string>();
function haystack(score: Score): string {
	let text = haystacks.get(score);
	if (text === undefined) {
		text = fold(
			[
				score.title,
				score.composer,
				composerName(score.composer),
				score.instrumentation,
				score.genre,
				score.form,
				score.key,
				score.style,
				score.period,
				score.year ? String(score.year) : ''
			].join(' ')
		);
		haystacks.set(score, text);
	}
	return text;
}

/** Every word of the query is somewhere in the score ("chopin noc", "bwv 846"). */
export function matchesQuery(score: Score, query: string): boolean {
	const words = fold(query).split(/\s+/).filter(Boolean);
	if (!words.length) return true;
	const text = haystack(score);
	return words.every((w) => text.includes(w));
}

function matches(score: Score, f: LibraryFilters, skip?: Facet): boolean {
	if (f.favorites && !score.favorite) return false;
	if (f.yearMin !== null && !(score.year >= f.yearMin)) return false;
	if (f.yearMax !== null && !(score.year <= f.yearMax)) return false;
	for (const facet of FACETS) {
		if (facet !== skip && f[facet].length && !f[facet].includes(facetValue(score, facet)))
			return false;
	}
	return matchesQuery(score, f.query);
}

export function filterScores(scores: Score[], f: LibraryFilters): Score[] {
	return scores.filter((s) => matches(s, f));
}

/**
 * How many scores each value of ``facet`` would show, given every other
 * filter: choosing "Romantic" still lists the other periods with their counts.
 * Values chosen but matching nothing stay listed (with 0) so they can be unticked.
 */
export function facetCounts(scores: Score[], facet: Facet, f: LibraryFilters): Tally[] {
	const counts = new Map<string, number>(f[facet].map((v) => [v, 0]));
	for (const score of scores) {
		const value = facetValue(score, facet);
		if (value && matches(score, f, facet)) counts.set(value, (counts.get(value) ?? 0) + 1);
	}
	const tallies = [...counts].map(([name, count]) => ({ name, count }));
	if (facet === 'period') {
		const order = (name: string) => {
			const i = PERIOD_ORDER.indexOf(name as Period);
			return i < 0 ? PERIOD_ORDER.length : i;
		};
		return tallies.sort((a, b) => order(a.name) - order(b.name));
	}
	if (facet === 'composer') {
		return tallies.sort((a, b) => composerSortKey(a.name).localeCompare(composerSortKey(b.name)));
	}
	return tallies.sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

/** "Frédéric Chopin" / "Chopin, Frédéric" -> "chopin frederic": sorted by family name. */
export function composerSortKey(composer: string): string {
	const [family, given] = composer.split(',').map((p) => p.trim());
	if (given) return fold(`${family} ${given}`);
	const parts = composer.trim().split(/\s+/);
	// "Johann Sebastian Bach" -> "bach johann sebastian"; particles stay with
	// the first names ("Ludwig van Beethoven" -> "beethoven ludwig van").
	const last = parts.pop() ?? '';
	return fold([last, ...parts].join(' '));
}

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

export function sortScores(scores: Score[], sort: LibrarySort): Score[] {
	const sign = sort.desc ? -1 : 1;
	const byTitle = (a: Score, b: Score) => collator.compare(a.title, b.title);
	const compare: Record<SortKey, (a: Score, b: Score) => number> = {
		composer: (a, b) => collator.compare(composerSortKey(a.composer), composerSortKey(b.composer)),
		title: byTitle,
		year: (a, b) => (a.year || 0) - (b.year || 0),
		plays: (a, b) => (a.number_of_plays || 0) - (b.number_of_plays || 0),
		played: (a, b) => String(a.last_played_at ?? '').localeCompare(String(b.last_played_at ?? '')),
		added: (a, b) => a.id - b.id
	};
	return [...scores].sort((a, b) => sign * compare[sort.key](a, b) || byTitle(a, b));
}

export interface ScoreGroup {
	/** The composer's name, or "" when the list isn't grouped. */
	heading: string;
	scores: Score[];
}

/** Consecutive scores of one composer under one heading (when sorted by composer). */
export function groupByComposer(scores: Score[], grouped: boolean): ScoreGroup[] {
	if (!grouped) return scores.length ? [{ heading: '', scores }] : [];
	const groups: ScoreGroup[] = [];
	for (const score of scores) {
		const heading = composerName(score.composer);
		const last = groups.at(-1);
		if (last && last.heading === heading) last.scores.push(score);
		else groups.push({ heading, scores: [score] });
	}
	return groups;
}

/** The last opened scores, most recent first. */
export function recentlyPlayed(scores: Score[], limit = 6): Score[] {
	return scores
		.filter((s) => s.last_played_at)
		.sort((a, b) => String(b.last_played_at).localeCompare(String(a.last_played_at)))
		.slice(0, limit);
}
