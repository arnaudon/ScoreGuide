import { describe, expect, it } from 'vitest';
import { GET } from './+server.js';
import { csvCell } from '#lib/csv.js';
import { makeCookies, makeFetch, jsonResponse, event } from '../../test-helpers.js';

const ROW = {
	user_id: 1,
	username: 'ann, "the" pianist',
	email: null,
	plan: 'pro',
	requests: 3,
	input_tokens: 100,
	output_tokens: 20,
	cost: 120,
	granted: 0,
	ai_used: 500,
	ai_allowance: 5000,
	storage_used: 10,
	storage_limit: 20
};

function get(search: string, cookies = makeCookies({ access_token: 'tok' }), fetch = makeFetch()) {
	const url = new URL(`http://localhost/admin/usage.csv${search}`);
	return GET(event({ url, cookies, fetch }) as Parameters<typeof GET>[0]);
}

describe('GET /admin/usage.csv', () => {
	it('escapes cells and defuses formulas', () => {
		expect(csvCell('a,b')).toBe('"a,b"');
		expect(csvCell('say "hi"')).toBe('"say ""hi"""');
		expect(csvCell('=HYPERLINK(1)')).toBe("'=HYPERLINK(1)");
		expect(csvCell(null)).toBe('');
		expect(csvCell(42)).toBe('42');
	});

	it('returns the month as a CSV download', async () => {
		const fetch = makeFetch(async () => jsonResponse([ROW]));
		const res = await get('?month=2026-11', undefined, fetch);
		expect(String(fetch.mock.calls[0][0])).toContain('/admin/usage?month=2026-11');
		expect(res.headers.get('Content-Disposition')).toContain('scoreguide-usage-2026-11.csv');
		const [header, line] = (await res.text()).trim().split('\n');
		expect(header.split(',')).toHaveLength(13);
		expect(line).toBe('1,"ann, ""the"" pianist",,pro,3,100,20,120,0,500,5000,10,20');
	});

	it('ignores a bad month and refuses without a login or admin rights', async () => {
		const fetch = makeFetch(async () => jsonResponse([]));
		const res = await get('?month=evil', undefined, fetch);
		expect(String(fetch.mock.calls[0][0])).toMatch(/\/admin\/usage$/);
		expect(res.headers.get('Content-Disposition')).toContain('current');
		await expect(get('', makeCookies())).rejects.toMatchObject({ status: 401 });
		const forbidden = makeFetch(async () => jsonResponse({ detail: 'no' }, 403));
		await expect(get('', undefined, forbidden)).rejects.toMatchObject({ status: 403 });
	});
});
