import type { UsageSummary, User } from '#lib/types.js';
import * as m from '#lib/paraglide/messages.js';

/** Share of this month's AI allowance already used, 0-100. */
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

/** "AI: 80% left this month", or undefined without usage data (demo, logged out). */
export function aiLeftLabel(user: Pick<User, 'usage'> | null | undefined): string | undefined {
	if (!user?.usage) return undefined;
	return m.ai_left_label({ percent: 100 - aiUsedPercent(user.usage) });
}

export const planLabel = (plan: string | null | undefined) =>
	plan === 'pro' ? m.plan_pro() : m.plan_free();
