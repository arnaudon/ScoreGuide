import { describe, expect, it } from 'vitest';
import { aiLeftLabel, aiUsedPercent, formatBytes, planLabel, storageUsedPercent } from './usage.js';

const usage = {
	plan: 'free',
	ai_used: 50,
	ai_allowance: 200,
	ai_resets_at: '2026-12-01T00:00:00',
	storage_used: 0,
	storage_limit: 0
};

describe('usage helpers', () => {
	it('computes percentages, capped and safe with zero limits', () => {
		expect(aiUsedPercent(usage)).toBe(25);
		expect(aiUsedPercent({ ai_used: 500, ai_allowance: 200 })).toBe(100);
		expect(aiUsedPercent({ ai_used: 0, ai_allowance: 0 })).toBe(0);
		expect(aiUsedPercent({ ai_used: 1, ai_allowance: 0 })).toBe(100);
		expect(storageUsedPercent({ storage_used: 0, storage_limit: 0 })).toBe(0);
		expect(storageUsedPercent({ storage_used: 5, storage_limit: 0 })).toBe(100);
		expect(storageUsedPercent({ storage_used: 1, storage_limit: 3 })).toBe(33);
	});

	it('formats sizes', () => {
		expect(formatBytes(4.2 * 1024 * 1024)).toBe('4.2 MB');
		expect(formatBytes(120 * 1024 * 1024)).toBe('120 MB');
		expect(formatBytes(1.5 * 1024 * 1024 * 1024)).toBe('1.5 GB');
	});

	it('labels what is left and the plan', () => {
		expect(aiLeftLabel({ usage })).toBe('AI: 75% left this month');
		expect(aiLeftLabel({ usage: null })).toBeUndefined();
		expect(aiLeftLabel(null)).toBeUndefined();
		expect(planLabel('pro')).toBe('Pro');
		expect(planLabel('free')).toBe('Free');
		expect(planLabel(undefined)).toBe('Free');
	});
});
