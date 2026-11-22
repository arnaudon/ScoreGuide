import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';
import type { UsageRow } from '#lib/types.js';
import { csvCell } from '#lib/csv.js';

const COLUMNS: (keyof UsageRow)[] = [
	'user_id',
	'username',
	'email',
	'plan',
	'requests',
	'input_tokens',
	'output_tokens',
	'cost',
	'ai_allowance',
	'storage_used',
	'storage_limit'
];

/** The admin usage table for a month (`?month=YYYY-MM`, default this one) as CSV. */
export const GET: RequestHandler = async ({ url, cookies, fetch }) => {
	const token = cookies.get('access_token');
	if (!token) error(401, 'Unauthorized');
	const month = url.searchParams.get('month') ?? '';
	const valid = /^\d{4}-(0[1-9]|1[0-2])$/.test(month);
	const res = await apiFetch(fetch, token)(`/admin/usage${valid ? `?month=${month}` : ''}`);
	if (!res.ok) error(res.status, 'Usage unavailable');
	const rows: UsageRow[] = await res.json();
	const lines = [
		COLUMNS.join(','),
		...rows.map((r) => COLUMNS.map((c) => csvCell(r[c])).join(','))
	];
	const name = `scoreguide-usage-${valid ? month : 'current'}.csv`;
	return new Response(lines.join('\n') + '\n', {
		headers: {
			'Content-Type': 'text/csv; charset=utf-8',
			'Content-Disposition': `attachment; filename="${name}"`
		}
	});
};
