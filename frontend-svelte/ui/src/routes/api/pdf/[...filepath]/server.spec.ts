import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { GET } from './+server.js';
import { makeCookies, makeFetch, event } from '../../../test-helpers.js';

function pdfResponse(status = 200, body = '%PDF-1.4', extraHeaders: Record<string, string> = {}) {
	return new Response(body, {
		status,
		headers: {
			'Content-Type': 'application/pdf',
			'Content-Length': String(body.length),
			'Cache-Control': 'public, max-age=86400, immutable',
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

	it('returns 404 when there is no token (cookie missing and no ?token=)', async () => {
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

	it('falls back to a URL token when the cookie is absent (legacy)', async () => {
		const fetch = makeFetch(async () => pdfResponse());
		await GET(
			event({
				params: { filepath: 'score.pdf' },
				url: new URL('http://x/api/pdf/score.pdf?token=urlOnly'),
				cookies: makeCookies(),
				request: req('http://x/api/pdf/score.pdf?token=urlOnly'),
				fetch
			})
		);
		expect(fetch.mock.calls[0][0]).not.toContain('token=');
		expect(authHeader(fetch)).toBe('Bearer urlOnly');
	});

	it('parses an embedded `?token=` segment inside the filepath param (PDF.js encoding)', async () => {
		const fetch = makeFetch(async () => pdfResponse());
		await GET(
			event({
				// PDF.js double-encodes the file URL, so the literal `?token=`
				// surfaces inside `params.filepath`.
				params: { filepath: 'foo.pdf?token=fromPath' },
				url: new URL('http://x/api/pdf/foo.pdf'),
				cookies: makeCookies(),
				request: req('http://x/api/pdf/foo.pdf'),
				fetch
			})
		);
		expect(fetch.mock.calls[0][0]).toContain('/pdf/foo.pdf');
		expect(fetch.mock.calls[0][0]).not.toContain('token=');
		expect(authHeader(fetch)).toBe('Bearer fromPath');
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
		expect(res.headers.get('Cache-Control')).toBe('public, max-age=86400, immutable');
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
