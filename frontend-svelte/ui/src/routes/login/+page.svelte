<script lang="ts">
	import { page } from '$app/state';
	import type { PageProps } from './$types';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';
	import * as m from '#lib/paraglide/messages.js';
	import PlayIcon from '@lucide/svelte/icons/play';

	let { form }: PageProps = $props();
	// ?signup (from the demo banner) opens straight on the sign-up form.
	let isRegister = $state(page.url.searchParams.has('signup'));
	let submitting = $state(false);
</script>

<div class="flex h-full items-center justify-center pt-10 pb-4">
	<div class="bg-card text-card-foreground shadow-card w-full max-w-md rounded-lg border p-6">
		<div class="mb-4 text-center">
			<img src="/logo.png" alt="ScoreGuide Logo" class="mx-auto mb-2 h-16 w-auto" />
			<h1 class="text-fancy-title text-3xl font-bold">ScoreGuide</h1>
			<p class="text-muted-foreground mt-2">
				{m.login_description()}
			</p>
			<p class="text-muted-foreground mt-1 text-sm">{m.login_ai_optional()}</p>
		</div>

		{#if !isRegister}
			<form
				method="POST"
				action="?/demo"
				class="border-primary/30 bg-primary/5 mb-6 rounded-lg border p-4"
				use:enhance
			>
				<Button type="submit" size="lg" class="w-full text-base">
					<PlayIcon class="size-4" aria-hidden="true" />
					{m.try_demo()}
				</Button>
				<p class="text-muted-foreground mt-2 text-center text-sm">{m.try_demo_hint()}</p>
			</form>
			<div class="text-muted-foreground mb-4 flex items-center gap-3 text-xs uppercase">
				<span class="bg-border h-px flex-1"></span>
				{m.login_or()}
				<span class="bg-border h-px flex-1"></span>
			</div>
		{/if}

		<h2 class="text-fancy-title mb-4 text-center text-xl font-semibold">
			{isRegister ? m.sign_up() : m.login()}
		</h2>

		<form
			method="POST"
			action={isRegister ? '?/register' : '?/login'}
			class="space-y-4"
			use:enhance={() => {
				submitting = true;
				return async ({ update }) => {
					submitting = false;
					await update();
				};
			}}
		>
			<div class="space-y-2">
				<label for="username" class="text-sm leading-none font-medium">{m.username()}</label>
				<Input id="username" name="username" type="text" value={form?.username ?? ''} />
			</div>
			{#if isRegister}
				<div class="space-y-2">
					<label for="email" class="text-sm leading-none font-medium">{m.email()}</label>
					<Input id="email" name="email" type="email" value={form?.email ?? ''} required />
				</div>
			{/if}
			<div class="space-y-2">
				<div class="flex items-center justify-between">
					<label for="password" class="text-sm leading-none font-medium">{m.password()}</label>
					{#if !isRegister}
						<a href={resolve('forgot-password')} class="text-primary text-sm hover:underline">
							{m.forgot_password_link()}
						</a>
					{/if}
				</div>
				<Input
					id="password"
					name="password"
					type="password"
					minlength={isRegister ? 8 : undefined}
					maxlength={isRegister ? 128 : undefined}
					autocomplete={isRegister ? 'new-password' : 'current-password'}
				/>
			</div>

			{#if isRegister}
				<div class="space-y-2">
					<label for="instrument" class="text-sm leading-none font-medium">
						{m.preferred_instrument()}
					</label>
					<select
						id="instrument"
						name="instrument"
						class="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus:ring-ring flex h-10 w-full items-center justify-between rounded-md border px-3 py-2 text-sm focus:ring-2 focus:ring-offset-2 focus:outline-none"
					>
						<option value="" disabled selected={!form?.instrument}>{m.select_instrument()}</option>
						<option value="piano" selected={form?.instrument === 'piano'}>{m.inst_piano()}</option>
						<option value="violin" selected={form?.instrument === 'violin'}>
							{m.inst_violin()}
						</option>
						<option value="viola" selected={form?.instrument === 'viola'}>{m.inst_viola()}</option>
						<option value="cello" selected={form?.instrument === 'cello'}>{m.inst_cello()}</option>
						<option value="guitar" selected={form?.instrument === 'guitar'}>
							{m.inst_guitar()}
						</option>
						<option value="flute" selected={form?.instrument === 'flute'}>{m.inst_flute()}</option>
						<option value="clarinet" selected={form?.instrument === 'clarinet'}>
							{m.inst_clarinet()}
						</option>
						<option value="trumpet" selected={form?.instrument === 'trumpet'}>
							{m.inst_trumpet()}
						</option>
						<option value="other" selected={form?.instrument === 'other'}>{m.inst_other()}</option>
					</select>
				</div>
				<div class="space-y-2">
					<label for="music_profile" class="text-sm leading-none font-medium">
						{m.profile_music_label()}
					</label>
					<p class="text-muted-foreground text-xs">{m.profile_music_hint()}</p>
					<textarea
						id="music_profile"
						name="music_profile"
						rows="4"
						maxlength="1000"
						placeholder={m.profile_music_placeholder()}
						class="border-input bg-background placeholder:text-muted-foreground focus:ring-ring w-full rounded-md border px-3 py-2 text-sm focus:ring-2 focus:outline-none"
						>{form?.musicProfile ?? ''}</textarea
					>
				</div>
			{/if}

			{#if !isRegister}
				<div class="flex items-center space-x-2 pt-2">
					<Checkbox id="remember" name="remember" />
					<label
						for="remember"
						class="text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
					>
						{m.keep_logged_in()}
					</label>
				</div>
			{/if}

			{#if form?.error}
				<p role="alert" class="text-destructive text-sm font-medium">{form.error}</p>
			{/if}
			{#if form?.message}
				<p role="status" class="text-success text-sm font-medium">
					{form.message}
				</p>
			{/if}

			<Button type="submit" class="w-full" disabled={submitting}>
				{#if submitting}
					{isRegister ? m.signing_up() : m.logging_in()}
				{:else}
					{isRegister ? m.sign_up() : m.login()}
				{/if}
			</Button>
		</form>

		<div class="mt-4 text-center text-sm">
			{#if isRegister}
				<p class="text-muted-foreground">
					{m.already_have_account()}
					<button
						type="button"
						class="text-primary hover:underline"
						onclick={() => (isRegister = false)}
					>
						{m.login()}
					</button>
				</p>
			{:else}
				<p class="text-muted-foreground">
					{m.dont_have_account()}
					<button
						type="button"
						class="text-primary hover:underline"
						onclick={() => (isRegister = true)}
					>
						{m.sign_up()}
					</button>
				</p>
			{/if}
		</div>
	</div>
</div>
