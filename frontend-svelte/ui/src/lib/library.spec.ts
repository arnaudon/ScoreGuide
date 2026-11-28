import { describe, it, expect } from 'vitest';
import {
	composerName,
	composerSortKey,
	emptyFilters,
	facetCounts,
	filterScores,
	fold,
	groupByComposer,
	hasFilters,
	matchesQuery,
	recentlyPlayed,
	sortScores,
	summarizeLibrary
} from './library.js';
import type { Score } from './types.js';

const score = (id: number, over: Partial<Score> = {}): Score =>
	({
		id,
		title: `Piece ${id}`,
		composer: 'Bach, Johann Sebastian',
		period: 'Baroque',
		number_of_plays: 0,
		last_played_at: null,
		...over
	}) as Score;

describe('composerName', () => {
	it('puts the first name first', () => {
		expect(composerName('Chopin, Frédéric')).toBe('Frédéric Chopin');
		expect(composerName('Anonymous')).toBe('Anonymous');
		expect(composerName('')).toBe('');
	});
});

describe('summarizeLibrary', () => {
	it('counts scores per composer and suggests the latest additions before any play', () => {
		const s = summarizeLibrary([
			score(1),
			score(2),
			score(3, { composer: 'Chopin, Frédéric', period: 'Romantic' }),
			score(4, { composer: '' })
		]);
		expect(s.total).toBe(4);
		expect(s.composers).toBe(2);
		expect(s.plays).toBe(0);
		expect(s.topComposers).toEqual([
			{ name: 'Johann Sebastian Bach', count: 2 },
			{ name: 'Frédéric Chopin', count: 1 }
		]);
		expect(s.periods).toEqual([
			{ name: 'Baroque', count: 3 },
			{ name: 'Romantic', count: 1 }
		]);
		expect(s.continueIsRecent).toBe(true);
		expect(s.continue.map((x) => x.id)).toEqual([4, 3, 2, 1]);
		expect(s.mostPlayed).toEqual([]);
	});

	it('ranks by plays once the user has played', () => {
		const s = summarizeLibrary(
			[
				score(1, { number_of_plays: 1, last_played_at: '2026-11-01T10:00:00' }),
				score(2, {
					composer: 'Chopin, Frédéric',
					number_of_plays: 5,
					last_played_at: '2026-11-18T09:00:00'
				}),
				score(3)
			],
			1
		);
		expect(s.plays).toBe(6);
		expect(s.topComposers).toEqual([
			{ name: 'Frédéric Chopin', count: 5 },
			{ name: 'Johann Sebastian Bach', count: 1 }
		]);
		expect(s.continueIsRecent).toBe(false);
		expect(s.continue.map((x) => x.id)).toEqual([2]);
		expect(s.mostPlayed.map((x) => x.id)).toEqual([2, 1]);
	});
});

describe('browsing the library', () => {
	const lib = [
		score(1, {
			title: 'Étude Op. 10 No. 1',
			composer: 'Chopin, Frédéric',
			period: 'Romantic',
			year: 1830,
			form: 'Étude',
			key: 'C major',
			number_of_plays: 3,
			last_played_at: '2026-01-02T00:00:00'
		}),
		score(2, {
			title: 'Prelude and Fugue BWV 846',
			composer: 'Johann Sebastian Bach',
			period: 'Baroque',
			year: 1722,
			form: 'Prelude and fugue',
			key: 'C major',
			favorite: true
		}),
		score(3, {
			title: 'Nocturne Op. 9 No. 2',
			composer: 'Frédéric Chopin',
			period: 'Romantic',
			year: 1832,
			form: 'Nocturne',
			key: 'E-flat major',
			number_of_plays: 1,
			last_played_at: '2026-03-01T00:00:00'
		}),
		score(4, {
			title: 'Sonata No. 14',
			composer: 'Ludwig van Beethoven',
			period: 'Classical',
			year: 1801,
			form: 'Sonata',
			key: 'C-sharp minor'
		})
	];

	it('folds case and accents', () => {
		expect(fold('Étude Frédéric')).toBe('etude frederic');
	});

	it('matches every word anywhere, accents ignored', () => {
		expect(matchesQuery(lib[0], 'chopin etude')).toBe(true);
		expect(matchesQuery(lib[1], 'bwv 846')).toBe(true);
		expect(matchesQuery(lib[1], 'bwv 847')).toBe(false);
		expect(matchesQuery(lib[3], '  ')).toBe(true);
	});

	it('filters by facets, years and favourites', () => {
		const f = emptyFilters();
		expect(hasFilters(f)).toBe(false);
		const ids = (filters: Partial<typeof f>) =>
			filterScores(lib, { ...f, ...filters }).map((s) => s.id);
		expect(ids({ composer: ['Frédéric Chopin'] })).toEqual([1, 3]);
		expect(ids({ period: ['Romantic', 'Baroque'], key: ['C major'] })).toEqual([1, 2]);
		expect(ids({ yearMin: 1800, yearMax: 1831 })).toEqual([1, 4]);
		expect(ids({ favorites: true })).toEqual([2]);
		expect(ids({ collections: true })).toEqual([]);
		expect(
			filterScores([...lib, score(5, { year: 0, collection: true })], {
				...f,
				collections: true
			}).map((s) => s.id)
		).toEqual([5]);
		// An unknown year (0) is outside any year range.
		expect(filterScores([score(6, { year: 0 })], { ...f, yearMax: 1900 }).map((s) => s.id)).toEqual(
			[]
		);
		expect(hasFilters({ ...f, favorites: true })).toBe(true);
	});

	it('counts each facet under the other filters, keeping chosen values', () => {
		const f = { ...emptyFilters(), period: ['Romantic', 'Medieval'], key: ['C major'] };
		// Periods counted without the period filter, in historical order.
		expect(facetCounts(lib, 'period', f)).toEqual([
			{ name: 'Medieval', count: 0 },
			{ name: 'Baroque', count: 1 },
			{ name: 'Romantic', count: 1 }
		]);
		// Composers sorted by family name.
		expect(facetCounts(lib, 'composer', emptyFilters()).map((t) => t.name)).toEqual([
			'Johann Sebastian Bach',
			'Ludwig van Beethoven',
			'Frédéric Chopin'
		]);
		expect(facetCounts(lib, 'form', emptyFilters())[0].count).toBe(1);
	});

	it('sorts composers by family name', () => {
		expect(composerSortKey('Chopin, Frédéric')).toBe('chopin frederic');
		expect(composerSortKey('Frédéric Chopin')).toBe('chopin frederic');
		expect(composerSortKey('Ludwig van Beethoven')).toBe('beethoven ludwig van');
	});

	it('sorts and groups', () => {
		const ids = (key: Parameters<typeof sortScores>[1]['key'], desc = false) =>
			sortScores(lib, { key, desc }).map((s) => s.id);
		expect(ids('composer')).toEqual([2, 4, 1, 3]);
		expect(ids('year')).toEqual([2, 4, 1, 3]);
		expect(ids('plays', true).slice(0, 2)).toEqual([1, 3]);
		expect(ids('played', true).slice(0, 2)).toEqual([3, 1]);
		expect(ids('added', true)).toEqual([4, 3, 2, 1]);
		expect(ids('title')[0]).toBe(1);
		const groups = groupByComposer(sortScores(lib, { key: 'composer', desc: false }), true);
		expect(groups.map((g) => [g.heading, g.scores.length])).toEqual([
			['Johann Sebastian Bach', 1],
			['Ludwig van Beethoven', 1],
			['Frédéric Chopin', 2]
		]);
		expect(groupByComposer(lib, false)).toEqual([{ heading: '', scores: lib }]);
		expect(groupByComposer([], false)).toEqual([]);
	});

	it('lists the last played first', () => {
		expect(recentlyPlayed(lib).map((s) => s.id)).toEqual([3, 1]);
	});
});
