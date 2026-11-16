import { describe, expect, it } from 'vitest';
import { tokenRole } from './token.js';

const jwt = (payload: unknown) =>
	`h.${Buffer.from(JSON.stringify(payload)).toString('base64url')}.sig`;

describe('tokenRole', () => {
	it('reads the role claim', () => {
		expect(tokenRole(jwt({ sub: 'demo', role: 'demo' }))).toBe('demo');
	});

	it('returns null for missing or malformed claims', () => {
		expect(tokenRole(jwt({ sub: 'x' }))).toBeNull();
		expect(tokenRole('not-a-jwt')).toBeNull();
		expect(tokenRole('a.%%%.c')).toBeNull();
	});
});
