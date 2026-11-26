import { httpUrl } from './url.js';

/**
 * A score's long description is plain text with a tiny, optional structure:
 * a line starting with `#`..`####` is a section heading, lines starting with
 * `- `, `* `, `• ` or `1. ` form a list, blank lines separate paragraphs,
 * `**bold**` and `*italic*` are honoured (AI models write them whatever the
 * prompt says), and http(s) URLs become links. Anything else stays plain text,
 * so old descriptions render as before. Nothing is ever interpreted as HTML.
 */
export type Inline = { text: string; href?: string; strong?: boolean; em?: boolean };
export type Block =
	| { kind: 'heading'; text: string }
	| { kind: 'paragraph'; parts: Inline[] }
	| { kind: 'list'; items: Inline[][] };

const URL_RE = /https?:\/\/[^\s<>"]+/g;

/** Split text into plain runs and links (trailing punctuation stays text). */
export function linkify(text: string): Inline[] {
	const parts: Inline[] = [];
	let last = 0;
	for (const match of text.matchAll(URL_RE)) {
		let url = match[0];
		// Drop trailing punctuation, but keep a ")" that closes a "(" in the URL
		// (Wikipedia: .../Piano_Sonata_No._8_(Beethoven)).
		for (;;) {
			const end = url.at(-1) ?? '';
			const unbalanced = end === ')' && url.split('(').length < url.split(')').length;
			if (!(/[.,;:!?\]]/.test(end) || unbalanced)) break;
			url = url.slice(0, -1);
		}
		const href = httpUrl(url);
		if (!href) continue;
		const start = match.index ?? 0;
		if (start > last) parts.push({ text: text.slice(last, start) });
		parts.push({ text: url, href });
		last = start + url.length;
	}
	if (last < text.length) parts.push({ text: text.slice(last) });
	return parts;
}

const EMPHASIS_RE = /\*\*(.+?)\*\*|\*(\S(?:.*?\S)?)\*/g;

/** Inline runs: **bold**, *italic*, links; stray asterisks are dropped. */
export function inline(text: string): Inline[] {
	const parts: Inline[] = [];
	let last = 0;
	const plain = (t: string) => parts.push(...linkify(t.replace(/\*\*/g, '')));
	for (const match of text.matchAll(EMPHASIS_RE)) {
		const start = match.index ?? 0;
		if (start > last) plain(text.slice(last, start));
		const [, bold, italic] = match;
		for (const run of linkify(bold ?? italic)) {
			parts.push(bold ? { ...run, strong: true } : { ...run, em: true });
		}
		last = start + match[0].length;
	}
	if (last < text.length) plain(text.slice(last));
	return parts;
}

const HEADING_RE = /^#{1,4}\s+(.*)$/;
const ITEM_RE = /^(?:[-*•]|\d{1,2}[.)])\s+(.*)$/;

export function parseDescription(text: string): Block[] {
	const blocks: Block[] = [];
	let paragraph: string[] = [];
	let list: Inline[][] | null = null;

	const flush = () => {
		if (paragraph.length) blocks.push({ kind: 'paragraph', parts: inline(paragraph.join('\n')) });
		paragraph = [];
		if (list) blocks.push({ kind: 'list', items: list });
		list = null;
	};

	for (const raw of text.split(/\r?\n/)) {
		const line = raw.trim();
		if (!line) {
			flush();
		} else if (HEADING_RE.test(line)) {
			flush();
			const title = line.replace(HEADING_RE, '$1').replace(/\*+/g, '').trim();
			blocks.push({ kind: 'heading', text: title.replace(/:$/, '') });
		} else if (ITEM_RE.test(line)) {
			if (paragraph.length) flush();
			(list ??= []).push(inline(line.replace(ITEM_RE, '$1').trim()));
		} else {
			if (list) flush();
			paragraph.push(line);
		}
	}
	flush();
	return blocks;
}
