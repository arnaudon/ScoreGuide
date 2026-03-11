import { redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ cookies }) => {
	cookies.delete('access_token', { path: '/' });
	redirect(303, '/login');
};

export const actions: Actions = {
	default: async ({ cookies }) => {
		cookies.delete('access_token', { path: '/' });
		redirect(303, '/login');
	}
};
