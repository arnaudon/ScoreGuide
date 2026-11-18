import { describe, it, expect } from 'vitest';
import { composerName, summarizeLibrary } from './library.js';
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
