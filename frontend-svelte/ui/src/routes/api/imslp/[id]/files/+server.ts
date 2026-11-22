import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';

/**
 * Same-origin proxy for an IMSLP work's file list (links to IMSLP's file
 * pages), fetched by the add dialog when it opens.
 */
export const GET: RequestHandler = async ({ params, cookies, fetch }) => {
	const token = cookies.get('access_token');
	if (!token) return json({ detail: 'Unauthorized' }, { status: 401 });
	if (!/^\d+$/.test(params.id)) return json({ detail: 'Not found' }, { status: 404 });
	try {
		const res = await apiFetch(fetch, token)(`/imslp/${params.id}/files`);
		const body = await res.json().catch(() => ({}));
		return json(body, { status: res.status });
	} catch (error) {
		console.error('IMSLP files proxy error:', error);
		return json({ detail: 'Backend unreachable' }, { status: 502 });
	}
};
