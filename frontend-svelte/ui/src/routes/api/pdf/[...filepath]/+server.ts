import type { RequestHandler } from './$types';
import { apiFetch } from '$lib/server/fetchApi.js';

/**
 * Same-origin PDF proxy. Reads the httpOnly `access_token` cookie set at
 * login and forwards it to the backend's `/pdf/{filename}` endpoint
 * server-to-server as an `Authorization: Bearer` header, so the JWT never
 * appears in any URL — neither the browser's nor the backend's access logs.
 *
 * For backwards compatibility with bookmarked PDF.js viewer URLs that
 * still carry `?token=...` in the path or query string, a token in the
 * URL is accepted but no longer required (and is still forwarded as a
 * header, not a query param).
 */
export const GET: RequestHandler = async ({ params, url, cookies, fetch, request }) => {
	const pathWithQuery = params.filepath;
	let filename = pathWithQuery;
	let urlToken: string | null;

	// PDF.js encodes the `?file=` query param value, which means our own
	// `?token=` query parameter ends up inside `params.filepath`. Strip it.
	const tokenMarker = '?token=';
	const tokenIndex = pathWithQuery.indexOf(tokenMarker);
	if (tokenIndex !== -1) {
		filename = pathWithQuery.substring(0, tokenIndex);
		urlToken = pathWithQuery.substring(tokenIndex + tokenMarker.length);
	} else {
		urlToken = url.searchParams.get('token');
	}

	// Prefer the cookie (same-origin, httpOnly) so the JWT never has to
	// travel through the URL. Fall back to the URL param for compatibility.
	const token = cookies.get('access_token') ?? urlToken;

	if (!filename || !token) {
		return new Response('Not found', { status: 404 });
	}

	const api = apiFetch(fetch, token);

	// Forward the incoming Range header so the backend's partial-content
	// support (206) reaches PDF.js — without this, every range request
	// PDF.js makes to prerender upcoming pages re-downloads the whole file,
	// which is what makes page turns feel slow.
	const rangeHeader = request.headers.get('Range');

	try {
		const response = await api(`/pdf/${filename}`, {
			headers: rangeHeader ? { Range: rangeHeader } : {}
		});

		if (!response.ok) {
			return new Response(response.body, {
				status: response.status,
				statusText: response.statusText,
				headers: {
					'Content-Type': response.headers.get('Content-Type') || 'application/json'
				}
			});
		}

		const headers = new Headers();
		headers.set('Content-Type', 'application/pdf');
		for (const name of ['Content-Length', 'Cache-Control', 'Accept-Ranges', 'Content-Range']) {
			if (response.headers.has(name)) {
				headers.set(name, response.headers.get(name)!);
			}
		}

		return new Response(response.body, {
			status: response.status,
			headers: headers
		});
	} catch (error) {
		console.error('PDF proxy error:', error);
		return new Response('Internal Server Error', { status: 500 });
	}
};
