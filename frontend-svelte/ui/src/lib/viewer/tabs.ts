/** A score kept open in the reader's tab strip. */
export interface ReaderTab {
	id: number;
	title: string;
	composer: string;
}

/** Oldest tabs drop off past this many. */
export const MAX_TABS = 8;

/**
 * Add (or refresh) a tab. A new tab goes to the end; an existing one keeps
 * its place but takes the latest title. Past `max`, the oldest other tab
 * is dropped.
 */
export function openTab(tabs: ReaderTab[], tab: ReaderTab, max = MAX_TABS): ReaderTab[] {
	const at = tabs.findIndex((t) => t.id === tab.id);
	if (at >= 0) return tabs.map((t, i) => (i === at ? tab : t));
	const next = [...tabs, tab];
	return next.length > max ? next.slice(next.length - max) : next;
}

/**
 * Close a tab. Returns the remaining tabs and the one to show instead when
 * the closed tab was the active one: its right neighbour, else its left,
 * else none.
 */
export function closeTab(
	tabs: ReaderTab[],
	id: number
): { tabs: ReaderTab[]; next: ReaderTab | null } {
	const at = tabs.findIndex((t) => t.id === id);
	if (at < 0) return { tabs, next: null };
	const rest = tabs.filter((t) => t.id !== id);
	return { tabs: rest, next: rest[at] ?? rest[at - 1] ?? null };
}

/** Parse stored tabs, ignoring anything malformed. */
export function parseTabs(raw: string | null): ReaderTab[] {
	try {
		const value: unknown = JSON.parse(raw ?? '[]');
		if (!Array.isArray(value)) return [];
		return value
			.filter(
				(t): t is ReaderTab =>
					!!t &&
					typeof t === 'object' &&
					Number.isInteger(t.id) &&
					typeof t.title === 'string' &&
					typeof t.composer === 'string'
			)
			.slice(-MAX_TABS);
	} catch {
		return [];
	}
}
