import { expect, test } from '@playwright/test';

async function login(page: import('@playwright/test').Page) {
	await page.goto('/login');
	await page.locator('input[name="username"]').fill('test');
	await page.locator('input[name="password"]').fill('hunter2');
	await page.getByRole('button', { name: /^login$/i }).click();
	await expect(page).toHaveURL('/home');
}

/** Titles of the library table's rows, in order. */
async function titles(page: import('@playwright/test').Page) {
	return page.locator('tbody tr').filter({ hasText: 'Etude' }).allTextContents();
}

test.describe('library table', () => {
	test('pages, sorts and filters the scores', async ({ page }) => {
		await login(page);
		await page.goto('/db-viewer');

		// 12 scores, 10 per page.
		await expect(page.locator('tbody tr').filter({ hasText: 'Etude' })).toHaveCount(10);
		await expect(page.getByText('Page 1 of 2')).toBeVisible();
		await page.getByRole('button', { name: 'Next' }).click();
		await expect(page.locator('tbody tr').filter({ hasText: 'Etude' })).toHaveCount(2);
		await page.getByRole('button', { name: 'Previous' }).click();

		// Sorting by title: ascending, then descending.
		const sortTitle = page.getByRole('button', { name: 'Title' });
		await sortTitle.click();
		await expect.poll(async () => (await titles(page))[0]).toContain('Etude No. 01');
		await sortTitle.click();
		await expect.poll(async () => (await titles(page))[0]).toContain('Etude No. 12');

		// Text filter on the title column, from page 2: back to the first page.
		await page.getByRole('button', { name: 'Next' }).click();
		await expect(page.getByText('Page 2 of 2')).toBeVisible();
		await page.getByPlaceholder('Filter titles...').fill('No. 07');
		await expect(page.getByText('Page 1 of 1')).toBeVisible();
		await expect(page.locator('tbody tr').filter({ hasText: 'Etude' })).toHaveCount(1);
		await expect(page.getByText('Etude No. 07')).toBeVisible();
	});
});
