import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';

const FIELDS = [
	'title',
	'composer',
	'short_description',
	'short_description_fr',
	'long_description',
	'long_description_fr',
	'youtube_url'
] as const;

/**
 * A detailed description from the demo library (public), shown by the effort
 * picker's "See an example" on a plan without detailed descriptions.
 */
export const GET: RequestHandler = async ({ fetch }) => {
	try {
		const res = await apiFetch(fetch, undefined)('/demo-example');
		if (!res.ok) return json(null, { status: res.status === 404 ? 404 : 502 });
		const body = (await res.json()) as Record<string, unknown>;
		const example: Record<string, string> = {};
		for (const key of FIELDS) example[key] = typeof body[key] === 'string' ? body[key] : '';
		return json(example, { headers: { 'Cache-Control': 'private, max-age=3600' } });
	} catch (error) {
		console.error('Demo example error:', error);
		return json(null, { status: 503 });
	}
};
