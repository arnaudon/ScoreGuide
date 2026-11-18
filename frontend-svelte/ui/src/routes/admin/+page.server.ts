import { fail, isRedirect, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';
import * as m from '#lib/paraglide/messages.js';
import type { ImslpProgress, TocReport } from '#lib/types.js';

export const load: PageServerLoad = async ({ cookies, fetch }) => {
	const token = cookies.get('access_token');

	if (!token) {
		redirect(303, '/login');
	}

	const api = apiFetch(fetch, token);
	try {
		const adminCheck = await api('/is_admin');
		if (!adminCheck.ok || !(await adminCheck.json())) {
			redirect(303, '/');
		}

		const response = await api('/users');

		let users = [];
		if (response.ok) {
			users = await response.json();
		}

		let stats = { total_works: 0, total_composers: 0 };
		const statsResponse = await api('/imslp/stats');
		if (statsResponse.ok) {
			stats = await statsResponse.json();
		}

		let progress: ImslpProgress = { status: 'idle', start: 0, works: 0, error: '' };
		const progressResponse = await api('/imslp/progress', { method: 'POST' });
		if (progressResponse.ok) {
			progress = await progressResponse.json();
		}

		let activeModels = { main: '', imslp: '', complete: '' };
		const modelResponse = await api('/admin/model');
		if (modelResponse.ok) {
			const resData = await modelResponse.json();
			activeModels = resData.models || { main: '', imslp: '', complete: '' };
		}

		let tocReports: TocReport[] = [];
		const reportsResponse = await api('/admin/toc-reports');
		if (reportsResponse.ok) {
			tocReports = await reportsResponse.json();
		}

		return { users, stats, progress, activeModels, tocReports };
	} catch (error) {
		// redirect() throws a Redirect, which we must let propagate.
		if (isRedirect(error)) throw error;
		console.error('Failed to fetch admin data:', error);
	}

	return {
		users: [],
		stats: { total_works: 0, total_composers: 0 },
		progress: { status: 'idle', start: 0, works: 0, error: '' } as ImslpProgress,
		activeModels: { main: '', imslp: '', complete: '' },
		tocReports: [] as TocReport[]
	};
};

export const actions: Actions = {
	resolve_toc_report: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		const id = (await request.formData()).get('id');
		if (!token || !id || !/^\d+$/.test(String(id))) {
			return fail(400, { error: 'Missing report id' });
		}
		const res = await apiFetch(fetch, token)(`/admin/toc-reports/${id}/resolve`, {
			method: 'POST'
		});
		if (!res.ok) {
			return fail(res.status, { error: 'Failed to resolve report' });
		}
	},
	refill_credits: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		const data = await request.formData();
		const userId = data.get('user_id');

		if (!userId) {
			return fail(400, { formId: 'credits', error: m.err_user_id_required() });
		}

		const api = apiFetch(fetch, token);
		const res = await api(`/users/${userId}/refill_credits`, { method: 'POST' });

		if (!res.ok) {
			const result = await res.json().catch((e) => {
				console.error('Failed to parse refill_credits error', e);
				return {};
			});
			return fail(res.status, {
				formId: 'credits',
				error: result.detail || m.err_refill_credits()
			});
		}
	},
	set_credits: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		const data = await request.formData();
		const userId = data.get('user_id');
		const max_credits = data.get('max_credits');

		if (!userId || max_credits === null) {
			return fail(400, { formId: 'credits', error: m.err_user_id_credits_required() });
		}

		const api = apiFetch(fetch, token);
		const res = await api(`/users/${userId}/credits`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ max_credits: Number(max_credits) })
		});

		if (!res.ok) {
			const result = await res.json().catch((e) => {
				console.error('Failed to parse set_credits error', e);
				return {};
			});
			return fail(res.status, {
				formId: 'credits',
				error: result.detail || m.err_update_credits()
			});
		}
	},
	set_models: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		const data = await request.formData();
		const models = {
			main: data.get('model_main')?.toString() || '',
			imslp: data.get('model_imslp')?.toString() || '',
			complete: data.get('model_complete')?.toString() || ''
		};
		const api = apiFetch(fetch, token);
		const res = await api('/admin/model', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ models })
		});

		if (!res.ok) {
			const result = await res.json().catch(() => ({}));
			return fail(res.status, {
				formId: 'models',
				error: result.detail || m.err_save_models()
			});
		}
		return { formId: 'models', success: true };
	},
	update: async ({ request, cookies, fetch }) => {
		const data = await request.formData();
		// Resume a stopped sync unless asked to start over.
		const query = data.get('restart') === 'true' ? '?restart=true' : '';
		const token = cookies.get('access_token');
		const api = apiFetch(fetch, token);
		return imslpResult(await api(`/imslp/start${query}`, { method: 'POST' }));
	},
	empty: async ({ cookies, fetch }) => {
		const token = cookies.get('access_token');
		const api = apiFetch(fetch, token);
		return imslpResult(await api('/imslp/empty', { method: 'POST' }));
	},
	cancel: async ({ cookies, fetch }) => {
		const token = cookies.get('access_token');
		const api = apiFetch(fetch, token);
		return imslpResult(await api('/imslp/cancel', { method: 'POST' }));
	}
};

/** Surface a failed IMSLP job call on the page instead of silently dropping it. */
async function imslpResult(res: Response) {
	if (res.ok) return;
	const result = await res.json().catch(() => ({}));
	return fail(res.status, {
		formId: 'imslp',
		error: result.detail || m.err_imslp_request({ status: res.status })
	});
}
