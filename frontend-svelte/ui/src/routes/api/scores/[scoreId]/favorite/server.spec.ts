import { describe, expect, it, vi } from 'vitest';
import { PUT } from './+server';

type Event = Parameters<typeof PUT>[0];

function event(
	scoreId: string,
	body: unknown,
	fetch: typeof globalThis.fetch,
	token = 'tok'
): Event {
	return {
		params: { scoreId },
		cookies: { get: () => token },
		fetch,
		request: new Request('http://x', { method: 'PUT', body: JSON.stringify(body) })
	} as unknown as Event;
}

describe('PUT /api/scores/:id/favorite', () => {
	it('forwards the choice with the session token', async () => {
		const fetch = vi.fn(async () => Response.json({ id: 7, favorite: true }));
		const res = await PUT(event('7', { favorite: true }, fetch));
		expect(await res.json()).toEqual({ ok: true, favorite: true });
		const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
		expect(url).toMatch(/\/scores\/7\/favorite$/);
		expect(init.method).toBe('PUT');
		expect(JSON.parse(String(init.body))).toEqual({ favorite: true });
		expect(new Headers(init.headers).get('Authorization')).toBe('Bearer tok');
	});

	it('rejects bad input before calling the backend', async () => {
		const fetch = vi.fn();
		expect((await PUT(event('x', { favorite: true }, fetch))).status).toBe(404);
		expect((await PUT(event('7', { favorite: 'yes' }, fetch))).status).toBe(400);
		expect((await PUT(event('7', { favorite: true }, fetch, ''))).status).toBe(401);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('passes failures on', async () => {
		const demo = vi.fn(async () => new Response('no', { status: 403 }));
		expect((await PUT(event('7', { favorite: true }, demo))).status).toBe(403);
		const down = vi.fn(async () => {
			throw new Error('down');
		});
		vi.spyOn(console, 'error').mockImplementation(() => {});
		expect((await PUT(event('7', { favorite: true }, down))).status).toBe(503);
	});
});
