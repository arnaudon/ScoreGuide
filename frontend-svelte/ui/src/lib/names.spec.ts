import { describe, it, expect } from 'vitest';
import { splitNames } from './names.js';

describe('splitNames', () => {
	it('trims, drops blanks and repeats', () => {
		expect(
			splitNames(' Radu Lupu, Glenn Gould,, radu lupu; Hélène Grimaud.\nGlenn Gould ')
		).toEqual(['Radu Lupu', 'Glenn Gould', 'Hélène Grimaud']);
		expect(splitNames('')).toEqual([]);
	});
});
