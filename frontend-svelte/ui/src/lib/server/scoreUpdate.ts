/**
 * Build a partial-update payload for `PUT /scores/{id}` from a FormData
 * submitted by the EditScoreDialog. Only fields present in formData are
 * included. Empty strings are forwarded (and overwrite the stored value on
 * the backend) — that's how the UI lets users clear a field. Mirrors the
 * backend `ScoreUpdate` schema (shared/shared/scores.py).
 */
const TEXT_FIELDS = [
	'title',
	'composer',
	'genre',
	'form',
	'style',
	'key',
	'instrumentation',
	'short_description',
	'long_description',
	'youtube_url',
	'period',
	'difficulty',
	'notable_interpreters'
] as const;

export function buildScoreUpdatePayload(data: FormData): Record<string, unknown> {
	const payload: Record<string, unknown> = {};
	for (const field of TEXT_FIELDS) {
		const value = data.get(field);
		if (value !== null) {
			payload[field] = value.toString();
		}
	}
	const yearRaw = data.get('year');
	if (yearRaw !== null && yearRaw !== '') {
		const yearNum = Number(yearRaw);
		if (!Number.isNaN(yearNum)) {
			payload.year = yearNum;
		}
	}
	return payload;
}
