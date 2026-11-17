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

/**
 * Same interface as {@link annotationsApi}, but kept in this browser's
 * localStorage instead of the server. Used for the read-only demo account,
 * whose writes the backend refuses: visitors can still try the pencil and
 * notes, and their marks stay on their own device.
 */
export function localAnnotationsApi(scoreId: number, storage: Storage | null = safeLocalStorage()) {
	const key = `demo.annotations.${scoreId}`;
	// In-memory fallback when storage is unavailable (private mode, blocked).
	let memory: Annotation[] = [];

	function read(): Annotation[] {
		if (!storage) return memory;
		try {
			const parsed = JSON.parse(storage.getItem(key) ?? '[]');
			return Array.isArray(parsed) ? parsed : [];
		} catch {
			return [];
		}
	}

	function write(items: Annotation[]) {
		memory = items;
		try {
			storage?.setItem(key, JSON.stringify(items));
		} catch {
			// Quota or blocked storage: keep the in-memory copy for this visit.
		}
	}

	function find(items: Annotation[], id: number) {
		const index = items.findIndex((a) => a.id === id);
		if (index === -1) throw new AnnotationsError(404);
		return index;
	}

	return {
		list: async () => read(),
		create: async (page: number, data: AnnotationData) => {
			const items = read();
			const now = new Date().toISOString();
			const created: Annotation = {
				id: items.reduce((max, a) => Math.max(max, a.id), 0) + 1,
				score_id: scoreId,
				page,
				kind: data.kind,
				data,
				created_at: now,
				updated_at: now
			};
			write([...items, created]);
			return created;
		},
		update: async (id: number, page: number, data: AnnotationData) => {
			const items = read();
			const index = find(items, id);
			const updated = {
				...items[index],
				page,
				kind: data.kind,
				data,
				updated_at: new Date().toISOString()
			};
			items[index] = updated;
			write(items);
			return updated;
		},
		remove: async (id: number) => {
			write(read().filter((a) => a.id !== id));
		},
		clearPage: async (page: number) => {
			write(read().filter((a) => a.page !== page));
		}
	};
}

function safeLocalStorage(): Storage | null {
	try {
		return typeof localStorage === 'undefined' ? null : localStorage;
	} catch {
		return null;
	}
}
