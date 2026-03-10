<script lang="ts">
	import type { ComponentProps } from 'svelte';
	import ArrowUpDown from 'lucide-svelte/icons/arrow-up-down';
	import { Button } from '$lib/components/ui/button/index.js';

	let {
		variant = 'ghost',
		title,
		...restProps
	}: ComponentProps<typeof Button> & { title: string } = $props();
</script>

<Button {variant} {...restProps} class="-ml-4 h-8 data-[state=open]:bg-accent">
	{title}
	<ArrowUpDown class="ms-2 h-4 w-4" />
</Button>
