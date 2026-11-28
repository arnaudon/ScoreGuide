/**
 * Minimal HTTP stub used only by the Playwright e2e tests. Mimics just
 * enough of the FastAPI backend to drive a successful login + /home load.
 *
 * Started automatically by playwright.config.ts on port 9999.
 */
import { readFileSync } from 'node:fs';
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

// The library list: 12 scores, so the table has two pages of 10.
// More than one batch of the library's list (30), to check it grows on scroll.
const LIBRARY = Array.from({ length: 40 }, (_, i) => ({
	id: 100 + i,
	title: `Etude No. ${String(i + 1).padStart(2, '0')}`,
	composer: i % 2 ? 'Chopin' : 'Liszt',
	year: 1830 + i,
	period: 'Romantic',
	genre: 'Solo keyboard',
	form: 'Étude',
	key: '',
	instrumentation: 'Piano',
	pdf_path: '',
	pdf_size: 0,
	number_of_plays: i,
	favorite: false,
	user_id: 1
}));

function json(res, status, body) {
	const payload = JSON.stringify(body);
	res.writeHead(status, {
		'Content-Type': 'application/json',
		'Content-Length': Buffer.byteLength(payload)
	});
	res.end(payload);
}

// Score 2: a real PDF with a long table of contents, to check the reader
// layout keeps the viewer on screen however many sections there are.
const REAL_PDF = readFileSync(
	new URL('../../../backend/tests/data/real_score.pdf', import.meta.url)
);
const LONG_TOC = {
	status: 'ready',
	sections: Array.from({ length: 40 }, (_, i) => ({
		id: i + 1,
		score_id: 2,
		position: i,
		title: `Movement ${i + 1}`,
		page: Math.min(i + 1, 3),
		source: 'outline',
		incipit_path: ''
	}))
};

const server = createServer(async (req, res) => {
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
		return json(res, 200, LIBRARY);
	}
	const favoriteMatch = url.pathname.match(/^\/scores\/(\d+)\/favorite$/);
	if (favoriteMatch && req.method === 'PUT') {
		const score = LIBRARY.find((s) => s.id === Number(favoriteMatch[1]));
		if (!score) return json(res, 404, { detail: 'Score not found' });
		const body = await new Promise((resolve) => {
			let data = '';
			req.on('data', (c) => (data += c));
			req.on('end', () => resolve(JSON.parse(data || '{}')));
		});
		score.favorite = body.favorite === true;
		return json(res, 200, score);
	}
	const scoreMatch = url.pathname.match(/^\/scores\/(\d+)$/);
	if (scoreMatch && req.method === 'GET') {
		if (scoreMatch[1] === '1') {
			return json(res, 200, {
				id: 1,
				title: 'Moonlight Sonata',
				composer: 'Beethoven',
				pdf_path: 'moonlight.pdf'
			});
		}
		if (scoreMatch[1] === '2') {
			return json(res, 200, {
				id: 2,
				title: 'Long Suite',
				composer: 'Bach',
				pdf_path: 'real.pdf'
			});
		}
		return json(res, 404, { detail: 'Score not found' });
	}
	if (url.pathname === '/scores/2/sections' && req.method === 'GET') {
		return json(res, 200, LONG_TOC);
	}
	if (/^\/scores\/\d+\/annotations$/.test(url.pathname) && req.method === 'GET') {
		return json(res, 200, []);
	}
	if (url.pathname === '/pdf/real.pdf' && req.method === 'GET') {
		res.writeHead(200, { 'Content-Type': 'application/pdf', 'Content-Length': REAL_PDF.length });
		return res.end(REAL_PDF);
	}
	return json(res, 404, { detail: `stub: no handler for ${req.method} ${url.pathname}` });
});

server.listen(PORT, () => {
	console.log(`[e2e stub-backend] listening on http://localhost:${PORT}`);
});
