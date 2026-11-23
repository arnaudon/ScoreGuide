import { page } from 'vitest/browser';
import { describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';
import ScoreContents from './ScoreContents.svelte';
import type { ScoreSection, SectionsResponse } from '#lib/types.js';

vi.mock('$app/state', () => ({ page: { data: {}, params: { id: '7' } } }));

function section(id: number, title: string, page: number, level = 0): ScoreSection {
	return {
		id,
		score_id: 7,
		position: id,
		title,
		page,
		source: 'ocr',
		incipit_path: '',
		version: 3,
		level
	};
}

function toc(sections: ScoreSection[]): SectionsResponse {
	return { status: 'ready', sections, confidence: 'medium', version: 3, latest_version: 3 };
}

describe('ScoreContents.svelte', () => {
	it('lists movements under their piece', async () => {
		render(ScoreContents, {
			toc: toc([
				section(1, 'Sonata 1', 7),
				section(2, 'Allegro', 7, 1),
				section(3, 'Adagio', 14, 1),
				section(4, 'Sonata 2', 23),
				section(5, 'Presto', 23, 1)
			]),
			canNavigate: true,
			onSelect: () => {}
		});
		const first = page.getByRole('list', { name: 'Movements of Sonata 1' });
		await expect.element(first).toBeInTheDocument();
		await expect.element(first.getByRole('button', { name: /Allegro/ })).toBeInTheDocument();
		await expect.element(first.getByRole('button', { name: /Adagio/ })).toBeInTheDocument();
		await expect.element(first.getByRole('button', { name: /Presto/ })).not.toBeInTheDocument();
		const second = page.getByRole('list', { name: 'Movements of Sonata 2' });
		await expect.element(second.getByRole('button', { name: /Presto/ })).toBeInTheDocument();
	});

	it('keeps a flat list flat and jumps to the page of an entry', async () => {
		const onSelect = vi.fn();
		render(ScoreContents, {
			toc: toc([section(1, 'Prelude 1', 1), section(2, 'Fugue 1', 3)]),
			canNavigate: true,
			onSelect
		});
		await expect.element(page.getByRole('list', { name: /Movements of/ })).not.toBeInTheDocument();
		await page.getByRole('button', { name: /Fugue 1/ }).click();
		expect(onSelect).toHaveBeenCalledWith(3);
	});
});
