/**
 * Client for the user's annotations on a score (mirrors
 * `shared/shared/annotations.py`). Coordinates are fractions of the page
 * (0..1, origin top-left).
 */

export type InkData = {
	kind: 'ink';
	points: [number, number][];
	color: string;
	/** Fraction of the page width. */
	width: number;
};

export type TextData = {
	kind: 'text';
	x: number;
	y: number;
	text: string;
	color: string;
};

export type AnnotationData = InkData | TextData;

export type Annotation = {
	id: number;
	score_id: number;
	page: number;
	kind: AnnotationData['kind'];
	data: AnnotationData;
	created_at: string;
	updated_at: string;
};

type FetchFn = typeof fetch;

export class AnnotationsError extends Error {
	constructor(readonly status: number) {
		super(`Annotations request failed (${status})`);
	}
}

export function annotationsApi(scoreId: number, fetchFn: FetchFn = fetch) {
	const base = `/api/scores/${scoreId}/annotations`;

	async function send<T>(path: string, init: RequestInit = {}): Promise<T> {
		const res = await fetchFn(path, {
			...init,
			headers: init.body ? { 'Content-Type': 'application/json' } : undefined
		});
		if (!res.ok) throw new AnnotationsError(res.status);
		return (res.status === 204 ? undefined : await res.json()) as T;
	}

	return {
		list: () => send<Annotation[]>(base),
		create: (page: number, data: AnnotationData) =>
			send<Annotation>(base, { method: 'POST', body: JSON.stringify({ page, data }) }),
		update: (id: number, page: number, data: AnnotationData) =>
			send<Annotation>(`${base}/${id}`, { method: 'PUT', body: JSON.stringify({ page, data }) }),
		remove: (id: number) => send<void>(`${base}/${id}`, { method: 'DELETE' }),
		clearPage: (page: number) => send<void>(`${base}?page=${page}`, { method: 'DELETE' })
	};
}
