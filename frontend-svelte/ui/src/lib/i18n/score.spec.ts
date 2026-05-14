import { describe, it, expect } from 'vitest';
import { isLocalizedField, localizedField } from './score.js';

const SCORE = {
	title: 'Sonata',
	short_description: 'short EN',
	short_description_fr: 'court FR',
	long_description: 'long EN',
	long_description_fr: ''
} as unknown as Parameters<typeof localizedField>[0];

describe('isLocalizedField', () => {
	it('recognises the two localised fields', () => {
		expect(isLocalizedField('short_description')).toBe(true);
		expect(isLocalizedField('long_description')).toBe(true);
	});

	it('rejects everything else', () => {
		expect(isLocalizedField('title')).toBe(false);
		expect(isLocalizedField('composer')).toBe(false);
		expect(isLocalizedField('short_description_fr')).toBe(false);
	});
});

describe('localizedField', () => {
	it('returns the English value when locale is en', () => {
		expect(localizedField(SCORE, 'short_description', 'en')).toBe('short EN');
	});

	it('returns the French value when locale is fr and _fr is non-empty', () => {
		expect(localizedField(SCORE, 'short_description', 'fr')).toBe('court FR');
	});

	it('falls back to the English value when _fr is empty', () => {
		expect(localizedField(SCORE, 'long_description', 'fr')).toBe('long EN');
	});

	it('matches any locale starting with `fr` (e.g. fr-CH)', () => {
		expect(localizedField(SCORE, 'short_description', 'fr-CH')).toBe('court FR');
	});

	it('returns an empty string when the field is missing entirely', () => {
		expect(
			localizedField({} as Parameters<typeof localizedField>[0], 'short_description', 'fr')
		).toBe('');
	});
});
