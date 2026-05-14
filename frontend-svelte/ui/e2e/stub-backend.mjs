/**
 * Minimal HTTP stub used only by the Playwright e2e tests. Mimics just
 * enough of the FastAPI backend to drive a successful login + /home load.
 *
 * Started automatically by playwright.config.ts on port 9999.
 */
import { createServer } from 'node:http';

const PORT = Number(process.env.STUB_PORT ?? 9999);

const USER = {
	id: 1,
	username: 'test',
	email: 'test@example.com',
	first_name: null,
	last_name: null,
	instrument: null,
	role: 'user',
	credits: 5,
	max_credits: 20,
	last_login: null
};

function json(res, status, body) {
	const payload = JSON.stringify(body);
	res.writeHead(status, {
		'Content-Type': 'application/json',
		'Content-Length': Buffer.byteLength(payload)
	});
	res.end(payload);
}

const server = createServer((req, res) => {
	const url = new URL(req.url ?? '/', `http://localhost:${PORT}`);

	if (url.pathname === '/token' && req.method === 'POST') {
		return json(res, 200, { access_token: 'stub-token', token_type: 'bearer' });
	}
	if (url.pathname === '/user' && req.method === 'GET') {
		return json(res, 200, USER);
	}
	if (url.pathname === '/is_admin' && req.method === 'GET') {
		return json(res, 200, false);
	}
	if (url.pathname === '/scores' && req.method === 'GET') {
		return json(res, 200, []);
	}
	return json(res, 404, { detail: `stub: no handler for ${req.method} ${url.pathname}` });
});

server.listen(PORT, () => {
	console.log(`[e2e stub-backend] listening on http://localhost:${PORT}`);
});
