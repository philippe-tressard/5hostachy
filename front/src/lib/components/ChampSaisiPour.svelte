<!--
  **« Saisi pour »** — au nom de qui le conseil syndical ouvre ce ticket : en son
  nom, pour un résident inscrit, ou pour une personne extérieure.

  Extrait de `FormulaireTicket.svelte` le 19/08/2026, au fil de l'eau : le
  garde-fou de modularité (rang 1) a refusé que le formulaire — déjà au-dessus de
  500 lignes — grossisse pour recevoir l'aperçu avant diffusion (#498). La règle
  est « on découpe le fichier QUAND on y touche ».

  ⚠️ **Les trois valeurs partent TOUJOURS ensemble vers l'API, y compris à `null`.**
  C'est leur *présence* qui dit au serveur d'écrire (`model_fields_set`), et c'est
  ce qui permet de revenir à « En mon nom » : sans elles, un `None` serait
  indistinguable d'un champ non envoyé, et le choix resterait sans effet — en
  silence. La composition du lot reste chez l'appelant, qui seul sait s'il crée ou
  corrige ; ce composant ne porte que la saisie.

  ⚠️ Le style voyage avec le balisage : `.saisi-pour-*` et `.tab-btn` sont définis
  ici. Un style de page n'atteint pas un composant — c'est la panne des pastilles
  nues (v2.67.11), que `npm run lint:classes-nues` refuse depuis.
-->
<script lang="ts">
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import type { ModeSaisiPour } from '$lib/tickets';

	/** Lié par l'appelant : lui seul sait ce que ces valeurs deviennent. */
	export let mode: ModeSaisiPour = 'moi';
	export let userId: number | null = null;
	export let nom = '';
	export let email = '';
	/** Résidents proposables — chargés par l'appelant, qui connaît ses droits. */
	export let residents: { id: number; prenom: string; nom: string; email: string }[] = [];
</script>

<SectionFormulaire titre="Saisi pour" requis>
	<div class="field champ-large saisi-pour-section">
		<div class="saisi-pour-tabs">
			<button type="button" class="tab-btn" class:active={mode === 'moi'} on:click={() => (mode = 'moi')}>
				En mon nom
			</button>
			<button type="button" class="tab-btn" class:active={mode === 'resident'} on:click={() => (mode = 'resident')}>
				Résident inscrit
			</button>
			<button type="button" class="tab-btn" class:active={mode === 'exterieur'} on:click={() => (mode = 'exterieur')}>
				Personne extérieure
			</button>
		</div>
		{#if mode === 'resident'}
			<select bind:value={userId} style="margin-top:.5rem" aria-label="Résident concerné">
				<option value={null}>— Sélectionner un résident —</option>
				{#each residents as u (u.id)}
					<option value={u.id}>{u.prenom} {u.nom}{u.email ? ` (${u.email})` : ''}</option>
				{/each}
			</select>
		{:else if mode === 'exterieur'}
			<div class="saisi-pour-exterieur">
				<input type="text" bind:value={nom} placeholder="Nom complet *" aria-label="Nom complet de la personne" required />
				<input type="email" bind:value={email} placeholder="Email (optionnel)" aria-label="Email de la personne" />
			</div>
		{/if}
	</div>
</SectionFormulaire>

<style>
	.saisi-pour-section {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: .75rem;
		margin-bottom: .5rem;
	}
	.saisi-pour-tabs { display: flex; gap: .25rem; margin-top: .5rem; flex-wrap: wrap; }
	/*  Les deux champs de la personne extérieure. Le `style=` en ligne qu'ils
	    portaient dans le formulaire est devenu une classe en sortant : une règle
	    nommée se relit, se surcharge et se contrôle — un `style=` ne fait rien de
	    tout cela (`lint:styles`). */
	.saisi-pour-exterieur { margin-top: .5rem; display: flex; flex-direction: column; gap: .5rem; }
	.tab-btn {
		padding: .375rem .75rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: transparent;
		cursor: pointer;
		font-size: .85rem;
		color: var(--color-text-muted);
		transition: background .15s, color .15s, border-color .15s;
	}
	.tab-btn.active {
		background: var(--color-primary);
		color: #fff;
		border-color: var(--color-primary);
	}
</style>
