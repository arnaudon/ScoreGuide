import { fail, redirect } from '@sveltejs/kit';
import { scoreFromImslp } from '#lib/imslp.js';
import type { Actions, PageServerLoad } from './$types';
import { dev } from '$app/env';
import { apiFetch } from '#lib/server/fetchApi.js';
import { buildScoreUpdatePayload } from '#lib/server/scoreUpdate.js';
import type { Score, User } from '#lib/types.js';
import { formBool } from '#lib/server/formBool.js';
import * as m from '#lib/paraglide/messages.js';

export const load: PageServerLoad = async ({ cookies, fetch }) => {
	const token = cookies.get('access_token');
	if (!token) {
		redirect(303, '/login');
	}

	const api = apiFetch(fetch, token);

	async function fetchUser(): Promise<User> {
		const res = await api('/user');
		if (!res.ok) {
			cookies.delete('access_token', { path: '/', httpOnly: true, secure: !dev, sameSite: 'lax' });
			redirect(303, '/login');
		}
		return (await res.json()) as User;
	}

	async function fetchScores(): Promise<Score[]> {
		const res = await api('/scores');
		return res.ok ? ((await res.json()) as Score[]) : [];
	}

	try {
		const [user, scores] = await Promise.all([fetchUser(), fetchScores()]);
		return { user, scores };
	} catch (error) {
		console.error('Failed to fetch page data:', error);
		redirect(303, '/login');
	}
};

export const actions: Actions = {
	upload: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) {
			return fail(401, { error: m.err_unauthorized() });
		}

		const data = await request.formData();
		const title = data.get('title');
		const composer = data.get('composer');
		const file = data.get('file') as File;

		if (!title || !composer || !file || file.size === 0) {
			return fail(400, { error: m.err_missing_fields() });
		}

		const api = apiFetch(fetch, token);
		try {
			// 1. Upload PDF
			let uploadFilename = file.name;
			if (!uploadFilename.toLowerCase().endsWith('.pdf')) {
				uploadFilename += '.pdf';
			}

			const formData = new FormData();
			formData.append('file', file, uploadFilename);
			const uploadRes = await api('/pdf', { method: 'POST', body: formData });

			if (!uploadRes.ok) {
				return fail(uploadRes.status, { error: m.err_upload_pdf() });
			}

			const uploadData = await uploadRes.json();
			const filename = uploadData.file_id || uploadFilename;

			// 2. Save the score with the user's data, so the uploaded PDF is
			// attached even if the agent then fails (or the user is out of credits).
			const scoreRes = await api('/scores', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					title: title.toString(),
					composer: composer.toString(),
					pdf_path: filename,
					source: 'manual'
				})
			});

			if (!scoreRes.ok) {
				return fail(scoreRes.status, { error: m.err_save_score() });
			}
			const saved = (await scoreRes.json().catch(() => null)) as { id?: unknown } | null;

			// 3. Complete it with the agent: the backend fills in the stored
			// score's details and saves them. It can be re-completed later.
			const completeRes = await api('/complete_score', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ score_id: saved?.id, detailed: formBool(data, 'detailed') })
			});
			const completionFailed = !completeRes.ok;
			// Keep the backend's reason (e.g. "out of credits") so the user knows why.
			const completionError = completionFailed ? await errorDetail(completeRes) : undefined;

			return { success: true, scoreAdded: true, completionFailed, completionError };
		} catch (error) {
			console.error('Upload error:', error);
			return fail(500, { error: m.err_backend_unreachable() });
		}
	},
	ask_agent: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) {
			return fail(401, { formId: 'agent', error: m.err_unauthorized() });
		}

		const data = await request.formData();
		const question = data.get('question');
		const messageHistoryRaw = data.get('message_history');

		if (!question) {
			return fail(400, { formId: 'agent', error: m.err_missing_prompt() });
		}

		let messageHistory = null;
		if (messageHistoryRaw) {
			try {
				messageHistory = JSON.parse(messageHistoryRaw.toString());
			} catch (e) {
				console.error('Failed to parse message_history', e);
			}
		}

		const api = apiFetch(fetch, token);
		try {
			const scoresRes = await api('/scores');
			const scores_deps = scoresRes.ok ? await scoresRes.json() : [];
			const deps = JSON.stringify({ scores: scores_deps });

			const res = await api('/imslp_agent', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					prompt: question.toString(),
					deps,
					message_history: messageHistory
				})
			});

			if (!res.ok) {
				const result = await res.json().catch((e) => {
					console.error('Failed to parse imslp_agent error', e);
					return {};
				});
				return fail(res.status, { formId: 'agent', error: result.detail || m.err_query_agent() });
			}

			const json = await res.json();
			let scores = [];
			const score_ids = json.response?.score_ids || [];
			const agent_response_text = json.response?.response || '';

			if (score_ids.length > 0) {
				const idsParam = encodeURIComponent(JSON.stringify(score_ids));
				const idScoresRes = await api(`/imslp/scores_by_ids?score_ids=${idsParam}`);
				if (idScoresRes.ok) {
					scores = await idScoresRes.json();
				}
			}

			const returned_message_history = json.response?.message_history || messageHistory;

			return {
				success: true,
				question: question.toString(),
				agent_results: {
					response: agent_response_text,
					scores,
					message_history: returned_message_history
				}
			};
		} catch (error) {
			console.error('Ask agent error:', error);
			return fail(500, { formId: 'agent', error: m.err_backend_unreachable() });
		}
	},
	add_imslp: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) {
			return fail(401, { error: m.err_unauthorized() });
		}

		const data = await request.formData();
		const imslp_id = data.get('imslp_id');
		const file = data.get('file') as File;

		if (!imslp_id || !file || file.size === 0) {
			return fail(400, { error: m.err_missing_imslp_or_pdf() });
		}

		const api = apiFetch(fetch, token);
		try {
			// 1. Upload PDF
			let uploadFilename = file.name;
			if (!uploadFilename.toLowerCase().endsWith('.pdf')) {
				uploadFilename += '.pdf';
			}

			const formData = new FormData();
			formData.append('file', file, uploadFilename);
			const uploadRes = await api('/pdf', { method: 'POST', body: formData });

			if (!uploadRes.ok) {
				return fail(uploadRes.status, { error: m.err_upload_pdf() });
			}

			const uploadData = await uploadRes.json();
			const filename = uploadData.file_id || uploadFilename;

			// 2. Fetch IMSLP Score Details
			const idsParam = encodeURIComponent(JSON.stringify([Number(imslp_id)]));
			const imslpRes = await api(`/imslp/scores_by_ids?score_ids=${idsParam}`);

			if (!imslpRes.ok) {
				return fail(imslpRes.status, { error: m.err_fetch_imslp() });
			}

			const imslpScores = await imslpRes.json();
			if (!imslpScores || imslpScores.length === 0) {
				return fail(404, { error: m.err_imslp_not_found() });
			}

			const newScore = scoreFromImslp(imslpScores[0], filename);

			const scoreRes = await api('/scores', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(newScore)
			});

			if (!scoreRes.ok) {
				return fail(scoreRes.status, { error: m.err_add_score() });
			}

			const saved = (await scoreRes.json().catch(() => null)) as { id?: unknown } | null;
			const scoreId = typeof saved?.id === 'number' ? saved.id : null;
			return { success: true, scoreAdded: true, scoreId };
		} catch (error) {
			console.error('Add IMSLP error:', error);
			return fail(500, { error: m.err_backend_unreachable() });
		}
	},
	recomplete: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) {
			return fail(401, { error: m.err_unauthorized() });
		}

		const data = await request.formData();
		const id = data.get('id');

		if (!id) {
			return fail(400, { error: m.err_missing_fields() });
		}

		const api = apiFetch(fetch, token);
		try {
			// The backend completes the stored score and saves it.
			const completeRes = await api('/complete_score', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ score_id: Number(id), detailed: formBool(data, 'detailed') })
			});

			if (completeRes.status === 409) {
				return fail(409, { error: m.completion_already_running() });
			}
			if (!completeRes.ok) {
				return fail(completeRes.status, {
					error: (await errorDetail(completeRes)) || m.err_complete_score()
				});
			}

			return { success: true };
		} catch (error) {
			console.error('Recomplete error:', error);
			return fail(500, { error: m.err_backend_unreachable() });
		}
	},
	delete: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) {
			return fail(401, { error: m.err_unauthorized() });
		}

		const data = await request.formData();
		const id = data.get('id');

		if (!id) {
			return fail(400, { error: m.err_missing_score_id() });
		}

		const api = apiFetch(fetch, token);
		try {
			const res = await api(`/scores/${id}`, { method: 'DELETE' });

			if (!res.ok) {
				return fail(res.status, { error: m.err_delete_score() });
			}

			return { success: true };
		} catch (error) {
			console.error('Delete error:', error);
			return fail(500, { error: m.err_backend_unreachable() });
		}
	},
	update_score: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) {
			return fail(401, { error: m.err_unauthorized() });
		}

		const data = await request.formData();
		const id = data.get('id');
		if (!id) {
			return fail(400, { error: m.err_missing_score_id() });
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
				return fail(res.status, { error: m.err_update_score() });
			}

			return { success: true, scoreUpdated: true };
		} catch (error) {
			console.error('Update score error:', error);
			return fail(500, { error: m.err_backend_unreachable() });
		}
	}
};

/** The backend's `detail` message for a failed response, if it sent one. */
async function errorDetail(res: Response): Promise<string | undefined> {
	const body = await res.json().catch(() => ({}));
	return typeof body?.detail === 'string' ? body.detail : undefined;
}
