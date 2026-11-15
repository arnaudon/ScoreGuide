import { page, userEvent } from 'vitest/browser';
import { afterEach, describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import { createRawSnippet } from 'svelte';
import '../../app.css';
import ScoreViewer from './ScoreViewer.svelte';
import pdfUrl from '#lib/viewer/fixtures/five-pages.pdf?url';

function sizedTarget(width: number, height: number) {
	const target = document.createElement('div');
	target.style.cssText = `width:${width}px;height:${height}px`;
	document.body.append(target);
	return target;
}

const pageLabel = () => page.getByText(/^\d+(–\d+)? \/ 5$/);

describe('ScoreViewer.svelte', () => {
	afterEach(() => {
		localStorage.clear();
		document.body.replaceChildren();
	});

	it('loads, renders and turns pages with buttons and keys', async () => {
		render(ScoreViewer, { target: sizedTarget(500, 700), props: { url: pdfUrl } });
		await expect.element(page.getByText('1 / 5')).toBeInTheDocument();
		await expect.poll(() => document.querySelector('[data-page="1"] canvas')).toBeTruthy();

		await page.getByRole('button', { name: 'Next page' }).click();
		await expect.element(page.getByText('2 / 5')).toBeInTheDocument();

		(document.activeElement as HTMLElement | null)?.blur();
		await userEvent.keyboard('{PageDown}');
		await expect.element(page.getByText('3 / 5')).toBeInTheDocument();
		await userEvent.keyboard('{ArrowLeft}');
		await expect.element(page.getByText('2 / 5')).toBeInTheDocument();
		await userEvent.keyboard('{End}');
		await expect.element(page.getByText('5 / 5')).toBeInTheDocument();
		await expect.element(page.getByRole('button', { name: 'Next page' })).toBeDisabled();
	});

	it('shows two pages side by side on wide screens', async () => {
		render(ScoreViewer, { target: sizedTarget(1200, 700), props: { url: pdfUrl } });
		await expect.element(page.getByText('1–2 / 5')).toBeInTheDocument();
		await page.getByRole('button', { name: 'Next page' }).click();
		await expect.element(page.getByText('3–4 / 5')).toBeInTheDocument();
		await page.getByRole('button', { name: 'Next page' }).click();
		await expect.element(page.getByText('4–5 / 5')).toBeInTheDocument();
	});

	it('turns pages by tapping the page edges', async () => {
		render(ScoreViewer, { target: sizedTarget(500, 700), props: { url: pdfUrl } });
		await expect.element(page.getByText('1 / 5')).toBeInTheDocument();
		const stage = page.getByRole('presentation');
		await stage.click({ position: { x: 480, y: 300 } });
		await expect.element(page.getByText('2 / 5')).toBeInTheDocument();
		await stage.click({ position: { x: 10, y: 300 } });
		await expect.element(page.getByText('1 / 5')).toBeInTheDocument();
	});

	it('remembers the last page read', async () => {
		localStorage.setItem('reader.page.test', '4');
		render(ScoreViewer, {
			target: sizedTarget(500, 700),
			props: { url: pdfUrl, storageKey: 'reader.page.test' }
		});
		await expect.element(page.getByText('4 / 5')).toBeInTheDocument();
		await page.getByRole('button', { name: 'Previous page' }).click();
		await expect.poll(() => localStorage.getItem('reader.page.test')).toBe('3');
	});

	it('enters and leaves full screen with a visible exit button', async () => {
		render(ScoreViewer, { target: sizedTarget(500, 700), props: { url: pdfUrl } });
		await expect.element(pageLabel()).toBeInTheDocument();
		await page.getByRole('button', { name: 'Full screen' }).click();
		const exit = page.getByRole('button', { name: 'Exit full screen' }).first();
		await expect.element(exit).toBeInTheDocument();
		await exit.click();
		await expect.element(page.getByRole('button', { name: 'Full screen' })).toBeInTheDocument();
	});

	it('opens the contents drawer and jumps to a page', async () => {
		const contents = createRawSnippet((goTo: () => (p: number) => void) => ({
			render: () => '<button type="button">Movement II</button>',
			setup: (el) => {
				el.addEventListener('click', () => goTo()(4));
			}
		}));
		render(ScoreViewer, { target: sizedTarget(500, 700), props: { url: pdfUrl, contents } });
		await expect.element(page.getByText('1 / 5')).toBeInTheDocument();
		await page.getByRole('button', { name: 'Contents' }).click();
		await page.getByRole('button', { name: 'Movement II' }).click();
		await expect.element(page.getByText('4 / 5')).toBeInTheDocument();
		await expect.element(page.getByRole('button', { name: 'Movement II' })).not.toBeInTheDocument();
	});

	it('reports a PDF that fails to load', async () => {
		render(ScoreViewer, {
			target: sizedTarget(500, 700),
			props: { url: '/definitely-missing.pdf' }
		});
		await expect.element(page.getByRole('alert')).toHaveTextContent('Could not load this PDF.');
	});
});
