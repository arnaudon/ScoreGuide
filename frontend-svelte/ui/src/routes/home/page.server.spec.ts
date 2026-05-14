import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { isRedirect, isActionFailure } from '@sveltejs/kit';
import { load, actions } from './+page.server.js';

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

function fakeRequest(fields: Record<string, string>) {
	const fd = new FormData();
	for (const [k, v] of Object.entries(fields)) fd.append(k, v);
	return { formData: async () => fd } as unknown as Request;
}

function jsonResponse(body: unknown, status = 200) {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

const SAMPLE_USER = { id: 1, username: 'alice', credits: 5, max_credits: 10 };
const SAMPLE_SCORES = [
	{ id: 11, title: 'Sonata', composer: 'Beethoven' },
	{ id: 22, title: 'Nocturne', composer: 'Chopin' }
];

const loadEvent = (cookies: ReturnType<typeof makeCookies>, fetch: ReturnType<typeof vi.fn>) =>
	({ cookies, fetch }) as never;

const actionEvent = (
	request: Request,
	cookies: ReturnType<typeof makeCookies>,
	fetch: ReturnType<typeof vi.fn>
) => ({ request, cookies, fetch }) as never;

describe('home load', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('redirects to /login when no token cookie', async () => {
		const fetch = vi.fn();
		const cookies = makeCookies();
		await expect(load(loadEvent(cookies, fetch))).rejects.toSatisfy(
			(thrown: unknown) => isRedirect(thrown) && thrown.location === '/login'
		);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('clears cookie and redirects when /user is unauthorized', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 401 }));
		const cookies = makeCookies({ access_token: 'expired' });
		await expect(load(loadEvent(cookies, fetch))).rejects.toSatisfy(
			(thrown: unknown) => isRedirect(thrown) && thrown.location === '/login'
		);
		expect(cookies.delete).toHaveBeenCalledWith('access_token', expect.any(Object));
	});

	it('returns user with hasScores=true when scores list is non-empty', async () => {
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(jsonResponse(SAMPLE_USER))
			.mockResolvedValueOnce(jsonResponse(SAMPLE_SCORES));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(loadEvent(cookies, fetch));
		expect(result).toEqual({ user: SAMPLE_USER, hasScores: true });
	});

	it('returns hasScores=false when scores list is empty', async () => {
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(jsonResponse(SAMPLE_USER))
			.mockResolvedValueOnce(jsonResponse([]));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(loadEvent(cookies, fetch));
		expect(result).toEqual({ user: SAMPLE_USER, hasScores: false });
	});

	it('logs and returns hasScores=false when /scores fetch throws', async () => {
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(jsonResponse(SAMPLE_USER))
			.mockRejectedValueOnce(new Error('network'));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(loadEvent(cookies, fetch));
		expect(result).toEqual({ user: SAMPLE_USER, hasScores: false });
		expect(errSpy).toHaveBeenCalled();
	});
});

describe('ask action', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('fails 400 when question is missing', async () => {
		const fetch = vi.fn();
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await actions.ask(actionEvent(fakeRequest({}), cookies, fetch));
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 400, data: { error: 'Missing question' } });
		expect(fetch).not.toHaveBeenCalled();
	});

	it('resolves a single scoreDetails when result.score_id matches a loaded score', async () => {
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(jsonResponse(SAMPLE_SCORES)) // GET /scores
			.mockResolvedValueOnce(jsonResponse({ score_id: 22 })); // POST /agent
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await actions.ask(
			actionEvent(fakeRequest({ question: 'find Chopin' }), cookies, fetch)
		);
		expect(result).toMatchObject({
			success: true,
			question: 'find Chopin',
			scoreDetails: SAMPLE_SCORES[1],
			scores: [SAMPLE_SCORES[1]]
		});
	});

	it('resolves multiple scores when result.score_ids contains an array', async () => {
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(jsonResponse(SAMPLE_SCORES))
			.mockResolvedValueOnce(jsonResponse({ score_ids: [11, 22] }));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await actions.ask(
			actionEvent(fakeRequest({ question: 'find both' }), cookies, fetch)
		);
		expect(result).toMatchObject({ success: true, scores: SAMPLE_SCORES });
	});

	it('fails with backend status when /agent returns non-OK', async () => {
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(jsonResponse(SAMPLE_SCORES))
			.mockResolvedValueOnce(jsonResponse({ detail: 'rate limited' }, 429));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await actions.ask(actionEvent(fakeRequest({ question: 'q' }), cookies, fetch));
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 429, data: { error: 'rate limited' } });
	});

	it('fails 500 and logs when /scores fetch throws', async () => {
		const fetch = vi.fn().mockRejectedValueOnce(new Error('boom'));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await actions.ask(actionEvent(fakeRequest({ question: 'q' }), cookies, fetch));
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 500 });
		expect(errSpy).toHaveBeenCalled();
	});
});
