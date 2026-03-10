<script lang="ts">
	import type { PageProps } from './$types';
	import * as Table from '$lib/components/ui/table/index.js';

	let { data }: PageProps = $props();
</script>

<div class="mb-4 flex items-center justify-between">
	<h1 class="text-2xl font-bold text-foreground">Users</h1>
</div>

<div class="rounded-md border bg-card text-card-foreground">
	<Table.Root>
		<Table.Header>
			<Table.Row>
				<Table.Head>ID</Table.Head>
				<Table.Head>Username</Table.Head>
				<Table.Head>Role</Table.Head>
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each data.users as user}
				<Table.Row>
					<Table.Cell>{user.id || '-'}</Table.Cell>
					<Table.Cell>{user.username}</Table.Cell>
					<Table.Cell class="capitalize">{user.role || (user.is_admin ? 'Admin' : 'User')}</Table.Cell>
				</Table.Row>
			{:else}
				<Table.Row>
					<Table.Cell colspan={3} class="text-center text-muted-foreground py-4">
						No users found.
					</Table.Cell>
				</Table.Row>
			{/each}
		</Table.Body>
	</Table.Root>
</div>
