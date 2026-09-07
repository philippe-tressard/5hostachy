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
		<!--  🔴 Quatre `class:` plutôt que `class="toast toast-{t.type}"` (#810).
		      Ce n'est pas un goût : devant une classe INTERPOLÉE, Svelte cesse de
		      déclarer les sélecteurs inutilisés **pour tout le fichier**, et
		      `lint:css-orphelin` devient aveugle sur l'écran entier. Mesuré :
		      une règle morte ajoutée ici n'était pas signalée avant, elle l'est
		      maintenant.

		      ⚠️ La conversion ne vaut QUE parce que les quatre classes sont
		      locales et connues. Là où l'interpolation vient d'une table de
		      correspondance (`badge {STATUT_BADGE[…]}`), l'éclater en `class:`
		      recopierait la table dans le balisage — c'est-à-dire exactement ce
		      que la table supprime. Ces fichiers-là restent déclarés non
		      mesurables, avec leur raison. -->
		<div
			class="toast"
			class:toast-success={t.type === 'success'}
			class:toast-error={t.type === 'error'}
			class:toast-warning={t.type === 'warning'}
			class:toast-info={t.type === 'info'}
			role="alert"
		>
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
