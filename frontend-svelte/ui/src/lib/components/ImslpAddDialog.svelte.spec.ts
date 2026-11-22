import { page } from 'vitest/browser';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';
import ImslpAddDialog from './ImslpAddDialog.svelte';
import type { ImslpResult } from '#lib/types.js';

const WORK: ImslpResult = {
	id: 42,
	title: 'Gymnopédies',
	composer: 'Satie, Erik',
	catalogue: '',
	year: 1888,
	period: 'Romantic',
	genre: 'Pieces',
	key: '',
	instrumentation: 'piano',
	permlink: 'https://imslp.org/wiki/Gymnop%C3%A9dies_(Satie,_Erik)',
	in_library: false
};

const file = (n: number) => ({
	file: `PMLP${n}-Satie.pdf`,
	description: n === 1 ? 'Complete Score' : `No.${n}`,
	copyright: n === 1 ? 'Public Domain' : 'Creative Commons Attribution 4.0',
	url: `https://imslp.org/wiki/File:PMLP${n}-Satie.pdf`
});

function stubFiles(body: unknown, ok = true) {
	const fetch = vi.fn(async () => new Response(JSON.stringify(body), { status: ok ? 200 : 404 }));
	vi.stubGlobal('fetch', fetch);
	return fetch;
}

describe('ImslpAddDialog.svelte', () => {
	afterEach(() => vi.unstubAllGlobals());

	it("lists the work's files with links to IMSLP, six at a time", async () => {
		const fetch = stubFiles([1, 2, 3, 4, 5, 6, 7, 8].map(file));
		render(ImslpAddDialog, { work: WORK, open: true });
		await expect.element(page.getByText('Complete Score')).toBeInTheDocument();
		expect(fetch).toHaveBeenCalledWith('/api/imslp/42/files', expect.anything());
		const links = page.getByRole('link', { name: 'Open on IMSLP' });
		await expect.element(links.first()).toHaveAttribute('href', file(1).url);
		await expect.element(links.first()).toHaveAttribute('target', '_blank');
		expect(links.all()).toHaveLength(6);
		await expect.element(page.getByText('Public Domain')).toBeInTheDocument();
		await page.getByRole('button', { name: 'Show all 8 files' }).click();
		await expect.poll(() => links.all().length).toBe(8);
	});

	it('falls back to the work page when there is no file list', async () => {
		stubFiles({ detail: 'nope' }, false);
		render(ImslpAddDialog, { work: WORK, open: true });
		await expect.element(page.getByText(/No file list for this work/)).toBeInTheDocument();
		await expect
			.element(page.getByRole('link', { name: WORK.permlink }))
			.toHaveAttribute('href', WORK.permlink);
	});
});
