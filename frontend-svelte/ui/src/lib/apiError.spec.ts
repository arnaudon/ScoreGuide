import { describe, expect, it } from 'vitest';
import { detailMessage } from './apiError';

describe('detailMessage', () => {
	it('keeps string details', () => {
		expect(detailMessage('Username already taken', 'x')).toBe('Username already taken');
	});
	it('reads the first validation error', () => {
		const detail = [{ loc: ['body', 'email'], msg: 'value is not a valid email address' }];
		expect(detailMessage(detail, 'x')).toBe('value is not a valid email address');
	});
	it('falls back otherwise', () => {
		expect(detailMessage(undefined, 'fallback')).toBe('fallback');
		expect(detailMessage([], 'fallback')).toBe('fallback');
		expect(detailMessage('', 'fallback')).toBe('fallback');
	});
});
