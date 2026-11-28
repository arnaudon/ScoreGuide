<script lang="ts">
	import { resolve } from '$app/paths';
	import * as m from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.js';

	/** The account's AI tokens are used up: the app goes on without AI; how to get more. */
	let { class: className = '' }: { class?: string } = $props();
</script>

<p class={cn('text-muted-foreground text-xs', className)}>
	{m.ai_none_left()}
	<a href={resolve('/contact')} class="text-primary font-medium hover:underline">
		{m.ai_get_more()}
	</a>
</p>
