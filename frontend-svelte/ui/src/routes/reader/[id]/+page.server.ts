import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { dev } from '$app/env';
import { apiFetch } from '#lib/server/fetchApi.js';
import { buildScoreUpdatePayload } from '#lib/server/scoreUpdate.js';
import { tokenRole } from '#lib/server/token.js';
import type { Score, SectionsResponse } from '#lib/types.js';

/** Score ids are numbers: a decoded `..%2F…` must not become another backend path. */
const ID = /^\d+$/;

export const load: PageServerLoad = async ({ cookies, params, fetch }) => {
	const token = cookies.get('access_token');
	if (!token) {
		redirect(303, '/login');
	}

	if (!ID.test(params.id)) return { score: null, toc: EMPTY_TOC };

	const api = apiFetch(fetch, token);
	try {
		const response = await api(`/scores/${params.id}`);

		if (response.ok) {
			const score = (await response.json()) as Score;

			cookies.set('last_score_id', params.id, {
				path: '/',
				httpOnly: true,
				secure: !dev,
				sameSite: 'lax',
				maxAge: 60 * 60 * 24 * 30 // 30 days
			});

			// The home page's "continue" and play counts. The backend counts one play
			// per sitting; the demo account is read-only.
			if (tokenRole(token) !== 'demo') {
				api(`/scores/${params.id}/play`, { method: 'POST' }).catch((error) =>
					console.error('Failed to record play:', error)
				);
			}

			return { score, toc: await loadSections(api, params.id) };
		}
	} catch (error) {
		console.error('Failed to fetch score:', error);
	}

	return { score: null, toc: EMPTY_TOC };
};

const EMPTY_TOC: SectionsResponse = {
	status: 'none',
	sections: [],
	confidence: null,
	version: null,
	latest_version: 1
};

/** The table of contents is optional: never fail the page over it. */
async function loadSections(
	api: ReturnType<typeof apiFetch>,
	id: string
): Promise<SectionsResponse> {
	try {
		const res = await api(`/scores/${id}/sections`);
		if (res.ok) return (await res.json()) as SectionsResponse;
	} catch (error) {
		console.error('Failed to fetch sections:', error);
	}
	return EMPTY_TOC;
}

export const actions: Actions = {
	generate_toc: async ({ cookies, params, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) {
			return fail(401, { error: 'Unauthorized' });
		}
		if (!ID.test(params.id)) return fail(404, { tocError: true });
		try {
			const res = await apiFetch(fetch, token)(`/scores/${params.id}/sections/generate`, {
				method: 'POST'
			});
			if (!res.ok) {
				return fail(res.status, { tocError: true });
			}
			return { tocStarted: true };
		} catch (error) {
			console.error('Generate TOC error:', error);
			return fail(500, { tocError: true });
		}
	},
	report_toc: async ({ request, cookies, params, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) {
			return fail(401, { reportError: true });
		}
		if (!ID.test(params.id)) return fail(404, { reportError: true });
		const comment = String((await request.formData()).get('comment') ?? '').slice(0, 1000);
		try {
			const res = await apiFetch(fetch, token)(`/scores/${params.id}/sections/report`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ comment })
			});
			if (!res.ok) {
				return fail(res.status, { reportError: true });
			}
			return { tocReported: true };
		} catch (error) {
			console.error('Report TOC error:', error);
			return fail(500, { reportError: true });
		}
	},
	update_score: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) {
			return fail(401, { error: 'Unauthorized' });
		}

		const data = await request.formData();
		const id = data.get('id');
		if (!id || !ID.test(id.toString())) {
			return fail(400, { error: 'Missing score ID' });
		}

		const payload = buildScoreUpdatePayload(data);

		const api = apiFetch(fetch, token);
		try {
			const res = await api(`/scores/${id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});

			if (!res.ok) {
				return fail(res.status, { error: 'Failed to update score' });
			}

			return { success: true, scoreUpdated: true };
		} catch (error) {
			console.error('Update score error:', error);
			return fail(500, { error: 'Server error when contacting backend' });
		}
	}
};
