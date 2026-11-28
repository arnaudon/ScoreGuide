import { expect, test, type Page } from '@playwright/test';

async function login(page: Page) {
	await page.goto('/login');
	await page.locator('input[name="username"]').fill('test');
	await page.locator('input[name="password"]').fill('hunter2');
	await page.getByRole('button', { name: /^login$/i }).click();
	await expect(page).toHaveURL('/home');
}

const cards = (page: Page) => page.locator('article').filter({ hasText: 'Etude' });

/** Sort by title (retried: a choice made before hydration is lost). */
async function sortByTitle(page: Page) {
	await expect(async () => {
		await page.getByLabel('Sort by').selectOption('composer');
		await page.getByLabel('Sort by').selectOption('title');
		await expect(cards(page).first()).toContainText('Etude No. 01', { timeout: 1000 });
	}).toPass();
}

test.describe('library', () => {
	test.use({ viewport: { width: 1280, height: 900 } });

	test('grows on scroll, searches, filters and sorts', async ({ page }) => {
		await login(page);
		await page.goto('/db-viewer');

		// 40 scores, 30 at first, the rest once the end of the list shows.
		await expect(cards(page)).toHaveCount(30);
		await expect(page.getByText('30 of 40 scores')).toBeVisible();
		await page.getByRole('button', { name: 'Show more' }).scrollIntoViewIfNeeded();
		await expect(cards(page)).toHaveCount(40);
		await expect(page.getByText('40 of 40 scores')).toBeVisible();

		// One search box over title, composer, instrumentation…
		const search = page.getByRole('searchbox', { name: /search title/i });
		await search.fill('no. 07');
		await expect(cards(page)).toHaveCount(1);
		await search.fill('chopin etude');
		await expect(cards(page)).toHaveCount(20);
		await page.getByRole('button', { name: 'Clear filters' }).first().click();
		await expect(search).toHaveValue('');

		// The composer list on the left; grouped under the composer's name.
		await page.getByRole('complementary').getByRole('button', { name: /^Liszt/ }).click();
		await expect(page.getByText('20 of 20 scores')).toBeVisible();
		await expect(page.getByRole('heading', { name: /^Liszt/ })).toBeVisible();
		await page.getByRole('button', { name: 'Remove filter Liszt' }).click();
		await expect(page.getByText('30 of 40 scores')).toBeVisible();

		// Sort by title, then reversed.
		await sortByTitle(page);
		await page.getByRole('button', { name: 'Reverse order' }).click();
		await expect(cards(page).first()).toContainText('Etude No. 40');
	});

	test('stars a score and remembers the list view', async ({ page }) => {
		await login(page);
		await page.goto('/db-viewer');
		await sortByTitle(page);

		await cards(page).first().getByRole('button', { name: 'Add to favourites' }).click();
		await page.getByRole('button', { name: 'Favourites', exact: true }).click();
		await expect(cards(page)).toHaveCount(1);
		await expect(cards(page).first()).toContainText('Etude No. 01');
		await page.getByRole('button', { name: 'Favourites', exact: true }).click();

		await page.getByRole('button', { name: 'List', exact: true }).click();
		await expect(page.locator('tbody tr').filter({ hasText: 'Etude' })).toHaveCount(30);
		await page.reload();
		await expect(page.locator('tbody tr').filter({ hasText: 'Etude' })).toHaveCount(30);
		await page.getByRole('button', { name: 'Cards', exact: true }).click();
		await expect(cards(page)).toHaveCount(30);
	});
});
