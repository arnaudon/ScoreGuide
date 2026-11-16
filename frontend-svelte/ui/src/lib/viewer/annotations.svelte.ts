/**
 * Reactive store for the annotations of one score: optimistic local
 * updates saved through the API in the background, plus undo.
 */
import type { Annotation, AnnotationData, annotationsApi } from '#lib/annotations.js';

type Api = ReturnType<typeof annotationsApi>;

type Op =
	| { kind: 'created'; id: number }
	| { kind: 'deleted'; id: number; page: number; data: AnnotationData }
	| { kind: 'updated'; id: number; before: AnnotationData };

const MAX_UNDO = 50;

export class AnnotationStore {
	items: Annotation[] = $state([]);
	loaded = $state(false);
	error: 'load' | 'save' | null = $state(null);
	#undo: Op[] = $state([]);
	#nextTempId = -1;
	/** Optimistic (negative) id -> server request that will give the real id. */
	// eslint-disable-next-line svelte/prefer-svelte-reactivity -- bookkeeping, never rendered
	#pending = new Map<number, Promise<Annotation | null>>();

	constructor(private readonly api: Api) {}

	get canUndo(): boolean {
		return this.#undo.length > 0;
	}

	forPage(page: number): Annotation[] {
		return this.items.filter((a) => a.page === page);
	}

	async load(): Promise<void> {
		try {
			this.items = await this.api.list();
			this.error = null;
		} catch {
			this.error = 'load';
		} finally {
			this.loaded = true;
		}
	}

	/** Add an annotation; returns its (temporary, then real) id. */
	create(page: number, data: AnnotationData, { record = true } = {}): number {
		const tempId = this.#nextTempId--;
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- serialized immediately
		const now = new Date().toISOString();
		this.items.push({
			id: tempId,
			score_id: 0,
			page,
			kind: data.kind,
			data,
			created_at: now,
			updated_at: now
		});
		if (record) this.#push({ kind: 'created', id: tempId });

		const request = this.api
			.create(page, data)
			.then((saved) => {
				this.#replaceId(tempId, saved);
				return saved;
			})
			.catch(() => {
				this.items = this.items.filter((a) => a.id !== tempId);
				this.error = 'save';
				return null;
			})
			.finally(() => this.#pending.delete(tempId));
		this.#pending.set(tempId, request);
		return tempId;
	}

	async update(id: number, data: AnnotationData): Promise<void> {
		const current = this.items.find((a) => a.id === id);
		if (!current) return;
		this.#push({ kind: 'updated', id, before: current.data });
		await this.#applyUpdate(id, data);
	}

	async remove(id: number, { record = true } = {}): Promise<void> {
		const current = this.items.find((a) => a.id === id);
		if (!current) return;
		this.items = this.items.filter((a) => a.id !== id);
		if (record) this.#push({ kind: 'deleted', id, page: current.page, data: current.data });
		const realId = await this.#resolve(id);
		if (realId === null) return;
		try {
			await this.api.remove(realId);
		} catch {
			this.items.push(current);
			this.error = 'save';
		}
	}

	async undo(): Promise<void> {
		const op = this.#undo.pop();
		if (!op) return;
		if (op.kind === 'created') {
			await this.remove(this.#currentId(op.id), { record: false });
		} else if (op.kind === 'deleted') {
			// Older undo steps refer to the old id; point them at the copy.
			this.#aliases.set(op.id, this.create(op.page, op.data, { record: false }));
		} else {
			await this.#applyUpdate(this.#currentId(op.id), op.before);
		}
	}

	dismissError(): void {
		this.error = null;
	}

	// ---- internals ----

	/** Ids recorded in the undo stack may have been temporary. */
	// eslint-disable-next-line svelte/prefer-svelte-reactivity -- bookkeeping, never rendered
	#aliases = new Map<number, number>();

	#currentId(id: number): number {
		let current = id;
		for (
			let next = this.#aliases.get(current);
			next !== undefined;
			next = this.#aliases.get(current)
		) {
			current = next;
		}
		return current;
	}

	#replaceId(tempId: number, saved: Annotation) {
		this.#aliases.set(tempId, saved.id);
		const index = this.items.findIndex((a) => a.id === tempId);
		// Keep any local edit made while the create was in flight.
		if (index !== -1) this.items[index] = { ...saved, data: this.items[index].data };
	}

	async #resolve(id: number): Promise<number | null> {
		const real = this.#currentId(id);
		if (real >= 0) return real;
		const saved = await this.#pending.get(real);
		return saved ? saved.id : null;
	}

	async #applyUpdate(id: number, data: AnnotationData) {
		const index = this.items.findIndex((a) => a.id === id);
		if (index === -1) return;
		const previous = this.items[index];
		this.items[index] = { ...previous, kind: data.kind, data };
		const realId = await this.#resolve(id);
		if (realId === null) return;
		try {
			await this.api.update(realId, previous.page, data);
		} catch {
			const i = this.items.findIndex((a) => a.id === id || a.id === realId);
			if (i !== -1) this.items[i] = previous;
			this.error = 'save';
		}
	}

	#push(op: Op) {
		this.#undo.push(op);
		if (this.#undo.length > MAX_UNDO) this.#undo.shift();
	}
}
