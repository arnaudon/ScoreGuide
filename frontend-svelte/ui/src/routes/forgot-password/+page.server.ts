import { fail } from '@sveltejs/kit';
import type { Actions } from './$types';
import { apiFetch } from '$lib/server/fetchApi.js';
import * as m from '$lib/paraglide/messages.js';

export const actions: Actions = {
	default: async ({ request, fetch }) => {
		const data = await request.formData();
		const email = data.get('email');

		if (!email) {
			return fail(400, { email: email?.toString(), error: m.err_missing_email() });
		}

		const api = apiFetch(fetch, undefined);
		const response = await api('/forgot-password', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ email: email.toString() })
		});

		if (!response.ok) {
			let errorMsg = m.err_something_went_wrong();
			try {
				const result = await response.json();
				errorMsg = result.detail || errorMsg;
			} catch (e) {
				console.error('Failed to parse forgot-password error response', e);
			}
			return fail(response.status, { email: email.toString(), error: errorMsg });
		}

		const result = await response.json();
		return { email: email.toString(), message: result.message };
	}
};
