import type { RequestHandler } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';

/**
 * "Download my data": forwards the httpOnly `access_token` cookie to the
 * backend's `GET /user/export` as a Bearer header and streams the ZIP back
 * (the body is passed through, never buffered: it holds every PDF).
 * The account page links here; an expired session goes to the login page.
 */
const toLogin = () => new Response(null, { status: 303, headers: { Location: '/login' } });

export const GET: RequestHandler = async ({ cookies, fetch }) => {
	const token = cookies.get('access_token');
	if (!token) {
		return toLogin();
	}

	try {
		const response = await apiFetch(fetch, token)('/user/export');
		if (response.status === 401) return toLogin();
		const headers = new Headers();
		for (const name of ['Content-Type', 'Content-Length', 'Content-Disposition', 'Cache-Control']) {
			const value = response.headers.get(name);
			if (value) headers.set(name, value);
		}
		return new Response(response.body, { status: response.status, headers });
	} catch (error) {
		console.error('Export proxy error:', error);
		return new Response('Service unavailable', { status: 503 });
	}
};
