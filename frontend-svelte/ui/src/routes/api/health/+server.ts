import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';

/**
 * Public liveness check for the uptime monitor: 200 only when the frontend,
 * the backend and its database all answer (the backend isn't public itself).
 */
export const GET: RequestHandler = async ({ fetch }) => {
	try {
		const res = await apiFetch(fetch, undefined)('/health', { signal: AbortSignal.timeout(5000) });
		return json(
			{ ok: res.ok },
			{ status: res.ok ? 200 : 503, headers: { 'Cache-Control': 'no-store' } }
		);
	} catch {
		return json({ ok: false }, { status: 503, headers: { 'Cache-Control': 'no-store' } });
	}
};
