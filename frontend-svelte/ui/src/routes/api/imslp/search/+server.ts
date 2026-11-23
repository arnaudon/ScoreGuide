import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';

const PARAMS = ['q', 'instrument', 'solo', 'period', 'limit', 'offset'] as const;

/**
 * Same-origin proxy for the IMSLP catalogue search, so the browser can search
 * as the user types with the httpOnly cookie forwarded server-side.
 */
export const GET: RequestHandler = async ({ url, cookies, fetch }) => {
	const token = cookies.get('access_token');
	if (!token) return json({ detail: 'Unauthorized' }, { status: 401 });
	const query = new URLSearchParams();
	for (const key of PARAMS) {
		const value = url.searchParams.get(key);
		if (value) query.set(key, value);
	}
	try {
		const res = await apiFetch(fetch, token)(`/imslp/search?${query}`);
		const body = await res.json().catch(() => ({}));
		return json(body, { status: res.status });
	} catch (error) {
		console.error('IMSLP search proxy error:', error);
		return json({ detail: 'Backend unreachable' }, { status: 502 });
	}
};
