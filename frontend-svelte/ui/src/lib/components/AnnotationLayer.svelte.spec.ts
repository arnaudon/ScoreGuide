import { page, userEvent } from 'vitest/browser';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';
import '../../app.css';
import AnnotationLayer from './AnnotationLayer.svelte';
import AnnotationTools from './AnnotationTools.svelte';
import type { Annotation } from '#lib/annotations.js';

const W = 400;
const H = 600;

function mount(props: Partial<Parameters<typeof render<typeof AnnotationLayer>>[1] & object> = {}) {
	const target = document.createElement('div');
	target.style.cssText = `position:relative;width:${W}px;height:${H}px`;
	document.body.append(target);
	const handlers = { onCreate: vi.fn(), onUpdate: vi.fn(), onDelete: vi.fn() };
	render(AnnotationLayer, {
		target,
		props: { width: W, height: H, items: [], tool: 'pen', color: '#e11d48', ...handlers, ...props }
	});
	const layer = target.firstElementChild as HTMLElement;
	return { target, layer, ...handlers };
}

function pointer(el: Element, type: string, x: number, y: number) {
	const rect = el.getBoundingClientRect();
	el.dispatchEvent(
		new PointerEvent(type, {
			bubbles: true,
			cancelable: true,
			isPrimary: true,
			pointerId: 1,
			pointerType: 'mouse',
			clientX: rect.left + x,
			clientY: rect.top + y
		})
	);
}

const ink = (id: number): Annotation => ({
	id,
	score_id: 1,
	page: 1,
	kind: 'ink',
	data: {
		kind: 'ink',
		points: [
			[0.1, 0.5],
			[0.9, 0.5]
		],
		color: '#2563eb',
		width: 0.004
	},
	created_at: '',
	updated_at: ''
});

const note = (id: number, text: string): Annotation => ({
	id,
	score_id: 1,
	page: 1,
	kind: 'text',
	data: { kind: 'text', x: 0.5, y: 0.2, text, color: '#2563eb' },
	created_at: '',
	updated_at: ''
});

describe('AnnotationLayer.svelte', () => {
	afterEach(() => document.body.replaceChildren());

	it('draws a pencil stroke in page coordinates', async () => {
		const { layer, onCreate } = mount();
		pointer(layer, 'pointerdown', 40, 60);
		pointer(layer, 'pointermove', 200, 300);
		pointer(layer, 'pointermove', 360, 540);
		pointer(layer, 'pointerup', 360, 540);
		expect(onCreate).toHaveBeenCalledOnce();
		const data = onCreate.mock.calls[0][0];
		expect(data.kind).toBe('ink');
		expect(data.color).toBe('#e11d48');
		expect(data.points[0][0]).toBeCloseTo(0.1, 2);
		expect(data.points[0][1]).toBeCloseTo(0.1, 2);
		expect(data.points.at(-1)[0]).toBeCloseTo(0.9, 2);
	});

	it('renders marks and notes without blocking taps when no tool is active', async () => {
		const { layer } = mount({ tool: null, items: [ink(1), note(2, 'breathe here')] });
		await expect.element(page.getByText('breathe here')).toBeInTheDocument();
		expect(layer.querySelectorAll('polyline')).toHaveLength(1);
		expect(getComputedStyle(layer).pointerEvents).toBe('none');
	});

	it('adds a text note where tapped', async () => {
		const { layer, onCreate } = mount({ tool: 'text' });
		pointer(layer, 'pointerdown', 200, 300);
		const editor = page.getByRole('textbox');
		await expect.element(editor).toBeInTheDocument();
		await userEvent.type(editor, 'slow down{Enter}');
		expect(onCreate).toHaveBeenCalledWith({
			kind: 'text',
			x: 0.5,
			y: 0.5,
			text: 'slow down',
			color: '#e11d48'
		});
		await expect.element(editor).not.toBeInTheDocument();
	});

	it('edits an existing note and deletes it when emptied', async () => {
		const { layer, onUpdate, onDelete } = mount({ tool: 'text', items: [note(7, 'p')] });
		const label = page.getByText('p', { exact: true });
		const rect = (await label.element()).getBoundingClientRect();
		const base = layer.getBoundingClientRect();
		pointer(layer, 'pointerdown', rect.left - base.left + 3, rect.top - base.top + 3);
		const editor = page.getByRole('textbox');
		await expect.element(editor).toHaveValue('p');
		await userEvent.type(editor, 'p{Enter}');
		expect(onUpdate).toHaveBeenCalledWith(7, expect.objectContaining({ text: 'pp' }));

		pointer(layer, 'pointerdown', rect.left - base.left + 3, rect.top - base.top + 3);
		await userEvent.clear(page.getByRole('textbox'));
		await userEvent.keyboard('{Enter}');
		expect(onDelete).toHaveBeenCalledWith(7);
	});

	it('erases a stroke under the eraser', async () => {
		const { layer, onDelete } = mount({ tool: 'eraser', items: [ink(3)] });
		pointer(layer, 'pointerdown', 200, 300); // on the horizontal line at y=0.5
		pointer(layer, 'pointerup', 200, 300);
		expect(onDelete).toHaveBeenCalledWith(3);
		pointer(layer, 'pointerdown', 200, 50); // empty area
		expect(onDelete).toHaveBeenCalledTimes(1);
	});
});

describe('AnnotationTools.svelte', () => {
	afterEach(() => document.body.replaceChildren());

	it('enters annotate mode, undoes with Ctrl+Z and leaves with Done', async () => {
		const onUndo = vi.fn();
		render(AnnotationTools, { props: { canUndo: true, onUndo } });
		await page.getByRole('button', { name: 'Annotate' }).click();
		await expect
			.element(page.getByRole('button', { name: 'Pencil' }))
			.toHaveAttribute('aria-pressed', 'true');
		await page.getByRole('button', { name: 'Eraser' }).click();
		await expect
			.element(page.getByRole('button', { name: 'Eraser' }))
			.toHaveAttribute('aria-pressed', 'true');
		await page.getByRole('button', { name: 'Blue' }).click(); // picking a colour returns to the pencil
		await expect
			.element(page.getByRole('button', { name: 'Pencil' }))
			.toHaveAttribute('aria-pressed', 'true');
		(document.activeElement as HTMLElement | null)?.blur();
		await userEvent.keyboard('{Control>}z{/Control}');
		expect(onUndo).toHaveBeenCalledOnce();
		await page.getByRole('button', { name: 'Undo' }).click();
		expect(onUndo).toHaveBeenCalledTimes(2);
		await page.getByRole('button', { name: 'Done' }).click();
		await expect.element(page.getByRole('button', { name: 'Annotate' })).toBeInTheDocument();
	});
});
