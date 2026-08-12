import { fail } from '@sveltejs/kit';
import type { Actions } from './$types';
import { apiFetch } from '$lib/server/fetchApi.js';

export const actions: Actions = {
	default: async ({ request, fetch }) => {
		const data = await request.formData();
		const email = data.get('email');

		if (!email) {
			return fail(400, { email: email?.toString(), error: 'Missing email' });
		}

		const api = apiFetch(fetch, undefined);
		const response = await api('/forgot-password', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ email: email.toString() })
		});

		if (!response.ok) {
			let errorMsg = 'Something went wrong. Please try again.';
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
