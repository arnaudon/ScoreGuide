import type { RequestHandler } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';

/**
 * Stored PDFs are named `<uuid hex>.pdf` (older ones `<name>.pdf`): one path
 * segment, never `..`. Anything else (e.g. `..%2Fadmin%2Fusage`) would let this
 * authenticated proxy reach other backend GET endpoints.
 */
const PDF_NAME = /^[\w.-]+\.pdf$/;

/**
 * Same-origin PDF proxy. Reads the httpOnly `access_token` cookie set at
 * login and forwards it to the backend's `/pdf/{filename}` endpoint
 * server-to-server as an `Authorization: Bearer` header, so the JWT never
 * appears in any URL — neither the browser's nor the backend's access logs.
 */
export const GET: RequestHandler = async ({ params, cookies, fetch, request }) => {
	const filename = params.filepath;
	const token = cookies.get('access_token');

	if (!token || !PDF_NAME.test(filename) || filename.includes('..')) {
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
