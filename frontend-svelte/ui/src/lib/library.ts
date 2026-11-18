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
