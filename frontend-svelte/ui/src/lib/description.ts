import { httpUrl } from './url.js';

/**
 * A score's long description is plain text with a tiny, optional structure:
 * a line starting with `## ` is a section heading, lines starting with `- `
 * form a list, blank lines separate paragraphs, and http(s) URLs become
 * links. Anything else stays plain text, so old descriptions render as before.
 * Nothing is ever interpreted as HTML.
 */
export type Inline = { text: string; href?: string };
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

export function parseDescription(text: string): Block[] {
	const blocks: Block[] = [];
	let paragraph: string[] = [];
	let list: Inline[][] | null = null;

	const flush = () => {
		if (paragraph.length) blocks.push({ kind: 'paragraph', parts: linkify(paragraph.join('\n')) });
		paragraph = [];
		if (list) blocks.push({ kind: 'list', items: list });
		list = null;
	};

	for (const raw of text.split(/\r?\n/)) {
		const line = raw.trim();
		if (!line) {
			flush();
		} else if (line.startsWith('## ')) {
			flush();
			blocks.push({ kind: 'heading', text: line.slice(3).trim() });
		} else if (line.startsWith('- ')) {
			if (paragraph.length) flush();
			(list ??= []).push(linkify(line.slice(2).trim()));
		} else {
			if (list) flush();
			paragraph.push(line);
		}
	}
	flush();
	return blocks;
}
