import { describe, it, expect } from 'vitest';
import { scoreFromImslp, instrumentLabel, periodLabel, INSTRUMENTS, PERIODS } from './imslp.js';

describe('scoreFromImslp', () => {
	it('links the work and adds the catalogue number to the title', () => {
		const body = scoreFromImslp(
			{
				id: 9,
				title: 'Ballade No.2',
				composer: 'Chopin, Frédéric',
				catalogue: 'Op.38',
				year: 1836,
				period: 'Romantic',
				genre: 'Ballades',
				key: 'F major',
				instrumentation: 'piano'
			},
			'file.pdf'
		);
		expect(body).toEqual({
			title: 'Ballade No.2, Op.38',
			composer: 'Chopin, Frédéric',
			pdf_path: 'file.pdf',
			imslp_id: 9,
			instrumentation: 'piano',
			style: '',
			key: 'F major',
			genre: 'Ballades',
			year: 1836,
			period: 'Romantic'
		});
	});

	it('leaves unknown values out and does not repeat the catalogue number', () => {
		const body = scoreFromImslp(
			{ id: 1, title: 'Nocturnes, Op.9', composer: 'C', catalogue: 'Op.9', year: 0, period: null },
			'f.pdf'
		);
		expect(body.title).toBe('Nocturnes, Op.9');
		expect(body).not.toHaveProperty('year');
		expect(body).not.toHaveProperty('period');
	});
});

describe('labels', () => {
	it('labels every filter value and passes unknown ones through', () => {
		for (const v of INSTRUMENTS) expect(instrumentLabel(v)).not.toBe('');
		for (const v of PERIODS) expect(periodLabel(v)).not.toBe('');
		expect(instrumentLabel('lute')).toBe('lute');
		expect(periodLabel('Other')).toBe('Other');
	});
});
