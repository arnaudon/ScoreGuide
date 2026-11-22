import { fail, isRedirect, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';
import * as m from '#lib/paraglide/messages.js';
import { detailMessage } from '#lib/apiError.js';
import { parseWeights } from '#lib/modelWeights.js';
import type { Credentials, ImslpProgress, PlanSettings, TocReport, UsageRow } from '#lib/types.js';

const CREDENTIAL_NAMES = ['google_api_key', 'infomaniak_api_key', 'infomaniak_product_id'];

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;

export const load: PageServerLoad = async ({ cookies, fetch, url }) => {
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

		let credentials: Credentials | null = null;
		const credentialsResponse = await api('/admin/credentials');
		if (credentialsResponse.ok) {
			credentials = await credentialsResponse.json();
		}

		let tocReports: TocReport[] = [];
		const reportsResponse = await api('/admin/toc-reports');
		if (reportsResponse.ok) {
			tocReports = await reportsResponse.json();
		}

		let planSettings: PlanSettings | null = null;
		const plansResponse = await api('/admin/plans');
		if (plansResponse.ok) {
			planSettings = await plansResponse.json();
		}

		// This month's usage (users table) and the month picked for the usage table.
		const month = MONTH.test(url.searchParams.get('month') ?? '')
			? (url.searchParams.get('month') as string)
			: '';
		let usageNow: UsageRow[] = [];
		const usageResponse = await api('/admin/usage');
		if (usageResponse.ok) {
			usageNow = await usageResponse.json();
		}
		let usageMonth = usageNow;
		if (month) {
			const monthResponse = await api(`/admin/usage?month=${month}`);
			usageMonth = monthResponse.ok ? await monthResponse.json() : [];
		}

		return {
			users,
			stats,
			progress,
			activeModels,
			credentials,
			tocReports,
			planSettings,
			usageNow,
			usageMonth,
			month
		};
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
		credentials: null as Credentials | null,
		tocReports: [] as TocReport[],
		planSettings: null as PlanSettings | null,
		usageNow: [] as UsageRow[],
		usageMonth: [] as UsageRow[],
		month: ''
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
	set_user_plan: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) return fail(401, { formId: 'plan', error: m.err_unauthorized() });
		const data = await request.formData();
		const userId = String(data.get('user_id') ?? '');
		const plan = String(data.get('plan') ?? '');
		if (!/^\d+$/.test(userId) || !['free', 'pro'].includes(plan)) {
			return fail(400, { formId: 'plan', error: m.err_update_plan() });
		}
		const limit = (name: string) => {
			const value = String(data.get(name) ?? '').trim();
			return value === '' ? null : Number(value);
		};
		const res = await apiFetch(fetch, token)(`/users/${userId}/plan`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				plan,
				ai_allowance: limit('ai_allowance'),
				storage_limit_mb: limit('storage_limit_mb')
			})
		});
		if (!res.ok) {
			const result = await res.json().catch(() => ({}));
			return fail(res.status, {
				formId: 'plan',
				error: detailMessage(result.detail, m.err_update_plan())
			});
		}
		return { formId: 'plan', success: true };
	},
	grant_tokens: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) return fail(401, { formId: 'grant', error: m.err_unauthorized() });
		const data = await request.formData();
		const userId = String(data.get('user_id') ?? '');
		const tokens = Number(String(data.get('tokens') ?? '').trim());
		if (!/^\d+$/.test(userId) || !Number.isInteger(tokens) || tokens <= 0) {
			return fail(400, { formId: 'grant', error: m.err_grant_tokens() });
		}
		const res = await apiFetch(fetch, token)(`/users/${userId}/grant`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ tokens })
		});
		if (!res.ok) {
			const result = await res.json().catch(() => ({}));
			return fail(res.status, {
				formId: 'grant',
				error: detailMessage(result.detail, m.err_grant_tokens())
			});
		}
		return { formId: 'grant', success: true };
	},
	set_plans: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) return fail(401, { formId: 'plans', error: m.err_unauthorized() });
		const data = await request.formData();
		const limits = Object.fromEntries(
			(['free', 'pro'] as const).map((plan) => [
				plan,
				{
					ai_tokens: Number(data.get(`${plan}_ai_tokens`)),
					storage_mb: Number(data.get(`${plan}_storage_mb`))
				}
			])
		);
		const weights = parseWeights(String(data.get('weights') ?? ''));
		if (weights === null) return fail(400, { formId: 'plans', error: m.err_model_weights() });
		const res = await apiFetch(fetch, token)('/admin/plans', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ limits, weights })
		});
		if (!res.ok) {
			const result = await res.json().catch(() => ({}));
			return fail(res.status, {
				formId: 'plans',
				error: detailMessage(result.detail, m.err_save_plans())
			});
		}
		return { formId: 'plans', success: true };
	},

	set_credentials: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		const data = await request.formData();
		// Only send what the admin typed (or asked to clear): blank fields keep
		// the stored value, since the page never has it.
		const credentials: Record<string, string> = {};
		for (const name of CREDENTIAL_NAMES) {
			const value = data.get(name)?.toString().trim() ?? '';
			if (value) credentials[name] = value;
			if (data.get(`clear_${name}`) === 'on') credentials[name] = '';
		}
		const api = apiFetch(fetch, token);
		const res = await api('/admin/credentials', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ credentials })
		});
		if (!res.ok) {
			return fail(res.status, { formId: 'credentials', error: m.err_save_credentials() });
		}
		return { formId: 'credentials', success: true };
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
