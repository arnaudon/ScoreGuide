import { page } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import ScoreDetails from './ScoreDetails.svelte';
import type { Score } from '#lib/types.js';

const score = (youtube_url = '') =>
	({ id: 1, title: 'Gymnopédie No.1', composer: 'Satie, Erik', youtube_url }) as unknown as Score;

describe('ScoreDetails.svelte YouTube', () => {
	it('always offers a YouTube search for the piece', async () => {
		render(ScoreDetails, { score: score() });
		await expect
			.element(page.getByRole('link', { name: 'Search on YouTube' }))
			.toHaveAttribute(
				'href',
				'https://www.youtube.com/results?search_query=Erik%20Satie%20Gymnop%C3%A9die%20No.1'
			);
		await expect.element(page.getByRole('button', { name: /Play here/ })).not.toBeInTheDocument();
	});

	it('plays the saved video in the privacy-enhanced player only after a click', async () => {
		render(ScoreDetails, { score: score('https://youtu.be/dQw4w9WgXcQ') });
		expect(document.querySelector('iframe')).toBeNull();
		await page.getByRole('button', { name: /Play here/ }).click();
		await expect
			.poll(() => document.querySelector('iframe')?.getAttribute('src'))
			.toBe('https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1&rel=0');
		await expect.element(page.getByRole('link', { name: 'Watch on YouTube' })).toBeInTheDocument();
	});

	it('keeps a non-video link as a plain link, without a player', async () => {
		render(ScoreDetails, { score: score('https://www.youtube.com/results?search_query=satie') });
		await expect.element(page.getByRole('link', { name: 'Watch on YouTube' })).toBeInTheDocument();
		await expect.element(page.getByRole('button', { name: /Play here/ })).not.toBeInTheDocument();
	});

	it('never renders a non-http link', async () => {
		render(ScoreDetails, {
			score: {
				...score('javascript:alert(1)'),
				permlink: 'javascript:alert(2)'
			} as unknown as Score
		});
		await expect.element(page.getByRole('link', { name: 'Search on YouTube' })).toBeInTheDocument();
		await expect
			.element(page.getByRole('link', { name: 'Watch on YouTube' }))
			.not.toBeInTheDocument();
		await expect.element(page.getByRole('link', { name: 'IMSLP' })).not.toBeInTheDocument();
		expect(document.querySelector('a[href^="javascript:"]')).toBeNull();
	});
});

describe('ScoreDetails.svelte description and plays', () => {
	it('renders sections, lists and source links', async () => {
		render(ScoreDetails, {
			score: {
				...score(),
				long_description:
					'## History\nWritten in 1888.\n\n## Sources\n- Wikipedia: https://en.wikipedia.org/wiki/Gymnop%C3%A9dies'
			} as unknown as Score
		});
		await expect.element(page.getByRole('heading', { name: 'History' })).toBeInTheDocument();
		await expect.element(page.getByRole('heading', { name: 'Sources' })).toBeInTheDocument();
		await expect
			.element(page.getByRole('link', { name: 'en.wikipedia.org' }))
			.toHaveAttribute('href', 'https://en.wikipedia.org/wiki/Gymnop%C3%A9dies');
	});

	it('shows how often a library score was played', async () => {
		render(ScoreDetails, { score: { ...score(), number_of_plays: 3 } as unknown as Score });
		await expect.element(page.getByText('Played 3×')).toBeInTheDocument();
	});

	it('says when a score was never opened, and nothing for IMSLP results', async () => {
		render(ScoreDetails, { score: { ...score(), number_of_plays: 0 } as unknown as Score });
		await expect.element(page.getByText('Not opened yet')).toBeInTheDocument();
	});
});
