import { page } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import EditScoreDialog from './EditScoreDialog.svelte';
import type { Score } from '#lib/types.js';

const score = (id: number, title: string) =>
	({ id, title, composer: 'Satie, Erik', year: 1888, period: 'Romantic' }) as unknown as Score;

describe('EditScoreDialog.svelte', () => {
	it("keeps what the user types when the page's data refreshes", async () => {
		const screen = await render(EditScoreDialog, { open: true, score: score(1, 'Stored') });
		const title = page.getByLabelText('Title');
		await expect.element(title).toHaveValue('Stored');
		await title.fill('My new title');

		// A background refresh hands a new object for the same score.
		await screen.rerender({ open: true, score: score(1, 'Stored') });
		await expect.element(title).toHaveValue('My new title');

		// Another score: its own values.
		await screen.rerender({ open: true, score: score(2, 'Other') });
		await expect.element(title).toHaveValue('Other');
	});

	it('starts again from the stored values when reopened', async () => {
		const screen = await render(EditScoreDialog, { open: true, score: score(1, 'Stored') });
		const title = page.getByLabelText('Title');
		await title.fill('Abandoned edit');
		await screen.rerender({ open: false, score: score(1, 'Stored') });
		await screen.rerender({ open: true, score: score(1, 'Stored') });
		await expect.element(page.getByLabelText('Title')).toHaveValue('Stored');
	});
});
