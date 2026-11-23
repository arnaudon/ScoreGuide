import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { dev } from '$app/env';
import { apiFetch } from '#lib/server/fetchApi.js';
import * as m from '#lib/paraglide/messages.js';
import { detailMessage } from '#lib/apiError.js';
import { passwordLengthOk } from '#lib/password.js';

export const load: PageServerLoad = async ({ cookies, fetch }) => {
	const token = cookies.get('access_token');

	if (!token) {
		redirect(303, '/login');
	}

	const api = apiFetch(fetch, token);
	const res = await api('/user');

	if (!res.ok) {
		redirect(303, '/login');
	}

	const user = await res.json();
	return { user };
};

export const actions: Actions = {
	update_profile: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) return fail(401, { error: m.err_unauthorized() });

		const data = await request.formData();
		const instrument = data.get('instrument');
		const email = data.get('email');
		// Sent only when the form has the field; an empty text clears the profile.
		const musicProfile = data.get('music_profile');

		const api = apiFetch(fetch, token);
		const res = await api('/user', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				instrument: instrument?.toString(),
				email: email?.toString(),
				music_profile: musicProfile === null ? undefined : musicProfile.toString()
			})
		});

		if (!res.ok) {
			const result = await res.json();
			return fail(res.status, {
				form: 'profile',
				error: detailMessage(result.detail, m.err_update_profile())
			});
		}

		return { form: 'profile', success: true };
	},
	update_password: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) return fail(401, { error: m.err_unauthorized() });

		const data = await request.formData();
		const current_password = data.get('current_password');
		const new_password = data.get('new_password');
		const confirm_password = data.get('confirm_password');

		if (!current_password || !new_password || !confirm_password) {
			return fail(400, { form: 'password', error: m.err_all_fields_required() });
		}

		if (new_password !== confirm_password) {
			return fail(400, { form: 'password', error: m.err_new_passwords_mismatch() });
		}

		if (!passwordLengthOk(new_password.toString())) {
			return fail(400, { form: 'password', error: m.err_password_length() });
		}

		const api = apiFetch(fetch, token);
		const res = await api('/user/password', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				current_password: current_password.toString(),
				new_password: new_password.toString()
			})
		});

		if (!res.ok) {
			const result = await res.json();
			return fail(res.status, {
				form: 'password',
				error: detailMessage(result.detail, m.err_update_password())
			});
		}

		// The change signed out every session, this one included: keep the
		// user logged in here with the fresh token the backend returns.
		const result = await res.json().catch(() => ({}));
		if (typeof result.access_token === 'string') {
			cookies.set('access_token', result.access_token, {
				path: '/',
				httpOnly: true,
				secure: !dev,
				sameSite: 'lax',
				maxAge: 60 * 60 * 24 // the backend's 1-day token
			});
		}
		return { form: 'password', success: true };
	},

	delete_account: async ({ cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) return fail(401, { error: m.err_unauthorized() });

		const api = apiFetch(fetch, token);
		const res = await api('/user', { method: 'DELETE' });

		if (!res.ok) {
			return fail(res.status, { form: 'delete', error: m.err_delete_account() });
		}

		cookies.delete('access_token', { path: '/', httpOnly: true, secure: !dev, sameSite: 'lax' });
		redirect(303, '/login');
	}
};
