import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { GET } from './+server.js';
import { makeCookies, makeFetch, event } from '../../../test-helpers.js';

function pdfResponse(status = 200, body = '%PDF-1.4', extraHeaders: Record<string, string> = {}) {
	return new Response(body, {
		status,
		headers: {
			'Content-Type': 'application/pdf',
			'Content-Length': String(body.length),
			'Cache-Control': 'private, max-age=86400, immutable',
			...extraHeaders
		}
	});
}

function req(url: string, headers: Record<string, string> = {}) {
	return new Request(url, { headers });
}

describe('GET /api/pdf/:filepath', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('returns 404 when there is no cookie', async () => {
		const fetch = vi.fn();
		const res = await GET(
			event({
				params: { filepath: 'score.pdf' },
				url: new URL('http://x/api/pdf/score.pdf'),
				cookies: makeCookies(),
				request: req('http://x/api/pdf/score.pdf'),
				fetch
			})
		);
		expect(res.status).toBe(404);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('returns 404 when filepath is empty', async () => {
		const res = await GET(
			event({
				params: { filepath: '' },
				url: new URL('http://x/api/pdf/'),
				cookies: makeCookies({ access_token: 'tok' }),
				request: req('http://x/api/pdf/'),
				fetch: vi.fn()
			})
		);
		expect(res.status).toBe(404);
	});

	function authHeader(fetch: ReturnType<typeof makeFetch>): string | null {
		const init = fetch.mock.calls[0][1] as RequestInit;
		return new Headers(init.headers).get('Authorization');
	}

	it('uses the cookie token when present, ignoring any URL fallback', async () => {
		const fetch = makeFetch(async () => pdfResponse());
		await GET(
			event({
				params: { filepath: 'score.pdf' },
				url: new URL('http://x/api/pdf/score.pdf?token=urlToken'),
				cookies: makeCookies({ access_token: 'cookieToken' }),
				request: req('http://x/api/pdf/score.pdf?token=urlToken'),
				fetch
			})
		);
		expect(fetch.mock.calls[0][0]).not.toContain('token=');
		expect(authHeader(fetch)).toBe('Bearer cookieToken');
	});

	it('ignores a URL token when the cookie is absent', async () => {
		const fetch = makeFetch(async () => pdfResponse());
		const res = await GET(
			event({
				params: { filepath: 'score.pdf' },
				url: new URL('http://x/api/pdf/score.pdf?token=urlOnly'),
				cookies: makeCookies(),
				request: req('http://x/api/pdf/score.pdf?token=urlOnly'),
				fetch
			})
		);
		expect(res.status).toBe(404);
		expect(fetch).not.toHaveBeenCalled();
	});

	it.each([
		'../admin/usage',
		'..%2Fadmin%2Fusage',
		'sub/score.pdf',
		'../x.pdf',
		'..pdf',
		'score.pdf?token=abc',
		'score.txt',
		'score.pdf/extra'
	])('returns 404 without calling the backend for %s', async (filepath) => {
		const fetch = vi.fn();
		const res = await GET(
			event({
				params: { filepath },
				url: new URL('http://x/api/pdf/x'),
				cookies: makeCookies({ access_token: 'tok' }),
				request: req('http://x/api/pdf/x'),
				fetch
			})
		);
		expect(res.status).toBe(404);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('accepts stored file names', async () => {
		const fetch = makeFetch(async () => pdfResponse());
		const res = await GET(
			event({
				params: { filepath: '0123abcd_chopin-op.66.pdf' },
				url: new URL('http://x/api/pdf/x'),
				cookies: makeCookies({ access_token: 'tok' }),
				request: req('http://x/api/pdf/x'),
				fetch
			})
		);
		expect(res.status).toBe(200);
		expect(fetch.mock.calls[0][0]).toMatch(/\/pdf\/0123abcd_chopin-op\.66\.pdf$/);
	});

	it('streams the PDF + preserves Content-Length / Cache-Control on happy path', async () => {
		const fetch = makeFetch(async () => pdfResponse());
		const res = await GET(
			event({
				params: { filepath: 'score.pdf' },
				url: new URL('http://x/api/pdf/score.pdf'),
				cookies: makeCookies({ access_token: 'tok' }),
				request: req('http://x/api/pdf/score.pdf'),
				fetch
			})
		);
		expect(res.status).toBe(200);
		expect(res.headers.get('Content-Type')).toBe('application/pdf');
		expect(res.headers.get('Content-Length')).toBe(String('%PDF-1.4'.length));
		expect(res.headers.get('Cache-Control')).toBe('private, max-age=86400, immutable');
	});

	it('propagates backend non-OK status through', async () => {
		const fetch = vi.fn(
			async () =>
				new Response('{"detail":"gone"}', {
					status: 404,
					headers: { 'Content-Type': 'application/json' }
				})
		);
		const res = await GET(
			event({
				params: { filepath: 'missing.pdf' },
				url: new URL('http://x/api/pdf/missing.pdf'),
				cookies: makeCookies({ access_token: 'tok' }),
				request: req('http://x/api/pdf/missing.pdf'),
				fetch
			})
		);
		expect(res.status).toBe(404);
	});

	it('returns 500 and logs when fetch throws', async () => {
		const fetch = vi.fn(async () => {
			throw new Error('backend down');
		});
		const res = await GET(
			event({
				params: { filepath: 'score.pdf' },
				url: new URL('http://x/api/pdf/score.pdf'),
				cookies: makeCookies({ access_token: 'tok' }),
				request: req('http://x/api/pdf/score.pdf'),
				fetch
			})
		);
		expect(res.status).toBe(500);
		expect(errSpy).toHaveBeenCalled();
	});

	it('forwards an incoming Range header to the backend', async () => {
		const fetch = makeFetch(async () => pdfResponse());
		await GET(
			event({
				params: { filepath: 'score.pdf' },
				url: new URL('http://x/api/pdf/score.pdf'),
				cookies: makeCookies({ access_token: 'tok' }),
				request: req('http://x/api/pdf/score.pdf', { Range: 'bytes=0-9' }),
				fetch
			})
		);
		const init = fetch.mock.calls[0][1] as RequestInit;
		expect(new Headers(init.headers).get('Range')).toBe('bytes=0-9');
	});

	it('sends no Range header to the backend when the request has none', async () => {
		const fetch = makeFetch(async () => pdfResponse());
		await GET(
			event({
				params: { filepath: 'score.pdf' },
				url: new URL('http://x/api/pdf/score.pdf'),
				cookies: makeCookies({ access_token: 'tok' }),
				request: req('http://x/api/pdf/score.pdf'),
				fetch
			})
		);
		const init = fetch.mock.calls[0][1] as RequestInit;
		expect(new Headers(init.headers).get('Range')).toBeNull();
	});

	it('passes through a 206 partial-content response with its range headers', async () => {
		const fetch = makeFetch(async () =>
			pdfResponse(206, '%PDF', {
				'Content-Range': 'bytes 0-3/1000',
				'Accept-Ranges': 'bytes'
			})
		);
		const res = await GET(
			event({
				params: { filepath: 'score.pdf' },
				url: new URL('http://x/api/pdf/score.pdf'),
				cookies: makeCookies({ access_token: 'tok' }),
				request: req('http://x/api/pdf/score.pdf', { Range: 'bytes=0-3' }),
				fetch
			})
		);
		expect(res.status).toBe(206);
		expect(res.headers.get('Content-Range')).toBe('bytes 0-3/1000');
		expect(res.headers.get('Accept-Ranges')).toBe('bytes');
	});
});
