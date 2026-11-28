import { describe, expect, it } from 'vitest';
import {
	aiLeftLabel,
	aiRemaining,
	aiUsedPercent,
	canAfford,
	defaultEffort,
	effortPercent,
	formatBytes,
	planLabel,
	storageUsedPercent
} from './usage.js';
import type { User } from './types.js';

const usage = {
	plan: 'free',
	ai_used: 50,
	ai_allowance: 200,
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
		expect(aiLeftLabel({ usage })).toBe('AI: 75% left');
		expect(aiLeftLabel({ usage: null })).toBeUndefined();
		expect(aiLeftLabel(null)).toBeUndefined();
		expect(planLabel('pro')).toBe('Pro');
		expect(planLabel('free')).toBe('Free');
		expect(planLabel(undefined)).toBe('Free');
	});
});

describe('AI effort', () => {
	const usage = (left: number, estimates = { quick: 10, standard: 40, detailed: 100 }) => ({
		plan: 'free',
		ai_used: 1000 - left,
		ai_allowance: 1000,
		storage_used: 0,
		storage_limit: 1,
		ai_run_estimates: estimates
	});
	const user = (left: number, extra: Partial<User> = {}) =>
		({ usage: usage(left), role: 'user', detailed_descriptions: false, ...extra }) as User;

	it('says what share of the tokens a run takes', () => {
		expect(effortPercent(user(1000), 'standard')).toBe(4);
		expect(effortPercent(user(1000, { role: 'admin' }), 'standard')).toBeUndefined();
		expect(
			effortPercent({ ...user(1000), usage: { ...usage(1000), ai_run_estimates: {} } }, 'quick')
		).toBeUndefined();
	});

	it('offers quick on the free plan, standard on pro, detailed by preference', () => {
		expect(defaultEffort(user(1000))).toBe('quick');
		expect(defaultEffort(user(1000, { usage: { ...usage(1000), plan: 'pro' } }))).toBe('standard');
		expect(defaultEffort(user(1000, { detailed_descriptions: true }))).toBe('detailed');
		expect(defaultEffort(user(1000, { role: 'admin' }))).toBe('standard');
	});

	it('lowers the effort to what the tokens left cover', () => {
		const detailed = { detailed_descriptions: true };
		expect(defaultEffort(user(50, detailed))).toBe('standard');
		expect(defaultEffort(user(20, detailed))).toBe('quick');
		expect(defaultEffort(user(5, detailed))).toBeNull();
		expect(canAfford(user(5), 'quick')).toBe(false);
		expect(canAfford(user(0, { role: 'admin' }), 'detailed')).toBe(true);
		// No estimate: any token left will do.
		const unknown = { ...user(5), usage: { ...usage(5), ai_run_estimates: {} } };
		expect(canAfford(unknown, 'detailed')).toBe(true);
		expect(aiRemaining(null)).toBe(Infinity);
	});
});
