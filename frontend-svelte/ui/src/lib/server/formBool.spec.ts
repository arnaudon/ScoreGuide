import { describe, expect, it } from 'vitest';
import { formBool } from './formBool';

const form = (...pairs: [string, string][]) => {
	const d = new FormData();
	for (const [k, v] of pairs) d.append(k, v);
	return d;
};

describe('formBool', () => {
	it('reads a checkbox with a hidden unchecked value', () => {
		expect(formBool(form(['x', 'false'], ['x', 'true']), 'x')).toBe(true);
		expect(formBool(form(['x', 'false']), 'x')).toBe(false);
		expect(formBool(form(), 'x')).toBeUndefined();
	});
});
