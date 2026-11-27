import { describe, expect, it, vi } from 'vitest';
import { GET } from './+server';

type Event = Parameters<typeof GET>[0];

function event(scoreId: string, fetch: typeof globalThis.fetch, token = 'tok'): Event {
	return {
		params: { scoreId },
		cookies: { get: () => token },
		fetch
	} as unknown as Event;
}

describe('GET /api/scores/:id/completion', () => {
	it('forwards the status with the session token', async () => {
		const fetch = vi.fn(async () => Response.json({ running: true }));
		const res = await GET(event('7', fetch));
		expect(await res.json()).toEqual({ running: true });
		const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
		expect(url).toMatch(/\/scores\/7\/completion$/);
		expect(new Headers(init.headers).get('Authorization')).toBe('Bearer tok');
	});

	it('rejects bad ids and missing sessions', async () => {
		const fetch = vi.fn();
		expect((await GET(event('..%2Fadmin', fetch))).status).toBe(404);
		expect((await GET(event('7', fetch, ''))).status).toBe(401);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('counts failures as not running', async () => {
		const down = vi.fn(async () => {
			throw new Error('down');
		});
		const res = await GET(event('7', down));
		expect(res.status).toBe(503);
		expect(await res.json()).toEqual({ running: false });
		const missing = vi.fn(async () => new Response('no', { status: 404 }));
		expect(await (await GET(event('7', missing))).json()).toEqual({ running: false });
	});
});
