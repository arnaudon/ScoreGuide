import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { isRedirect, isActionFailure } from '@sveltejs/kit';
import { load, actions } from './+page.server.js';
import { makeCookies, makeFetch, fakeRequest, jsonResponse, event } from '../test-helpers.js';

const USER = { id: 1, username: 'alice' };
const SCORE = { id: 11, title: 'Sonata', composer: 'Beethoven' };
const IMSLP_SCORE = {
	id: 42,
	title: 'X',
	composer: 'Y',
	instrumentation: 'piano',
	style: 'Romantic',
	period: '',
	year: '1850',
	key: 'C'
};

function pdfFile(name = 'test.pdf') {
	return new File(['%PDF-1.4'], name, { type: 'application/pdf' });
}

describe('db-viewer load', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('redirects to /login when no token', async () => {
		await expect(load(event({ cookies: makeCookies(), fetch: vi.fn() }))).rejects.toSatisfy(
			(t: unknown) => isRedirect(t) && t.location === '/login'
		);
	});

	it('clears the cookie and redirects when /user is unauthorized', async () => {
		const fetch = vi.fn(async (url: string) =>
			url.includes('/user') ? new Response(null, { status: 401 }) : jsonResponse([])
		);
		const cookies = makeCookies({ access_token: 'tok' });
		await expect(load(event({ cookies, fetch }))).rejects.toSatisfy(
			(t: unknown) => isRedirect(t) && t.location === '/login'
		);
		expect(cookies.delete).toHaveBeenCalledWith('access_token', expect.any(Object));
	});

	it('returns { user, scores } on happy path', async () => {
		const fetch = vi.fn(async (url: string) =>
			url.includes('/user') ? jsonResponse(USER) : jsonResponse([SCORE])
		);
		const result = await load(event({ cookies: makeCookies({ access_token: 'tok' }), fetch }));
		expect(result).toEqual({ user: USER, scores: [SCORE] });
	});

	it('returns empty scores when /scores returns non-OK', async () => {
		const fetch = vi.fn(async (url: string) =>
			url.includes('/user') ? jsonResponse(USER) : new Response(null, { status: 500 })
		);
		const result = await load(event({ cookies: makeCookies({ access_token: 'tok' }), fetch }));
		expect(result).toEqual({ user: USER, scores: [] });
	});
});

describe('upload action', () => {
	it('fails 401 when not authenticated', async () => {
		const result = await actions.upload(
			event({
				request: fakeRequest({ title: 't', composer: 'c', file: pdfFile() }),
				cookies: makeCookies(),
				fetch: vi.fn()
			})
		);
		expect(result).toMatchObject({ status: 401 });
	});

	it('fails 400 when title is missing', async () => {
		const result = await actions.upload(
			event({
				request: fakeRequest({ composer: 'c', file: pdfFile() }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch: vi.fn()
			})
		);
		expect(result).toMatchObject({ status: 400, data: { error: 'Missing required fields' } });
	});

	it('uploads PDF, completes via agent, saves score on happy path', async () => {
		const fetch = makeFetch()
			.mockResolvedValueOnce(jsonResponse({ file_id: 'final.pdf' })) // POST /pdf
			.mockResolvedValueOnce(jsonResponse({ title: 't', composer: 'c', year: 1850 })) // POST /complete_score
			.mockResolvedValueOnce(jsonResponse({ id: 1 })); // POST /scores
		const result = await actions.upload(
			event({
				request: fakeRequest({ title: 't', composer: 'c', file: pdfFile() }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toEqual({ success: true, scoreAdded: true });
		// 3rd call is POST /scores with `source: 'manual'` + pdf_path
		const lastBody = JSON.parse(fetch.mock.calls[2][1]!.body as string);
		expect(lastBody).toMatchObject({ pdf_path: 'final.pdf', source: 'manual' });
	});

	it('fails when /pdf upload returns non-OK', async () => {
		const fetch = makeFetch().mockResolvedValueOnce(new Response(null, { status: 500 }));
		const result = await actions.upload(
			event({
				request: fakeRequest({ title: 't', composer: 'c', file: pdfFile() }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 500, data: { error: 'Failed to upload PDF' } });
	});
});

describe('ask_agent action', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('fails 400 when no question', async () => {
		const result = await actions.ask_agent(
			event({
				request: fakeRequest({}),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch: vi.fn()
			})
		);
		expect(result).toMatchObject({ status: 400 });
	});

	it('returns agent response + filtered IMSLP scores on happy path', async () => {
		const fetch = makeFetch()
			.mockResolvedValueOnce(jsonResponse([])) // GET /scores
			.mockResolvedValueOnce(jsonResponse({ response: { score_ids: [42], response: 'found' } })) // POST /imslp_agent
			.mockResolvedValueOnce(jsonResponse([IMSLP_SCORE])); // GET /imslp/scores_by_ids
		const result = await actions.ask_agent(
			event({
				request: fakeRequest({ question: 'find piano works' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toMatchObject({
			success: true,
			question: 'find piano works',
			agent_results: { response: 'found', scores: [IMSLP_SCORE] }
		});
	});

	it('fails 500 and logs when /scores fetch throws', async () => {
		const fetch = makeFetch().mockRejectedValueOnce(new Error('boom'));
		const result = await actions.ask_agent(
			event({
				request: fakeRequest({ question: 'q' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toMatchObject({ status: 500 });
		expect(errSpy).toHaveBeenCalled();
	});
});

describe('add_imslp action', () => {
	it('fails 400 when imslp_id or file is missing', async () => {
		const result = await actions.add_imslp(
			event({
				request: fakeRequest({ imslp_id: '42' }), // no file
				cookies: makeCookies({ access_token: 'tok' }),
				fetch: vi.fn()
			})
		);
		expect(result).toMatchObject({ status: 400 });
	});

	it('uploads PDF + reads IMSLP metadata + saves on happy path', async () => {
		const fetch = makeFetch()
			.mockResolvedValueOnce(jsonResponse({ file_id: 'beethoven.pdf' })) // POST /pdf
			.mockResolvedValueOnce(jsonResponse([IMSLP_SCORE])) // GET /imslp/scores_by_ids
			.mockResolvedValueOnce(jsonResponse({ id: 1 })); // POST /scores
		const result = await actions.add_imslp(
			event({
				request: fakeRequest({ imslp_id: '42', file: pdfFile() }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toEqual({ success: true, scoreAdded: true });
		const saved = JSON.parse(fetch.mock.calls[2][1]!.body as string);
		expect(saved).toMatchObject({ title: 'X', composer: 'Y', pdf_path: 'beethoven.pdf' });
	});

	it('fails 404 when IMSLP returns an empty array', async () => {
		const fetch = makeFetch()
			.mockResolvedValueOnce(jsonResponse({ file_id: 'x.pdf' }))
			.mockResolvedValueOnce(jsonResponse([]));
		const result = await actions.add_imslp(
			event({
				request: fakeRequest({ imslp_id: '42', file: pdfFile() }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toMatchObject({ status: 404 });
	});
});

describe('delete action', () => {
	it('fails 400 when id is missing', async () => {
		const result = await actions.delete(
			event({
				request: fakeRequest({}),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch: vi.fn()
			})
		);
		expect(result).toMatchObject({ status: 400 });
	});

	it('returns success on happy path', async () => {
		const fetch = makeFetch();
		const result = await actions.delete(
			event({
				request: fakeRequest({ id: '7' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toEqual({ success: true });
		expect(fetch.mock.calls[0][1]!.method).toBe('DELETE');
	});

	it('fails with backend status when /scores DELETE returns non-OK', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 500 }));
		const result = await actions.delete(
			event({
				request: fakeRequest({ id: '7' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toMatchObject({ status: 500 });
	});
});

describe('recomplete action', () => {
	it('fails 400 when required fields are missing', async () => {
		const result = await actions.recomplete(
			event({
				request: fakeRequest({ id: '7' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch: vi.fn()
			})
		);
		expect(result).toMatchObject({ status: 400 });
	});

	it('PUTs the recompleted score on happy path', async () => {
		const fetch = makeFetch()
			.mockResolvedValueOnce(jsonResponse({ title: 't', composer: 'c', year: 1850 })) // POST /complete_score
			.mockResolvedValueOnce(jsonResponse({ id: 7 })); // PUT /scores/7
		const result = await actions.recomplete(
			event({
				request: fakeRequest({ id: '7', title: 't', composer: 'c', pdf_path: 'p.pdf' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toEqual({ success: true });
		expect(fetch.mock.calls[1][1]!.method).toBe('PUT');
		expect(fetch.mock.calls[1][0]).toContain('/scores/7');
	});
});
