import { describe, expect, it } from 'vitest';
import { youtubeEmbedUrl, youtubeSearchUrl, youtubeVideoId } from './youtube.js';

describe('youtube helpers', () => {
	it('reads the video id from the usual link shapes', () => {
		const id = 'dQw4w9WgXcQ';
		for (const url of [
			`https://www.youtube.com/watch?v=${id}&t=30s`,
			`https://m.youtube.com/watch?v=${id}`,
			`https://youtu.be/${id}?si=abc`,
			`https://www.youtube.com/embed/${id}`,
			`https://www.youtube-nocookie.com/embed/${id}`,
			`https://youtube.com/shorts/${id}`,
			`https://www.youtube.com/live/${id}`
		]) {
			expect(youtubeVideoId(url)).toBe(id);
		}
	});

	it('rejects anything else', () => {
		for (const url of [
			'',
			null,
			'not a url',
			'https://www.youtube.com/results?search_query=bach',
			'https://www.youtube.com/watch?v=short',
			'https://evil.example/watch?v=dQw4w9WgXcQ',
			'https://www.youtube.com/channel/UCabcdefghijk'
		]) {
			expect(youtubeVideoId(url)).toBeNull();
		}
	});

	it('builds the privacy-enhanced embed and the search links', () => {
		expect(youtubeEmbedUrl('dQw4w9WgXcQ')).toBe(
			'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1&rel=0'
		);
		expect(youtubeSearchUrl('Satie, Erik', 'Gymnopédie No.1')).toBe(
			'https://www.youtube.com/results?search_query=Erik%20Satie%20Gymnop%C3%A9die%20No.1'
		);
	});
});
