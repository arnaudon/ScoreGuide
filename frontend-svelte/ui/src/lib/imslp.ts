import type { IMSLPScore, ImslpResult } from '#lib/types.js';
import * as m from '#lib/paraglide/messages.js';

/** Instrument filter values: matched against IMSLP's (English) instrumentation. */
export const INSTRUMENTS = [
	'piano',
	'organ',
	'harpsichord',
	'guitar',
	'violin',
	'cello',
	'flute',
	'voice',
	'chorus',
	'orchestra'
] as const;

/** Matches `shared.scores.Period`. */
export const PERIODS = [
	'Medieval',
	'Renaissance',
	'Baroque',
	'Classical',
	'Romantic',
	'Modernist',
	'Postmodernist'
] as const;

const INSTRUMENT_LABELS: Record<string, () => string> = {
	piano: m.instrument_piano,
	organ: m.instrument_organ,
	harpsichord: m.instrument_harpsichord,
	guitar: m.instrument_guitar,
	violin: m.instrument_violin,
	cello: m.instrument_cello,
	flute: m.instrument_flute,
	voice: m.instrument_voice,
	chorus: m.instrument_chorus,
	orchestra: m.instrument_orchestra
};

const PERIOD_LABELS: Record<string, () => string> = {
	Medieval: m.period_medieval,
	Renaissance: m.period_renaissance,
	Baroque: m.period_baroque,
	Classical: m.period_classical,
	Romantic: m.period_romantic,
	Modernist: m.period_modernist,
	Postmodernist: m.period_postmodernist
};

export const instrumentLabel = (value: string) => INSTRUMENT_LABELS[value]?.() ?? value;
export const periodLabel = (value: string) => PERIOD_LABELS[value]?.() ?? value;

/**
 * Body for `POST /scores` from a catalogue entry: links it (`imslp_id`), puts
 * the catalogue number in the title, and leaves unknown values to the backend
 * defaults instead of sending placeholders.
 */
export function scoreFromImslp(
	work: Pick<IMSLPScore | ImslpResult, 'id' | 'title' | 'composer'> &
		Partial<Pick<IMSLPScore, 'catalogue' | 'year' | 'period' | 'genre' | 'style' | 'key'>> & {
			instrumentation?: string;
		},
	pdfPath: string
): Record<string, unknown> {
	const catalogue = (work.catalogue ?? '').trim();
	const score: Record<string, unknown> = {
		title:
			catalogue && !work.title.includes(catalogue) ? `${work.title}, ${catalogue}` : work.title,
		composer: work.composer,
		pdf_path: pdfPath,
		imslp_id: work.id,
		instrumentation: work.instrumentation ?? '',
		style: work.style ?? '',
		key: work.key ?? '',
		genre: work.genre ?? ''
	};
	const year = Number(work.year);
	if (Number.isInteger(year) && year > 0) score.year = year;
	if (work.period) score.period = work.period;
	return score;
}
