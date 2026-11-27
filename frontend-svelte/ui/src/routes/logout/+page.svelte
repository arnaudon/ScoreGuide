<script lang="ts">
	import { resolve } from '$app/paths';
	import * as m from '#lib/paraglide/messages.js';
	import { Button } from '#lib/components/ui/button/index.js';
</script>

<div class="flex h-full items-center justify-center pt-10 pb-4">
	<div class="bg-card text-card-foreground shadow-card w-full max-w-md rounded-lg border p-6">
		<h1 class="text-fancy-title mb-4 text-center text-xl font-semibold">{m.logout_confirm()}</h1>
		<form method="POST" class="flex items-center justify-center gap-4">
			<Button type="submit">{m.nav_logout()}</Button>
			<a href={resolve('home')} class="text-primary text-sm hover:underline">
				{m.error_back_home()}
			</a>
		</form>
	</div>
</div>
