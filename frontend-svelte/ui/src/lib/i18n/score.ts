import type { Score, IMSLPScore } from '$lib/types.js';
import { getLocale } from '$lib/paraglide/runtime.js';

/**
 * Fields on `Score` (and only `Score`) that also have a `_fr` counterpart.
 * Updated when shared/scores.py grows new localised fields.
 */
const LOCALIZED_FIELDS = ['short_description', 'long_description'] as const;
export type LocalizedField = (typeof LOCALIZED_FIELDS)[number];

export function isLocalizedField(key: string): key is LocalizedField {
	return (LOCALIZED_FIELDS as readonly string[]).includes(key);
}

/**
 * Returns the locale-appropriate value of a Score field.
 *
 * - For `LocalizedField` keys in French locale, prefers `${key}_fr` when
 *   non-empty.
 * - Falls back to the English source field or `''`.
 *
 * `IMSLPScore` doesn't carry `_fr` variants today, so the helper just
 * returns the English value for it.
 */
export function localizedField(
	score: Score | IMSLPScore | Record<string, unknown>,
	key: LocalizedField,
	locale: string = getLocale()
): string {
	const record = score as Record<string, unknown>;
	if (locale.startsWith('fr')) {
		const fr = record[`${key}_fr`];
		if (typeof fr === 'string' && fr.length > 0) return fr;
	}
	const en = record[key];
	return typeof en === 'string' ? en : '';
}
