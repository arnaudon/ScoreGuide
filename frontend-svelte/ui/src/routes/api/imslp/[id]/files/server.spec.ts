import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { GET } from './+server.js';
import { makeCookies, makeFetch, jsonResponse, event } from '../../../../test-helpers.js';

function get(id: string, cookies = makeCookies({ access_token: 'tok' }), fetch = makeFetch()) {
	const url = new URL(`http://localhost/api/imslp/${id}/files`);
	return GET(event({ url, cookies, fetch, params: { id } }) as Parameters<typeof GET>[0]);
}

describe('GET /api/imslp/[id]/files', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('401s without a token and 404s a non-numeric id, without calling the backend', async () => {
		const fetch = makeFetch();
		expect((await get('12', makeCookies(), fetch)).status).toBe(401);
		expect((await get('..%2Fuser', undefined, fetch)).status).toBe(404);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('returns the backend file list with the bearer token', async () => {
		const files = [
			{ file: 'a.pdf', description: 'Complete Score', copyright: 'Public Domain', url: 'u' }
		];
		const fetch = makeFetch(async () => jsonResponse(files));
		const res = await get('12', undefined, fetch);
		expect(await res.json()).toEqual(files);
		expect(String(fetch.mock.calls[0][0])).toContain('/imslp/12/files');
		expect(new Headers(fetch.mock.calls[0][1]!.headers).get('Authorization')).toBe('Bearer tok');
	});

	it('passes backend errors through and reports an unreachable backend', async () => {
		expect(
			(
				await get(
					'12',
					undefined,
					makeFetch(async () => jsonResponse({}, 404))
				)
			).status
		).toBe(404);
		const down = makeFetch(async () => {
			throw new Error('down');
		});
		expect((await get('12', undefined, down)).status).toBe(502);
	});
});
