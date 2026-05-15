import type { RequestHandler } from './$types';
import { apiFetch } from '$lib/server/fetchApi.js';

/**
 * Same-origin PDF proxy. Reads the httpOnly `access_token` cookie set at
 * login and forwards it to the backend's `/pdf/{filename}?token=...`
 * endpoint server-to-server, so the JWT never appears in the browser's
 * URL bar, access logs, or Referer headers.
 *
 * For backwards compatibility with bookmarked PDF.js viewer URLs that
 * still carry `?token=...` in the path or query string, a token in the
 * URL is accepted but no longer required.
 */
export const GET: RequestHandler = async ({ params, url, cookies, fetch }) => {
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

	const api = apiFetch(fetch, undefined);

	try {
		const response = await api(`/pdf/${filename}?token=${token}`);

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
		if (response.headers.has('Content-Length')) {
			headers.set('Content-Length', response.headers.get('Content-Length')!);
		}
		if (response.headers.has('Cache-Control')) {
			headers.set('Cache-Control', response.headers.get('Cache-Control')!);
		}

		return new Response(response.body, {
			status: 200,
			headers: headers
		});
	} catch (error) {
		console.error('PDF proxy error:', error);
		return new Response('Internal Server Error', { status: 500 });
	}
};
