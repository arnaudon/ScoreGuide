import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';

const ID = /^\d+$/;

/**
 * Whether the AI is completing this score right now (`{ running }`), so the
 * score card shows "working…" again after a reload instead of offering a
 * second, paid run. Anything but a clear answer counts as not running.
 */
export const GET: RequestHandler = async ({ params, cookies, fetch }) => {
	const token = cookies.get('access_token');
	if (!token) return new Response('Unauthorized', { status: 401 });
	if (!ID.test(params.scoreId)) return new Response('Not found', { status: 404 });
	try {
		const res = await apiFetch(fetch, token)(`/scores/${params.scoreId}/completion`);
		if (!res.ok) return json({ running: false }, { status: res.status });
		const body = (await res.json()) as { running?: unknown };
		return json({ running: body.running === true });
	} catch (error) {
		console.error('Completion status error:', error);
		return json({ running: false }, { status: 503 });
	}
};
