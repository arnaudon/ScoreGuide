<script lang="ts">
	import { page } from '$app/state';
	import { locales, localizeHref } from '$lib/paraglide/runtime';
	import * as m from '$lib/paraglide/messages.js';
	import '../app.css';
	import AppSidebar from '$lib/components/Sidebar.svelte';
	import Footer from '$lib/components/Footer.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { ModeWatcher } from 'mode-watcher';
	import { onMount } from 'svelte';

	let { children, data } = $props();
	let showCookieBanner = $state(false);

	onMount(() => {
		if (!localStorage.getItem('cookie_consent')) {
			showCookieBanner = true;
		}
	});

	function acceptCookies() {
		localStorage.setItem('cookie_consent', 'true');
		showCookieBanner = false;
	}
</script>

<svelte:head>
	<title>ScoreGuide</title>
	<meta
		name="description"
		content="Your intelligent music score library. Upload, manage, and discover scores with AI-powered assistance."
	/>
	<meta property="og:title" content="ScoreGuide" />
	<meta
		property="og:description"
		content="Your intelligent music score library. Upload, manage, and discover scores with AI-powered assistance."
	/>
	<meta property="og:type" content="website" />
</svelte:head>

<ModeWatcher />

{#if data.loggedIn}
	<Sidebar.Provider style="--sidebar-width: 10rem;">
		<AppSidebar />
		<Sidebar.Inset class="bg-background text-foreground main-wrapper flex w-full flex-1 flex-col">
			<main class="w-full flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
				<Sidebar.Trigger class="mb-4" />
				{@render children()}
			</main>
			<Footer />
		</Sidebar.Inset>
	</Sidebar.Provider>
{:else}
	<div class="bg-background text-foreground main-wrapper relative flex min-h-screen flex-col">
		<main class="w-full flex-1">
			{@render children()}
		</main>
		<Footer showLanguageToggle={true} />
	</div>
{/if}

{#if showCookieBanner}
	<div
		class="bg-card border-border fixed right-0 bottom-0 left-0 z-50 flex flex-col items-center justify-between gap-4 border-t p-4 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)] sm:flex-row"
		role="region"
		aria-label={m.cookie_banner_label()}
	>
		<p class="text-card-foreground text-sm">{m.cookie_consent_msg()}</p>
		<button
			type="button"
			onclick={acceptCookies}
			class="bg-primary text-primary-foreground hover:bg-primary/90 rounded-md px-4 py-2 text-sm font-medium whitespace-nowrap"
		>
			{m.cookie_consent_accept()}
		</button>
	</div>
{/if}

<div style="display:none">
	{#each locales as locale (locale)}
		<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- localizeHref already returns the resolved path -->
		<a href={localizeHref(page.url.pathname, { locale })} hreflang={locale}>{locale}</a>
	{/each}
</div>
