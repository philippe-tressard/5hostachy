<!--
  La section **Quand** du cadre — quand ça se passe, et pour quand c'est attendu.

  Née du chantier v2.0.0 (#1092) : le Calendrier cesse d'être un objet pour
  devenir une vue — « tout ce qui porte une date ». Pour cela, une actualité et
  une affaire doivent pouvoir dire *quand*, ce que seul `Evenement` savait faire.

  ## 🔴 Deux dates, deux notions — les confondre casse les deux

  | Champ | Sens | Alimente |
  |---|---|---|
  | `debut` / `fin` | *ça se passe le X* | le **calendrier** |
  | `echeance` | *ça doit être fait avant le X* | le **suivi** (relance, retard) |

  Une échéance affichée dans l'agenda de la résidence y mettrait « devis attendu
  sous 15 jours » entre l'assemblée générale et la coupure d'eau ; et une date
  d'événement prise pour une échéance n'alerterait jamais sur un retard.

  `avecEcheance` est donc **faux par défaut** : une actualité ne se suit pas, et
  lui ouvrir le champ afficherait un contrôle que le serveur ne consomme pas —
  ce que le cadre #430 interdit en toutes lettres.

  ## Ce que la date dispense d'écrire

  Renseigner `debut` rend la **description facultative** : « Coupure d'eau —
  jeudi 9h-12h » se suffit. La règle est au serveur (`app/utils/quand.py`), et
  l'écran ne fait que la refléter — c'est ce qui a manqué jusqu'ici, l'astérisque
  de « Description * » ne vivant QUE dans le formulaire.
-->
<script lang="ts">
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';

	/** Préfixe des identifiants — l'écran en ouvre parfois plusieurs à la fois. */
	export let idPrefixe: string;

	/**  L'échéance n'existe que sur un objet qu'on SUIT. Ouvrir ce champ sur une
	 *   actualité poserait une valeur que rien ne relit. */
	export let avecEcheance = false;

	export let premiere = false;

	/** `datetime-local` rend `''` quand le champ est vide, jamais `null`. */
	export let debut = '';
	export let fin = '';
	export let echeance = '';
</script>

<SectionFormulaire titre="Quand" {premiere} idTitre="{idPrefixe}-quand">
	<div class="quand-grille">
		<div class="field">
			<label for="{idPrefixe}-debut">Début</label>
			<input id="{idPrefixe}-debut" type="datetime-local" bind:value={debut} />
		</div>
		<div class="field">
			<label for="{idPrefixe}-fin">Fin</label>
			<input id="{idPrefixe}-fin" type="datetime-local" bind:value={fin} />
		</div>
		{#if avecEcheance}
			<div class="field">
				<label for="{idPrefixe}-echeance">Échéance</label>
				<input id="{idPrefixe}-echeance" type="date" bind:value={echeance} />
			</div>
		{/if}
	</div>
	<p class="quand-aide">
		{#if avecEcheance}
			Une <strong>date de début</strong> fait paraître l'affaire au calendrier. Une
			<strong>échéance</strong> déclenche une relance si rien n'a bougé.
		{:else}
			Une <strong>date de début</strong> fait paraître l'actualité au calendrier — et dispense d'écrire
			une description.
		{/if}
	</p>
</SectionFormulaire>

<style>
	/*  Une colonne sous 520 px : trois champs de date côte à côte sur un
	    téléphone débordent, et `datetime-local` a une largeur minimale que le
	    navigateur impose (socle 11 §10). */
	.quand-grille {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0.75rem;
	}
	.quand-aide {
		margin: 0.55rem 0 0;
		font-size: 0.8rem;
		color: var(--color-text-muted);
		line-height: 1.45;
	}
</style>
