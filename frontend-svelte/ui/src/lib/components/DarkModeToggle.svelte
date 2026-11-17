<!--
	@component
	Light / dark switch for the sidebar. Uses the sidebar's own colours
	(the sidebar is dark in both themes), so it stays visible in each.
-->
<script lang="ts">
	import Sun from '@lucide/svelte/icons/sun';
	import Moon from '@lucide/svelte/icons/moon';
	import { toggleMode } from 'mode-watcher';
	import * as m from '#lib/paraglide/messages.js';
</script>

<button
	type="button"
	onclick={toggleMode}
	class="border-sidebar-border text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-sidebar-ring relative inline-flex size-9 items-center justify-center rounded-md border transition-colors focus-visible:ring-2 focus-visible:outline-none"
	aria-label={m.toggle_theme()}
	title={m.toggle_theme()}
>
	<Sun class="size-[1.1rem] scale-100 rotate-0 transition-all dark:scale-0 dark:-rotate-90" />
	<Moon
		class="absolute size-[1.1rem] scale-0 rotate-90 transition-all dark:scale-100 dark:rotate-0"
	/>
</button>
