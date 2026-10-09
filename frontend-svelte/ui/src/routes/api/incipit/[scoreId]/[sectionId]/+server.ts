import type { RequestHandler } from './$types';
import { apiFetch } from '$lib/server/fetchApi.js';

/**
 * Same-origin proxy for table-of-contents incipit images: `<img>` can't send
 * the bearer token, so the httpOnly cookie is forwarded server-side, like the
 * `/api/pdf` proxy does.
 */
export const GET: RequestHandler = async ({ params, cookies, fetch }) => {
	const token = cookies.get('access_token');
	if (!token || !/^\d+$/.test(params.scoreId) || !/^\d+$/.test(params.sectionId)) {
		return new Response('Not found', { status: 404 });
	}
	try {
		const res = await apiFetch(
			fetch,
			token
		)(`/scores/${params.scoreId}/sections/${params.sectionId}/incipit`);
		if (!res.ok) {
			return new Response('Not found', { status: res.status === 401 ? 401 : 404 });
		}
		return new Response(res.body, {
			headers: {
				'Content-Type': 'image/png',
				'Cache-Control': res.headers.get('Cache-Control') ?? 'private, max-age=86400'
			}
		});
	} catch (error) {
		console.error('Incipit proxy error:', error);
		return new Response('Internal Server Error', { status: 500 });
	}
};
