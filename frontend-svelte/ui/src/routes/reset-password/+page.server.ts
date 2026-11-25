import { fail } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';
import * as m from '#lib/paraglide/messages.js';
import { detailMessage } from '#lib/apiError.js';
import { callBackend } from '#lib/server/callBackend.js';
import { passwordLengthOk } from '#lib/password.js';

export const load: PageServerLoad = async ({ url }) => {
	return { token: url.searchParams.get('token') ?? '' };
};

export const actions: Actions = {
	default: async ({ request, fetch }) => {
		const data = await request.formData();
		const token = data.get('token');
		const newPassword = data.get('new_password');
		const confirmPassword = data.get('confirm_password');

		if (!token) {
			return fail(400, { token: '', error: m.err_invalid_reset_link() });
		}

		if (!newPassword || !confirmPassword) {
			return fail(400, { token: token.toString(), error: m.err_missing_password() });
		}

		if (newPassword.toString() !== confirmPassword.toString()) {
			return fail(400, { token: token.toString(), error: m.err_passwords_mismatch() });
		}

		if (!passwordLengthOk(newPassword.toString())) {
			return fail(400, { token: token.toString(), error: m.err_password_length() });
		}

		const api = apiFetch(fetch, undefined);
		const answer = await callBackend(() =>
			api('/reset-password', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ token: token.toString(), new_password: newPassword.toString() })
			})
		);
		if (!answer) {
			return fail(503, { token: token.toString(), error: m.err_service_unavailable() });
		}
		if (!answer.res.ok) {
			return fail(answer.res.status, {
				token: token.toString(),
				error: detailMessage(answer.data.detail, m.err_something_went_wrong())
			});
		}

		return { success: true, message: answer.data.message as string | undefined };
	}
};
