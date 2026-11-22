<script lang="ts">
	import { page } from '$app/state';
	import { locales, localizeHref } from '#lib/paraglide/runtime.js';
	import * as m from '#lib/paraglide/messages.js';
	// Self-hosted fonts: no request to Google for every visitor (privacy, CSP).
	import '@fontsource/figtree/400.css';
	import '@fontsource/figtree/500.css';
	import '@fontsource/figtree/600.css';
	import '@fontsource/figtree/700.css';
	import '@fontsource/eb-garamond/600.css';
	import '@fontsource/eb-garamond/700.css';
	import '../app.css';
	import AppSidebar from '#lib/components/Sidebar.svelte';
	import Footer from '#lib/components/Footer.svelte';
	import * as Sidebar from '#lib/components/ui/sidebar/index.js';
	import { ModeWatcher } from 'mode-watcher';
	import { onMount } from 'svelte';
	import { enhance } from '$app/forms';

	let { children, data } = $props();
	let resendState = $state<'idle' | 'sent' | 'failed'>('idle');
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

<!-- Its pre-paint theme script lives in app.html, where it gets the CSP nonce. -->
<ModeWatcher disableHeadScriptInjection />

{#if data.loggedIn}
	<Sidebar.Provider style="--sidebar-width: 4rem;">
		<AppSidebar />
		<Sidebar.Inset class="bg-background text-foreground flex w-full flex-1 flex-col">
			<main class="w-full flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
				<!-- Desktop: the icon rail is always shown. Mobile: opens the drawer. -->
				<Sidebar.Trigger class="mb-4 md:hidden" />
				{#if data.isDemo}
					<div
						role="status"
						class="bg-muted text-muted-foreground mb-4 flex flex-col gap-2 rounded-md p-3 text-sm sm:flex-row sm:items-center sm:justify-between"
					>
						<span>{m.demo_banner()}</span>
						<!-- Both leave the demo first; "create" opens the sign-up form. -->
						<form method="POST" action="/logout" use:enhance class="flex shrink-0 gap-4">
							<button
								type="submit"
								name="next"
								value="signup"
								class="text-primary font-medium whitespace-nowrap hover:underline"
								>{m.demo_signup()}</button
							>
							<button
								type="submit"
								class="text-primary font-medium whitespace-nowrap hover:underline"
								>{m.demo_login()}</button
							>
						</form>
					</div>
				{/if}
				{#if data.emailUnverified && !data.isDemo}
					<div
						role="status"
						class="bg-muted text-muted-foreground mb-4 flex flex-col gap-2 rounded-md p-3 text-sm sm:flex-row sm:items-center sm:justify-between"
					>
						<span>{resendState === 'sent' ? m.verify_resent() : m.verify_banner()}</span>
						{#if resendState === 'failed'}
							<span class="text-destructive">{m.verify_resend_failed()}</span>
						{/if}
						{#if resendState !== 'sent'}
							<form
								method="POST"
								action="/verify-email?/resend"
								use:enhance={() =>
									async ({ result }) => {
										resendState = result.type === 'success' ? 'sent' : 'failed';
									}}
								class="shrink-0"
							>
								<button
									type="submit"
									class="text-primary font-medium whitespace-nowrap hover:underline"
									>{m.verify_resend()}</button
								>
							</form>
						{/if}
					</div>
				{/if}
				{@render children()}
			</main>
			<Footer />
		</Sidebar.Inset>
	</Sidebar.Provider>
{:else}
	<div class="bg-background text-foreground relative flex min-h-screen flex-col">
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
