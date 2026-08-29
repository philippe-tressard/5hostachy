<!--
  Confirmation.svelte — « êtes-vous sûr ? », dans la charte du site.

  ## Le défaut qu'il retire (#605, 29/08/2026)

  Quarante gestes du site demandaient confirmation avec `confirm()` — la boîte
  NATIVE du navigateur. Elle a trois défauts, et aucun n'est cosmétique :

  1. **elle bloque le fil d'exécution** du navigateur entier, onglet compris ;
  2. **elle ignore la charte** : ni la couleur du danger, ni le libellé des
     boutons, ni la casse du site. Sur mobile elle s'affiche en haut de l'écran,
     loin du pouce, avec « OK / Annuler » en anglais selon la langue du système ;
  3. **elle ne dit pas la gravité.** Archiver et supprimer définitivement y ont
     exactement le même aspect — or l'un se défait et l'autre non.

  ⚠️ Ce composant s'emploie par `confirmer()` (`$lib/confirmation.ts`), jamais
  directement : c'est l'appel impératif qui rend la conversion des quarante
  sites tenable, et qui garde les appelants à une ligne.
-->
<script lang="ts">
	import Modale from './Modale.svelte';

	export let titre: string;
	export let message: string;
	export let libelleConfirmer = 'Confirmer';
	export let libelleAnnuler = 'Annuler';
	/** `true` = geste irréversible : le bouton passe en rouge et le dit. */
	export let danger = false;
	export let onReponse: (ok: boolean) => void;
</script>

<Modale {titre} on:fermer={() => onReponse(false)}>
	<p class="confirmation-message">{message}</p>
	<!--  « Annuler » AVANT la validation — la norme du 18/08/2026, vérifiée par
	      `lint:soumission` sur les formulaires. La même main, le même ordre. -->
	<div class="form-actions">
		<button type="button" class="btn btn-outline" on:click={() => onReponse(false)}>
			{libelleAnnuler}
		</button>
		<button
			type="button"
			class="btn {danger ? 'btn-danger' : 'btn-primary'}"
			on:click={() => onReponse(true)}
		>
			{libelleConfirmer}
		</button>
	</div>
</Modale>

<style>
	.confirmation-message {
		margin: 0 0 1.25rem;
		font-size: 0.95rem;
		line-height: 1.5;
		white-space: pre-line;
	}
</style>
