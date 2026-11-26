import { describe, expect, it } from 'vitest';
import { linkify, parseDescription } from './description';

describe('parseDescription', () => {
	it('keeps an unstructured description as one paragraph', () => {
		expect(parseDescription('One line.\nAnother line.')).toEqual([
			{ kind: 'paragraph', parts: [{ text: 'One line.\nAnother line.' }] }
		]);
	});

	it('reads headings, paragraphs and lists', () => {
		const text = '## History\nFirst para.\n\nSecond para.\n## How to play\n- one\n- two\nAfter.';
		expect(parseDescription(text)).toEqual([
			{ kind: 'heading', text: 'History' },
			{ kind: 'paragraph', parts: [{ text: 'First para.' }] },
			{ kind: 'paragraph', parts: [{ text: 'Second para.' }] },
			{ kind: 'heading', text: 'How to play' },
			{ kind: 'list', items: [[{ text: 'one' }], [{ text: 'two' }]] },
			{ kind: 'paragraph', parts: [{ text: 'After.' }] }
		]);
	});

	it('closes a paragraph when a list starts', () => {
		expect(parseDescription('Intro\n- item').map((b) => b.kind)).toEqual(['paragraph', 'list']);
	});

	it('returns nothing for blank text', () => {
		expect(parseDescription('  \n\n')).toEqual([]);
	});
});

describe('linkify', () => {
	it('turns http(s) URLs into links and leaves trailing punctuation', () => {
		expect(linkify('See https://example.org/a_(b). (https://example.org/c), done')).toEqual([
			{ text: 'See ' },
			{ text: 'https://example.org/a_(b)', href: 'https://example.org/a_(b)' },
			{ text: '. (' },
			{ text: 'https://example.org/c', href: 'https://example.org/c' },
			{ text: '), done' }
		]);
	});

	it('never links other schemes', () => {
		expect(linkify('javascript:alert(1) and ftp://x')).toEqual([
			{ text: 'javascript:alert(1) and ftp://x' }
		]);
	});
});
