import { redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { dev } from '$app/env';

export const load: PageServerLoad = async ({ cookies }) => {
	cookies.delete('access_token', { path: '/', httpOnly: true, secure: !dev, sameSite: 'lax' });
	redirect(303, '/login');
};

export const actions: Actions = {
	default: async ({ cookies, request }) => {
		cookies.delete('access_token', { path: '/', httpOnly: true, secure: !dev, sameSite: 'lax' });
		// The demo banner's "create an account" lands on the sign-up form.
		const form = await request.formData().catch(() => null);
		redirect(303, form?.get('next') === 'signup' ? '/login?signup' : '/login');
	}
};
