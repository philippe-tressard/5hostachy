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
		gap: 0.5rem;
		max-width: 340px;
	}

	.toast {
		padding: 0.75rem 1rem;
		border-radius: var(--radius);
		font-size: 0.875rem;
		box-shadow: var(--shadow);
		animation: slide-in 0.2s ease;
	}

	.toast-success {
		background: #e6f4ee;
		color: #2e7d52;
		border-left: 4px solid #2e7d52;
	}
	.toast-error {
		background: #fdedec;
		color: #c0392b;
		border-left: 4px solid #c0392b;
	}
	.toast-warning {
		background: #fdf3e0;
		color: #b07d1e;
		border-left: 4px solid #b07d1e;
	}
	.toast-info {
		background: var(--color-primary-light);
		color: var(--color-primary-dark);
		border-left: 4px solid var(--color-primary);
	}

	@keyframes slide-in {
		from {
			opacity: 0;
			transform: translateX(1rem);
		}
		to {
			opacity: 1;
			transform: translateX(0);
		}
	}
</style>
