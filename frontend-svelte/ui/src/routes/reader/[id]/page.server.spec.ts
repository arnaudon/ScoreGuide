import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { isRedirect } from '@sveltejs/kit';
import { load } from './+page.server.js';
import { makeCookies, jsonResponse, event } from '../../test-helpers.js';

const SCORE = { id: 7, title: 'Sonata', composer: 'Beethoven' };
const OTHER = { id: 99, title: 'Other', composer: 'X' };

describe('reader/[id] load', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('redirects to /login when no token cookie', async () => {
		const fetch = vi.fn();
		const cookies = makeCookies();
		await expect(load(event({ cookies, fetch, params: { id: '7' } }))).rejects.toSatisfy(
			(thrown: unknown) => isRedirect(thrown) && thrown.location === '/login'
		);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('returns the matching score and persists last_score_id when found', async () => {
		const fetch = vi.fn(async () => jsonResponse([OTHER, SCORE]));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event({ cookies, fetch, params: { id: '7' } }));
		expect(result).toEqual({ score: SCORE });
		expect(cookies.set).toHaveBeenCalledWith(
			'last_score_id',
			'7',
			expect.objectContaining({ httpOnly: true, sameSite: 'lax' })
		);
	});

	it('does not leak `token` into the page data', async () => {
		const fetch = vi.fn(async () => jsonResponse([SCORE]));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = (await load(event({ cookies, fetch, params: { id: '7' } }))) as Record<
			string,
			unknown
		>;
		expect('token' in result).toBe(false);
	});

	it('returns score: undefined when id not in list, and does NOT set last_score_id', async () => {
		const fetch = vi.fn(async () => jsonResponse([OTHER]));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event({ cookies, fetch, params: { id: '7' } }));
		expect(result).toEqual({ score: undefined });
		expect(cookies.set).not.toHaveBeenCalled();
	});

	it('returns score: null when /scores responds non-OK', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 500 }));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event({ cookies, fetch, params: { id: '7' } }));
		expect(result).toEqual({ score: null });
	});

	it('returns score: null and logs when fetch throws', async () => {
		const fetch = vi.fn(async () => {
			throw new Error('network down');
		});
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event({ cookies, fetch, params: { id: '7' } }));
		expect(result).toEqual({ score: null });
		expect(errSpy).toHaveBeenCalled();
	});
});
