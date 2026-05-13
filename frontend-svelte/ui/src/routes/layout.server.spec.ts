import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { load } from './+layout.server.js';

function makeCookies(initial: Record<string, string> = {}) {
	const store = new Map(Object.entries(initial));
	return {
		get: vi.fn((k: string) => store.get(k)),
		set: vi.fn(),
		delete: vi.fn(),
		serialize: vi.fn(),
		getAll: vi.fn()
	};
}

function jsonResponse(body: unknown, status = 200) {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

const event = (cookies: ReturnType<typeof makeCookies>, fetch: ReturnType<typeof vi.fn>) =>
	({ cookies, fetch }) as never;

describe('+layout.server load', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;

	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('returns logged-out without calling fetch when no token cookie', async () => {
		const fetch = vi.fn();
		const cookies = makeCookies();
		const result = await load(event(cookies, fetch));
		expect(result).toEqual({ loggedIn: false, isAdmin: false });
		expect(fetch).not.toHaveBeenCalled();
	});

	it('returns isAdmin true when /is_admin returns truthy', async () => {
		const fetch = vi.fn(async () => jsonResponse(true));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event(cookies, fetch));
		expect(result).toEqual({ loggedIn: true, isAdmin: true });
	});

	it('returns isAdmin false when /is_admin returns falsy', async () => {
		const fetch = vi.fn(async () => jsonResponse(false));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event(cookies, fetch));
		expect(result).toEqual({ loggedIn: true, isAdmin: false });
	});

	it('returns logged-out on non-OK response (e.g., expired token)', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 401 }));
		const cookies = makeCookies({ access_token: 'expired' });
		const result = await load(event(cookies, fetch));
		expect(result).toEqual({ loggedIn: false, isAdmin: false });
	});

	it('logs and degrades gracefully when fetch throws', async () => {
		const fetch = vi.fn(async () => {
			throw new Error('network down');
		});
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event(cookies, fetch));
		expect(result).toEqual({ loggedIn: true, isAdmin: false });
		expect(errSpy).toHaveBeenCalled();
	});
});
