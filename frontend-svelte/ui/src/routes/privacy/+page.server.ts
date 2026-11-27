import type { PageServerLoad } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';
import { vendorName } from '#lib/vendors.js';

export type AIModel = { name: string; vendor: string; host: string };

/** The models in use now; the page still renders without them. */
export const load: PageServerLoad = async ({ fetch }) => {
	try {
		const res = await apiFetch(fetch, undefined)('/ai-models');
		if (!res.ok) return { models: [] as AIModel[] };
		const body = (await res.json()) as { models?: AIModel[] };
		const models = Array.isArray(body.models) ? body.models : [];
		return { models: models.map((x) => ({ ...x, vendor: vendorName(x.vendor) })) };
	} catch {
		return { models: [] as AIModel[] };
	}
};
