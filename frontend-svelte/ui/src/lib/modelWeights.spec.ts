import { describe, expect, it } from 'vitest';
import { formatWeights, parseWeights } from './modelWeights.js';

describe('model weights', () => {
	it('parses "model = weight" lines, keeping "=" or ":" inside the name', () => {
		expect(parseWeights('infomaniak:moonshotai/Kimi-K2.6 = 5\n\n  test=0.5  \n')).toEqual({
			'infomaniak:moonshotai/Kimi-K2.6': 5,
			test: 0.5
		});
		expect(parseWeights('')).toEqual({});
	});

	it('rejects malformed lines', () => {
		for (const bad of ['no equals', '= 3', 'm =', 'm = x', 'm = -1']) {
			expect(parseWeights(bad)).toBeNull();
		}
	});

	it('round-trips', () => {
		const weights = { a: 1, 'infomaniak:b': 2.5 };
		expect(parseWeights(formatWeights(weights))).toEqual(weights);
	});
});
