import type { RequestHandler } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';

/**
 * Same-origin proxy for a score's first-page image (library cards): `<img>`
 * can't send the bearer token, so the httpOnly cookie is forwarded server-side.
 */
export const GET: RequestHandler = async ({ params, cookies, fetch }) => {
	const token = cookies.get('access_token');
	if (!token || !/^\d+$/.test(params.scoreId)) {
		return new Response('Not found', { status: 404 });
	}
	try {
		const res = await apiFetch(fetch, token)(`/scores/${params.scoreId}/thumbnail`);
		if (!res.ok) {
			return new Response('Not found', { status: res.status === 401 ? 401 : 404 });
		}
		return new Response(res.body, {
			headers: {
				'Content-Type': 'image/png',
				'Cache-Control': res.headers.get('Cache-Control') ?? 'private, max-age=3600'
			}
		});
	} catch (error) {
		console.error('Thumbnail proxy error:', error);
		return new Response('Internal Server Error', { status: 500 });
	}
};
