import { fail } from '@sveltejs/kit';
import type { Actions } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';
import * as m from '#lib/paraglide/messages.js';
import { detailMessage } from '#lib/apiError.js';
import { callBackend } from '#lib/server/callBackend.js';

export const actions: Actions = {
	default: async ({ request, fetch }) => {
		const data = await request.formData();
		const email = data.get('email');

		if (!email) {
			return fail(400, { email: email?.toString(), error: m.err_missing_email() });
		}

		const api = apiFetch(fetch, undefined);
		const answer = await callBackend(() =>
			api('/forgot-password', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email: email.toString() })
			})
		);
		if (!answer) {
			return fail(503, { email: email.toString(), error: m.err_service_unavailable() });
		}
		if (!answer.res.ok) {
			return fail(answer.res.status, {
				email: email.toString(),
				error: detailMessage(answer.data.detail, m.err_something_went_wrong())
			});
		}

		return { email: email.toString(), message: answer.data.message as string | undefined };
	}
};
