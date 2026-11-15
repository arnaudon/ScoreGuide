import { expect, test } from '@playwright/test';

async function login(page: import('@playwright/test').Page) {
	await page.goto('/login');
	await page.locator('input[name="username"]').fill('test');
	await page.locator('input[name="password"]').fill('hunter2');
	await page.getByRole('button', { name: /^login$/i }).click();
	await expect(page).toHaveURL('/home');
}

test.describe('reader page', () => {
	test('shows the "not found" message for an unknown score id', async ({ page }) => {
		await login(page);
		await page.goto('/reader/999');
		await expect(page.getByRole('heading', { name: /score not found/i })).toBeVisible();
	});

	test('wires the score viewer to the PDF proxy', async ({ page }) => {
		await login(page);
		const pdfRequest = page.waitForRequest((r) => r.url().includes('/api/pdf/moonlight.pdf'));
		await page.goto('/reader/1');
		await expect(page.getByRole('heading', { name: 'Moonlight Sonata' })).toBeVisible();
		await expect(page.getByRole('region', { name: 'Moonlight Sonata' })).toBeVisible();
		// Smoke check only — the stub backend doesn't serve real PDF bytes, so
		// the viewer requests the PDF through the proxy and reports the failure.
		await pdfRequest;
		await expect(page.getByRole('alert')).toContainText('Could not load this PDF.');
		await expect(page.getByRole('button', { name: 'Full screen' }).first()).toBeVisible();
	});
});
