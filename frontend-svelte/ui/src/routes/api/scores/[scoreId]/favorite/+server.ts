import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';

/** Star or unstar one of the user's scores: body `{ favorite: boolean }`. */
export const PUT: RequestHandler = async ({ params, cookies, fetch, request }) => {
	const token = cookies.get('access_token');
	if (!token) return new Response('Unauthorized', { status: 401 });
	if (!/^\d+$/.test(params.scoreId)) return new Response('Not found', { status: 404 });
	const body = (await request.json().catch(() => null)) as { favorite?: unknown } | null;
	if (typeof body?.favorite !== 'boolean') return new Response('Bad request', { status: 400 });
	try {
		const res = await apiFetch(fetch, token)(`/scores/${params.scoreId}/favorite`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ favorite: body.favorite })
		});
		if (!res.ok) return json({ ok: false }, { status: res.status });
		const score = (await res.json()) as { favorite?: unknown };
		return json({ ok: true, favorite: score.favorite === true });
	} catch (error) {
		console.error('Favorite proxy error:', error);
		return json({ ok: false }, { status: 503 });
	}
};
