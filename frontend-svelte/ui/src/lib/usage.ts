import type { UsageSummary, User } from '#lib/types.js';
import * as m from '#lib/paraglide/messages.js';

/** Share of the account's AI tokens already used, 0-100. */
export function aiUsedPercent(usage: Pick<UsageSummary, 'ai_used' | 'ai_allowance'>): number {
	if (usage.ai_allowance <= 0) return usage.ai_used > 0 ? 100 : 0;
	return Math.min(100, Math.round((100 * usage.ai_used) / usage.ai_allowance));
}

/** Share of storage used, 0-100. */
export function storageUsedPercent(
	usage: Pick<UsageSummary, 'storage_used' | 'storage_limit'>
): number {
	if (usage.storage_limit <= 0) return usage.storage_used > 0 ? 100 : 0;
	return Math.min(100, Math.round((100 * usage.storage_used) / usage.storage_limit));
}

/** "4.2 MB", "120 MB", "1.5 GB". */
export function formatBytes(bytes: number): string {
	const mb = bytes / (1024 * 1024);
	if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
	if (mb >= 10) return `${Math.round(mb)} MB`;
	return `${mb.toFixed(1)} MB`;
}

/** "AI: 80% left", or undefined without usage data (demo, logged out). */
export function aiLeftLabel(user: Pick<User, 'usage'> | null | undefined): string | undefined {
	if (!user?.usage) return undefined;
	return m.ai_left_label({ percent: 100 - aiUsedPercent(user.usage) });
}

export const planLabel = (plan: string | null | undefined) =>
	plan === 'pro' ? m.plan_pro() : m.plan_free();

/** How much the AI may search (and spend) to fill in a score. */
export const EFFORTS = ['quick', 'standard', 'detailed'] as const;
export type Effort = (typeof EFFORTS)[number];

type AiUser = Pick<User, 'usage' | 'role' | 'detailed_descriptions'> | null | undefined;

/** Weighted AI tokens the account has left (Infinity when not metered). */
export function aiRemaining(user: AiUser): number {
	if (!user?.usage || user.role === 'admin') return Infinity;
	return Math.max(0, user.usage.ai_allowance - user.usage.ai_used);
}

/** Share of all the account's AI tokens one run at ``effort`` takes, or undefined. */
export function effortPercent(user: AiUser, effort: Effort): number | undefined {
	const estimate = user?.usage?.ai_run_estimates?.[effort];
	const allowance = user?.usage?.ai_allowance ?? 0;
	if (!estimate || allowance <= 0 || user?.role === 'admin') return undefined;
	return (100 * estimate) / allowance;
}

/** Whether the tokens left cover a typical run at ``effort``. */
export function canAfford(user: AiUser, effort: Effort): boolean {
	const left = aiRemaining(user);
	const estimate = user?.usage?.ai_run_estimates?.[effort];
	return estimate ? left >= estimate : left > 0;
}

/**
 * The effort to offer first: detailed by preference, else standard on a paid
 * plan and quick on the free one, lowered to what the tokens left still
 * cover; null when not even a quick run fits.
 */
export function defaultEffort(user: AiUser): Effort | null {
	const preferred: Effort = user?.detailed_descriptions
		? 'detailed'
		: user?.role === 'admin' || user?.usage?.plan === 'pro'
			? 'standard'
			: 'quick';
	for (let i = EFFORTS.indexOf(preferred); i >= 0; i--) {
		if (canAfford(user, EFFORTS[i])) return EFFORTS[i];
	}
	return null;
}
