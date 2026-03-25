<script module lang="ts">
	import { writable } from 'svelte/store';

	export interface ToastMessage {
		id: number;
		type: 'success' | 'error' | 'info' | 'warning';
		message: string;
	}

	export const toasts = writable<ToastMessage[]>([]);

	let counter = 0;

	export function toast(type: ToastMessage['type'], message: string, duration = 4000) {
		const id = ++counter;
		toasts.update((t) => [...t, { id, type, message }]);
		setTimeout(() => dismiss(id), duration);
	}

	function dismiss(id: number) {
		toasts.update((t) => t.filter((x) => x.id !== id));
	}
</script>

<div class="toast-container" aria-live="polite">
	{#each $toasts as t (t.id)}
		<div class="toast toast-{t.type}" role="alert">
			<span>{t.message}</span>
		</div>
	{/each}
</div>

<style>
	.toast-container {
		position: fixed;
		bottom: 5rem;
		right: 1rem;
		z-index: 9999;
		display: flex;
		flex-direction: column;
		gap: .5rem;
		max-width: 340px;
	}

	.toast {
		padding: .75rem 1rem;
		border-radius: var(--radius);
		font-size: .875rem;
		box-shadow: var(--shadow);
		animation: slide-in .2s ease;
	}

	.toast-success { background: #E6F4EE; color: #2E7D52; border-left: 4px solid #2E7D52; }
	.toast-error   { background: #FDEDEC; color: #C0392B; border-left: 4px solid #C0392B; }
	.toast-warning { background: #FDF3E0; color: #B07D1E; border-left: 4px solid #B07D1E; }
	.toast-info    { background: var(--color-primary-light); color: var(--color-primary-dark); border-left: 4px solid var(--color-primary); }

	@keyframes slide-in {
		from { opacity: 0; transform: translateX(1rem); }
		to   { opacity: 1; transform: translateX(0); }
	}
</style>
