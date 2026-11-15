import type { RequestHandler } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';

const ID = /^\d+$/;

/**
 * Same-origin JSON proxy for score annotations: the browser can't send the
 * bearer token (httpOnly cookie), so it's forwarded server-side.
 *
 *   GET    /api/scores/:id/annotations            list
 *   POST   /api/scores/:id/annotations            create
 *   DELETE /api/scores/:id/annotations[?page=N]   clear page / score
 *   PUT    /api/scores/:id/annotations/:aid       replace
 *   DELETE /api/scores/:id/annotations/:aid       remove
 */
const proxy: RequestHandler = async ({ params, url, cookies, fetch, request }) => {
	const token = cookies.get('access_token');
	if (!token) return new Response('Unauthorized', { status: 401 });

	const item = params.annotationId !== undefined;
	if (!ID.test(params.scoreId) || (item && !ID.test(params.annotationId!))) {
		return new Response('Not found', { status: 404 });
	}

	const method = request.method;
	const allowed = item ? ['PUT', 'DELETE'] : ['GET', 'POST', 'DELETE'];
	if (!allowed.includes(method)) {
		return new Response('Method not allowed', {
			status: 405,
			headers: { Allow: allowed.join(', ') }
		});
	}

	let path = `/scores/${params.scoreId}/annotations`;
	if (item) path += `/${params.annotationId}`;
	const page = url.searchParams.get('page');
	if (!item && method === 'DELETE' && page !== null) {
		if (!ID.test(page)) return new Response('Bad request', { status: 400 });
		path += `?page=${page}`;
	}

	const hasBody = method === 'POST' || method === 'PUT';
	try {
		const res = await apiFetch(fetch, token)(path, {
			method,
			headers: hasBody ? { 'Content-Type': 'application/json' } : {},
			body: hasBody ? await request.text() : undefined
		});
		if (res.status === 204) return new Response(null, { status: 204 });
		return new Response(res.body, {
			status: res.status,
			headers: { 'Content-Type': res.headers.get('Content-Type') ?? 'application/json' }
		});
	} catch (error) {
		console.error('Annotations proxy error:', error);
		return new Response('Internal Server Error', { status: 500 });
	}
};

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
