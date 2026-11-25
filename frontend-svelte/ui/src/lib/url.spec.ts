import { describe, it, expect } from 'vitest';
import { httpUrl } from './url.js';

describe('httpUrl', () => {
	it('keeps http and https links', () => {
		expect(httpUrl('https://imslp.org/wiki/X')).toBe('https://imslp.org/wiki/X');
		expect(httpUrl(' HTTP://example.com ')).toBe('HTTP://example.com');
	});

	it.each([
		'javascript:alert(1)',
		' javascript:alert(1)',
		'data:text/html,x',
		'//evil.com',
		'/x',
		''
	])('drops %s', (url) => {
		expect(httpUrl(url)).toBe('');
	});

	it('drops non-strings', () => {
		expect(httpUrl(undefined)).toBe('');
		expect(httpUrl(null)).toBe('');
		expect(httpUrl(42)).toBe('');
	});
});
