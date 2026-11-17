import { describe, expect, it } from 'vitest';
import { demoAgentAnswer } from './demoAgent';
import type { Score } from '#lib/types.js';

const score = (id: number, composer: string, title: string, extra: Partial<Score> = {}) =>
	({
		id,
		composer,
		title,
		period: 'Classical',
		form: '',
		difficulty: 'moderate',
		...extra
	}) as Score;

const library = [
	score(1, 'Johann Sebastian Bach', 'Prelude in C major, BWV 846', {
		period: 'Baroque',
		form: 'Prelude'
	}),
	score(2, 'Ludwig van Beethoven', 'Piano Sonata No. 8 “Pathétique”', {
		form: 'Sonata',
		difficulty: 'advanced'
	}),
	score(3, 'Erik Satie', 'Gymnopédie No. 1', { period: 'Modernist', difficulty: 'easy' })
];

describe('demoAgentAnswer', () => {
	it('finds scores by composer or title, ignoring case and accents', () => {
		expect(demoAgentAnswer('give me a Bach score', library).score_ids).toEqual([1]);
		expect(demoAgentAnswer('la sonate pathetique', library).score_ids).toEqual([2]);
		expect(demoAgentAnswer('Gymnopedie please', library).response).toContain('Erik Satie');
	});

	it('uses period, difficulty and form hints', () => {
		expect(demoAgentAnswer('something easy', library).score_ids).toEqual([3]);
		expect(demoAgentAnswer('un morceau baroque', library).score_ids).toEqual([1]);
		expect(demoAgentAnswer('a sonata with movements', library).score_ids).toEqual([2]);
	});

	it('falls back to the whole library', () => {
		const answer = demoAgentAnswer('hello', library);
		expect(answer.score_ids).toEqual([1, 2, 3]);
		expect(answer.response).toMatch(/demo/i);
	});
});
