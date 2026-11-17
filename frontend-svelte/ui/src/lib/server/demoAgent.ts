import type { Score } from '#lib/types.js';
import * as m from '#lib/paraglide/messages.js';

/** Lowercase, accent-free words, so "Pathétique" matches "pathetique". */
function words(text: string): string[] {
	return text
		.normalize('NFD')
		.replace(/\p{Diacritic}/gu, '')
		.toLowerCase()
		.split(/[^a-z0-9]+/)
		.filter((w) => w.length >= 4);
}

// Question words (en/fr) mapped to score fields, for asks like
// "something easy" or "une sonate romantique".
const HINTS: [RegExp, (s: Score) => boolean][] = [
	[/\b(easy|facile|simple|beginner|debutant)/, (s) => s.difficulty === 'easy'],
	[
		/\b(hard|difficult|advanced|challeng|avance)/,
		(s) => s.difficulty === 'advanced' || s.difficulty === 'expert'
	],
	[/\bbaroque/, (s) => s.period === 'Baroque'],
	[/\b(classical|classique)/, (s) => s.period === 'Classical'],
	[/\b(romantic|romantique)/, (s) => s.period === 'Romantic'],
	[/\b(modern|impression)/, (s) => s.period === 'Modernist'],
	[/\bsonat/, (s) => /sonat/i.test(s.form)],
	[/\bprel/, (s) => /prel/i.test(s.form)],
	[/\b(movement|mouvement)/, (s) => /sonat/i.test(s.form)]
];

/**
 * Scripted stand-in for the AI assistant on the read-only demo account:
 * picks scores from the demo library by composer, title or a few hints
 * (period, difficulty, form), so visitors see what the real assistant does
 * without spending model credits.
 */
export function demoAgentAnswer(question: string, scores: Score[]) {
	const asked = new Set(words(question));
	const plain = words(question).join(' ');
	const byName = scores.filter((s) =>
		[...words(s.composer), ...words(s.title)].some((w) => asked.has(w))
	);
	const hints = HINTS.filter(([re]) => re.test(plain));
	const matches = byName.length
		? byName
		: hints.length
			? scores.filter((s) => hints.every(([, ok]) => ok(s)))
			: [];

	if (!matches.length) {
		return {
			response: m.demo_agent_fallback({ count: scores.length }),
			score_ids: scores.map((s) => s.id)
		};
	}
	const list = matches.map((s) => `• ${s.composer} — ${s.title}`).join('\n');
	return {
		response: `${m.demo_agent_found({ count: matches.length })}\n\n${list}`,
		score_ids: matches.map((s) => s.id)
	};
}
