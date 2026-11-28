<!--
	@component
	App navigation: a narrow rail of icons on desktop (labels as tooltips and
	for screen readers), a drawer with icons and labels on mobile.
-->
<script lang="ts">
	import * as Sidebar from '#lib/components/ui/sidebar/index.js';
	import { useSidebar } from '#lib/components/ui/sidebar/context.svelte.js';
	import DarkModeToggle from './DarkModeToggle.svelte';
	import LanguagePicker from './LanguagePicker.svelte';
	import ReportBug from './ReportBug.svelte';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import * as m from '#lib/paraglide/messages.js';
	import { enhance } from '$app/forms';
	import BookOpen from '@lucide/svelte/icons/book-open';
	import House from '@lucide/svelte/icons/house';
	import LibraryBig from '@lucide/svelte/icons/library-big';
	import LogOut from '@lucide/svelte/icons/log-out';
	import Shield from '@lucide/svelte/icons/shield';
	import User from '@lucide/svelte/icons/user';

	// `/` only matches the exact home route; every other nav target also
	// matches its own sub-routes (e.g. /reader/[id] keeps the reader active).
	function isActive(href: string) {
		const path = page.url.pathname;
		return href === '/' ? path === '/' : path === href || path.startsWith(`${href}/`);
	}

	let items = $derived([
		{ href: resolve('/'), match: '/', label: m.nav_home(), icon: House },
		{
			href: resolve('/db-viewer'),
			match: '/db-viewer',
			label: m.nav_db_viewer(),
			icon: LibraryBig
		},
		{ href: resolve('/reader'), match: '/reader', label: m.nav_pdf_viewer(), icon: BookOpen },
		{ href: resolve('/account'), match: '/account', label: m.nav_account(), icon: User },
		...(page.data.isAdmin
			? [{ href: resolve('/admin'), match: '/admin', label: m.nav_admin(), icon: Shield }]
			: [])
	]);

	// Labels show as tooltips on the desktop rail; the mobile drawer
	// prints them next to the icons instead.
	const sidebar = useSidebar();
	let tip = $derived({ hidden: sidebar.isMobile });

	const button =
		'h-11 justify-center md:size-11 md:p-0 [&>svg]:size-5 max-md:justify-start max-md:gap-3';
</script>

<Sidebar.Root>
	<Sidebar.Header class="items-center p-2 pt-4">
		<a href={resolve('/')} title="ScoreGuide">
			<img src="/logo.png" alt="ScoreGuide" class="h-9 w-auto" />
		</a>
	</Sidebar.Header>
	<Sidebar.Content>
		<Sidebar.Group class="p-2">
			<Sidebar.GroupContent>
				<Sidebar.Menu class="items-center gap-1 max-md:items-stretch">
					{#each items as item (item.match)}
						<Sidebar.MenuItem>
							<Sidebar.MenuButton
								isActive={isActive(item.match)}
								class={button}
								tooltipContent={item.label}
								tooltipContentProps={tip}
							>
								{#snippet child({ props })}
									<a href={item.href} aria-label={item.label} {...props}>
										<item.icon />
										<span class="md:sr-only">{item.label}</span>
									</a>
								{/snippet}
							</Sidebar.MenuButton>
						</Sidebar.MenuItem>
					{/each}
				</Sidebar.Menu>
			</Sidebar.GroupContent>
		</Sidebar.Group>
	</Sidebar.Content>
	<Sidebar.Footer class="items-center gap-2 p-2 pb-4 max-md:items-stretch">
		<Sidebar.Menu class="items-center max-md:items-stretch">
			<Sidebar.MenuItem>
				<Sidebar.MenuButton
					class={button}
					tooltipContent={m.nav_logout()}
					tooltipContentProps={tip}
				>
					{#snippet child({ props })}
						<form method="POST" action="/logout" use:enhance>
							<!-- After the spread: the tooltip trigger sets type="button". -->
							<button {...props} type="submit" aria-label={m.nav_logout()}>
								<LogOut />
								<span class="md:sr-only">{m.nav_logout()}</span>
							</button>
						</form>
					{/snippet}
				</Sidebar.MenuButton>
			</Sidebar.MenuItem>
		</Sidebar.Menu>
		<div class="flex flex-col items-center gap-2 max-md:flex-row">
			<DarkModeToggle />
			<LanguagePicker compact />
			<ReportBug
				compact
				class="text-muted-foreground hover:text-foreground hover:bg-accent inline-flex size-9 items-center justify-center rounded-md"
			/>
		</div>
	</Sidebar.Footer>
</Sidebar.Root>
