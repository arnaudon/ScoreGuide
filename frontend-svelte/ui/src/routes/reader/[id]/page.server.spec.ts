import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { isRedirect } from '@sveltejs/kit';
import { load, actions } from './+page.server.js';
import { makeCookies, makeFetch, fakeRequest, jsonResponse, event } from '../../test-helpers.js';

const SCORE = { id: 7, title: 'Sonata', composer: 'Beethoven' };
const TOC = {
	status: 'ready',
	sections: [
		{
			id: 1,
			score_id: 7,
			position: 0,
			title: 'Allegro',
			page: 1,
			source: 'ocr',
			incipit_path: 'x.png',
			level: 0
		}
	]
};
const EMPTY_TOC = {
	status: 'none',
	sections: [],
	confidence: null,
	version: null,
	latest_version: 1
};

/** Backend stub: score at /scores/{id}, table of contents at /scores/{id}/sections. */
function scoreAndToc(toc: () => Promise<Response> = async () => jsonResponse(TOC)) {
	return makeFetch(async (url: string) =>
		url.endsWith('/sections') ? toc() : jsonResponse(SCORE)
	);
}

describe('reader/[id] load', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('records a play, except for the read-only demo account', async () => {
		const plays = (fetch: ReturnType<typeof scoreAndToc>) =>
			fetch.mock.calls.filter(
				([url, init]) => String(url).endsWith('/scores/7/play') && init?.method === 'POST'
			);
		const fetch = scoreAndToc();
		await load(
			event({ cookies: makeCookies({ access_token: 'tok' }), fetch, params: { id: '7' } })
		);
		expect(plays(fetch)).toHaveLength(1);

		const demoToken = `x.${Buffer.from(JSON.stringify({ role: 'demo' })).toString('base64url')}.y`;
		const demoFetch = scoreAndToc();
		await load(
			event({
				cookies: makeCookies({ access_token: demoToken }),
				fetch: demoFetch,
				params: { id: '7' }
			})
		);
		expect(plays(demoFetch)).toHaveLength(0);
	});

	it('still opens the score when recording the play fails', async () => {
		const fetch = makeFetch(async (url: string) => {
			if (url.endsWith('/play')) throw new Error('down');
			return url.endsWith('/sections') ? jsonResponse(TOC) : jsonResponse(SCORE);
		});
		const result = await load(
			event({ cookies: makeCookies({ access_token: 'tok' }), fetch, params: { id: '7' } })
		);
		expect(result).toEqual({ score: SCORE, toc: TOC });
		await new Promise((r) => setTimeout(r, 0));
		expect(errSpy).toHaveBeenCalledWith('Failed to record play:', expect.any(Error));
	});

	it('redirects to /login when no token cookie', async () => {
		const fetch = vi.fn();
		const cookies = makeCookies();
		await expect(load(event({ cookies, fetch, params: { id: '7' } }))).rejects.toSatisfy(
			(thrown: unknown) => isRedirect(thrown) && thrown.location === '/login'
		);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('fetches /scores/{id} directly and persists last_score_id when found', async () => {
		const fetch = scoreAndToc();
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event({ cookies, fetch, params: { id: '7' } }));
		expect(result).toEqual({ score: SCORE, toc: TOC });
		expect(fetch.mock.calls[0][0]).toContain('/scores/7');
		expect(cookies.set).toHaveBeenCalledWith(
			'last_score_id',
			'7',
			expect.objectContaining({ httpOnly: true, sameSite: 'lax' })
		);
	});

	it('never sends a non-numeric id to the backend', async () => {
		const fetch = makeFetch();
		const cookies = makeCookies({ access_token: 'tok' });
		expect(await load(event({ cookies, fetch, params: { id: '../admin/usage' } }))).toEqual({
			score: null,
			toc: EMPTY_TOC
		});
		const toc = await actions.generate_toc(
			event({ cookies, fetch, params: { id: '../admin' }, request: fakeRequest() })
		);
		expect(toc).toMatchObject({ status: 404 });
		const report = await actions.report_toc(
			event({ cookies, fetch, params: { id: '../admin' }, request: fakeRequest() })
		);
		expect(report).toMatchObject({ status: 404 });
		const update = await actions.update_score(
			event({ cookies, fetch, request: fakeRequest({ id: '../users/1', title: 't' }) })
		);
		expect(update).toMatchObject({ status: 400 });
		expect(fetch).not.toHaveBeenCalled();
	});

	it('still shows the score when the table of contents fails to load', async () => {
		const cookies = makeCookies({ access_token: 'tok' });
		const notOk = scoreAndToc(async () => new Response(null, { status: 500 }));
		expect(await load(event({ cookies, fetch: notOk, params: { id: '7' } }))).toEqual({
			score: SCORE,
			toc: EMPTY_TOC
		});
		const thrown = scoreAndToc(async () => {
			throw new Error('down');
		});
		expect(await load(event({ cookies, fetch: thrown, params: { id: '7' } }))).toEqual({
			score: SCORE,
			toc: EMPTY_TOC
		});
		expect(errSpy).toHaveBeenCalled();
	});

	it('does not leak `token` into the page data', async () => {
		const fetch = vi.fn(async () => jsonResponse(SCORE));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = (await load(event({ cookies, fetch, params: { id: '7' } }))) as Record<
			string,
			unknown
		>;
		expect('token' in result).toBe(false);
	});

	it('returns score: null when the id is not found (404), and does NOT set last_score_id', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 404 }));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event({ cookies, fetch, params: { id: '7' } }));
		expect(result).toEqual({ score: null, toc: EMPTY_TOC });
		expect(cookies.set).not.toHaveBeenCalled();
	});

	it('returns score: null when /scores/{id} responds non-OK', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 500 }));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event({ cookies, fetch, params: { id: '7' } }));
		expect(result).toEqual({ score: null, toc: EMPTY_TOC });
	});

	it('returns score: null and logs when fetch throws', async () => {
		const fetch = vi.fn(async () => {
			throw new Error('network down');
		});
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event({ cookies, fetch, params: { id: '7' } }));
		expect(result).toEqual({ score: null, toc: EMPTY_TOC });
		expect(errSpy).toHaveBeenCalled();
	});
});

describe('reader/[id] update_score action', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('fails 401 when not authenticated', async () => {
		const result = await actions.update_score(
			event({
				request: fakeRequest({ id: '7', title: 't' }),
				cookies: makeCookies(),
				fetch: vi.fn()
			})
		);
		expect(result).toMatchObject({ status: 401 });
	});

	it('fails 400 when id is missing', async () => {
		const result = await actions.update_score(
			event({
				request: fakeRequest({ title: 't' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch: vi.fn()
			})
		);
		expect(result).toMatchObject({ status: 400 });
	});

	it('PUTs the submitted fields on happy path', async () => {
		const fetch = makeFetch().mockResolvedValueOnce(jsonResponse({ id: 7 }));
		const result = await actions.update_score(
			event({
				request: fakeRequest({
					id: '7',
					title: 'New',
					composer: 'C',
					year: '1900',
					period: 'Modernist',
					difficulty: 'easy'
				}),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toEqual({ success: true, scoreUpdated: true });
		expect(fetch.mock.calls[0][1]!.method).toBe('PUT');
		expect(fetch.mock.calls[0][0]).toContain('/scores/7');
		const body = JSON.parse(fetch.mock.calls[0][1]!.body as string);
		expect(body).toMatchObject({
			title: 'New',
			composer: 'C',
			year: 1900,
			period: 'Modernist',
			difficulty: 'easy'
		});
	});

	it('forwards backend failure status', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 404 }));
		const result = await actions.update_score(
			event({
				request: fakeRequest({ id: '999', title: 't' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toMatchObject({ status: 404 });
	});
});

describe('reader/[id] generate_toc action', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('fails 401 when not authenticated', async () => {
		const result = await actions.generate_toc(
			event({ cookies: makeCookies(), fetch: vi.fn(), params: { id: '7' } })
		);
		expect(result).toMatchObject({ status: 401 });
	});

	it('POSTs the generate endpoint', async () => {
		const fetch = makeFetch(async () => jsonResponse({ status: 'running', sections: [] }, 202));
		const result = await actions.generate_toc(
			event({ cookies: makeCookies({ access_token: 'tok' }), fetch, params: { id: '7' } })
		);
		expect(result).toEqual({ tocStarted: true });
		expect(fetch.mock.calls[0][0]).toContain('/scores/7/sections/generate');
		expect(fetch.mock.calls[0][1]!.method).toBe('POST');
	});

	it('reports backend failures and network errors', async () => {
		const cookies = makeCookies({ access_token: 'tok' });
		const notOk = vi.fn(async () => new Response(null, { status: 429 }));
		expect(
			await actions.generate_toc(event({ cookies, fetch: notOk, params: { id: '7' } }))
		).toMatchObject({ status: 429, data: { tocError: true } });
		const thrown = vi.fn(async () => {
			throw new Error('down');
		});
		expect(
			await actions.generate_toc(event({ cookies, fetch: thrown, params: { id: '7' } }))
		).toMatchObject({ status: 500, data: { tocError: true } });
	});
});
