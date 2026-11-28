<!--
	@component
	"Report a problem": opens Sentry's feedback form (the report comes with the
	error trail of this visit, so a bug can be found again); without Sentry
	(dev, tests) or if the form can't open, goes to the contact page instead.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { getFeedback } from '@sentry/sveltekit';
	import Bug from '@lucide/svelte/icons/bug';
	import * as m from '#lib/paraglide/messages.js';

	let { compact = false, class: className = '' }: { compact?: boolean; class?: string } = $props();

	async function open(event: MouseEvent) {
		const feedback = getFeedback();
		if (!feedback) return; // the link's href (contact page) applies
		event.preventDefault();
		try {
			const form = await feedback.createForm({
				formTitle: m.report_title(),
				messageLabel: m.report_message(),
				messagePlaceholder: m.report_placeholder(),
				isRequiredLabel: m.report_required(),
				submitButtonLabel: m.report_send(),
				cancelButtonLabel: m.report_cancel(),
				successMessageText: m.report_thanks()
			});
			form.appendToDom();
			form.open();
		} catch {
			await goto(resolve('/contact'));
		}
	}
</script>

<a
	href={resolve('/contact')}
	onclick={open}
	class={className || 'hover:underline'}
	aria-label={compact ? m.report_problem() : undefined}
	title={compact ? m.report_problem() : undefined}
>
	{#if compact}<Bug class="size-4" />{:else}{m.report_problem()}{/if}
</a>
