<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import DarkModeToggle from './DarkModeToggle.svelte';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { setLocale } from '$lib/paraglide/runtime';
	import * as m from '$lib/paraglide/messages.js';
	import { enhance } from '$app/forms';

	function setLanguage(lang: 'en' | 'fr') {
		setLocale(lang);
	}

	// `/` only matches the exact home route; every other nav target also
	// matches its own sub-routes (e.g. /reader/[id] keeps "PDF Viewer" active).
	function isActive(href: string) {
		const path = page.url.pathname;
		return href === '/' ? path === '/' : path === href || path.startsWith(`${href}/`);
	}
</script>

<Sidebar.Root>
	<Sidebar.Header class="flex flex-col items-center gap-2 p-4 text-center">
		<img src="/logo.png" alt="ScoreGuide Logo" class="h-12 w-auto" />
		<h2 class="text-foreground text-xl font-bold">ScoreGuide</h2>
	</Sidebar.Header>
	<Sidebar.Content>
		<Sidebar.Group>
			<Sidebar.GroupContent>
				<Sidebar.Menu>
					<Sidebar.MenuItem>
						<Sidebar.MenuButton isActive={isActive('/')}>
							{#snippet child({ props })}
								<a href={resolve('/')} {...props}>{m.nav_home()}</a>
							{/snippet}
						</Sidebar.MenuButton>
					</Sidebar.MenuItem>
					<Sidebar.MenuItem>
						<Sidebar.MenuButton isActive={isActive('/db-viewer')}>
							{#snippet child({ props })}
								<a href={resolve('/db-viewer')} {...props}>{m.nav_db_viewer()}</a>
							{/snippet}
						</Sidebar.MenuButton>
					</Sidebar.MenuItem>
					<Sidebar.MenuItem>
						<Sidebar.MenuButton isActive={isActive('/reader')}>
							{#snippet child({ props })}
								<a href={resolve('/reader')} {...props}>{m.nav_pdf_viewer()}</a>
							{/snippet}
						</Sidebar.MenuButton>
					</Sidebar.MenuItem>
					<Sidebar.MenuItem>
						<Sidebar.MenuButton isActive={isActive('/account')}>
							{#snippet child({ props })}
								<a href={resolve('/account')} {...props}>{m.nav_account()}</a>
							{/snippet}
						</Sidebar.MenuButton>
					</Sidebar.MenuItem>
					{#if page.data.isAdmin}
						<Sidebar.MenuItem>
							<Sidebar.MenuButton isActive={isActive('/admin')}>
								{#snippet child({ props })}
									<a href={resolve('/admin')} {...props}>{m.nav_admin()}</a>
								{/snippet}
							</Sidebar.MenuButton>
						</Sidebar.MenuItem>
					{/if}
				</Sidebar.Menu>
			</Sidebar.GroupContent>
		</Sidebar.Group>
	</Sidebar.Content>
	<Sidebar.Footer class="gap-4 p-4">
		<Sidebar.Menu>
			<Sidebar.MenuItem>
				<Sidebar.MenuButton class="justify-center text-center">
					{#snippet child({ props })}
						<form method="POST" action="/logout" class="w-full" use:enhance>
							<button type="submit" {...props}>{m.nav_logout()}</button>
						</form>
					{/snippet}
				</Sidebar.MenuButton>
			</Sidebar.MenuItem>
		</Sidebar.Menu>
		<div class="flex items-center gap-2">
			<DarkModeToggle />
			<div
				class="flex rounded-md border text-xs font-semibold"
				role="group"
				aria-label={m.language_switch()}
			>
				<button
					type="button"
					onclick={() => setLanguage('en')}
					aria-label={m.language_switch_to_en()}
					class="hover:bg-muted p-2"
				>
					EN
				</button>
				<div class="bg-border w-[1px]"></div>
				<button
					type="button"
					onclick={() => setLanguage('fr')}
					aria-label={m.language_switch_to_fr()}
					class="hover:bg-muted p-2"
				>
					FR
				</button>
			</div>
		</div>
	</Sidebar.Footer>
</Sidebar.Root>
