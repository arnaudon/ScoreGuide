import { page } from 'vitest/browser';
import { describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';
import ChatScores from './ChatScores.svelte';
import type { Score } from '#lib/types.js';

const score = (id: number) =>
	({ id, title: `Piece ${id}`, composer: 'Satie, Erik' }) as unknown as Score;

describe('ChatScores.svelte', () => {
	it('lists scores with a reader link and opens details on click', async () => {
		const onSelect = vi.fn();
		render(ChatScores, { scores: [score(1), score(2)], onSelect });
		await expect.element(page.getByText('Piece 1')).toBeInTheDocument();
		await expect
			.element(page.getByRole('link', { name: 'Open' }).first())
			.toHaveAttribute('href', '/reader/1');
		await page.getByText('Piece 2').click();
		expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }));
	});

	it('shows five at first, then the rest', async () => {
		render(ChatScores, { scores: [1, 2, 3, 4, 5, 6, 7].map(score) });
		expect(page.getByRole('link', { name: 'Open' }).all()).toHaveLength(5);
		await page.getByRole('button', { name: '2 more' }).click();
		await expect.poll(() => page.getByRole('link', { name: 'Open' }).all().length).toBe(7);
	});
});
