<!--
  Les gestes de rôle d'un compte (Admin › Comptes) : donner ou retirer le
  conseil syndical et l'administration. Le geste lui-même — la confirmation, puis
  l'appel — reste à l'onglet, qui le reçoit par `demander`.

  Extrait d'`OngletUtilisateurs` le 08/10/2026 (#1571) : l'onglet frôlait les
  500 lignes, et ses styles en ligne ne pouvaient passer en classes sans le faire
  déborder.
-->
<script lang="ts">
	import type { UtilisateurAdmin } from '$lib/api';
	import { aRole } from '$lib/stores/auth';

	export let u: UtilisateurAdmin;
	export let demander: (u: UtilisateurAdmin, role: string, action: 'ajouter' | 'retirer') => void;
</script>

{#if !u.actif}
	<span class="muted inactif">Compte inactif</span>
{:else}
	<div class="action-row">
		<!-- Ajouter CS si pas déjà — réservé aux propriétaires -->
		{#if !aRole(u, 'conseil_syndical')}
			{#if u.statut?.startsWith('copropriétaire')}
				<button
					class="btn btn-outline btn-sm ajouter-cs"
					on:click={() => demander(u, 'conseil_syndical', 'ajouter')}
				>
					+ CS
				</button>
			{/if}
		{:else}
			<button
				class="btn btn-outline btn-sm retirer"
				on:click={() => demander(u, 'conseil_syndical', 'retirer')}
			>
				– CS
			</button>
		{/if}
		<!-- Ajouter Admin si pas déjà — réservé aux propriétaires -->
		{#if !aRole(u, 'admin')}
			{#if u.statut?.startsWith('copropriétaire')}
				<button
					class="btn btn-outline btn-sm ajouter-admin"
					on:click={() => demander(u, 'admin', 'ajouter')}
				>
					+ Admin
				</button>
			{/if}
		{:else}
			<button
				class="btn btn-outline btn-sm retirer"
				on:click={() => demander(u, 'admin', 'retirer')}
			>
				– Admin
			</button>
		{/if}
	</div>
{/if}

<style>
	.inactif {
		font-size: var(--fs-sm);
	}
	/*  Qualifiés par `.btn-outline` : posées seules, ces teintes perdraient contre
	    `.btn-outline:hover` (0,2,0) — que l'attribut `style` d'origine, lui, battait. */
	.btn-outline.ajouter-cs {
		color: #1d4ed8;
		border-color: #1d4ed8;
	}
	.btn-outline.ajouter-admin {
		color: #c2410c;
		border-color: #c2410c;
	}
	.btn-outline.retirer {
		color: var(--color-danger);
		border-color: var(--color-danger);
	}
</style>
