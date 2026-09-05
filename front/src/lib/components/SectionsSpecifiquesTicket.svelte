<!--
  SectionsSpecifiquesTicket.svelte — les sections 2 et 3 du cadre #430 pour un
  ticket : « Catégorie », « Saisi pour », les options de publication, et le
  workflow.

  ## Pourquoi ce fichier existe (05/09/2026)

  Extrait de `FormulaireTicket.svelte`, que le contrôle de modularité a refusé de
  laisser grossir (514 → 527 lignes). La bonne réponse n'était pas de raboter :
  ces quatre blocs forment ce qui est PROPRE au ticket, là où tout le reste du
  formulaire — sections 4 à 9 — vient déjà de `ChampsCommuns`. Le formulaire
  garde donc la soumission et l'assemblage ; ce fichier-ci, ce que le ticket a de
  particulier.

  ⚠️ **Il ne décide de rien.** La présence des sections reste gouvernée par
  `sectionPresente(TICKET, etat, …)`, comme partout ailleurs : une condition en
  dur rouvrirait la divergence silencieuse que le cadre supprime, et
  `lint:etats` la refuse.
-->
<script lang="ts">
	import ChampSaisiPour from '$lib/components/ChampSaisiPour.svelte';
	import SectionOptionsPublication from '$lib/components/SectionOptionsPublication.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import WorkflowPastilles from '$lib/components/WorkflowPastilles.svelte';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import { isCS } from '$lib/stores/auth';
	import { OPTIONS_TICKET, STATUT_TICKET_OPTIONS, type ModeSaisiPour } from '$lib/tickets';
	import type { Etat } from '$lib/entites/types';
	import { sectionPresente } from '$lib/entites/types';
	import { TICKET } from '$lib/entites/ticket';

	/** L'état de rendu — c'est lui, et non l'écran, qui décide des sections. */
	export let etat: Etat;
	/** Les catégories, déjà mises en forme pour `ChoixPastilles` par l'appelant. */
	export let OPTIONS_CATEGORIE: readonly { val: string; label: string; desc?: string }[] = [];
	/** Les résidents proposés par « Saisi pour ». */
	export let usersActifs: { id: number; prenom: string; nom: string; email: string }[] = [];
	/** Le formulaire est-il en correction ? Change le seul texte d'aide du workflow. */
	export let modeEdition = false;

	export let categorie = 'panne';
	export let statut = 'ouvert';
	/**  🔴 LES TROIS OPTIONS DE PUBLICATION, en un objet lié (05/09/2026).
	 *
	 *   Un objet plutôt que trois `bind:` séparés : c'est LUI que l'écran reprend
	 *   du ticket (`optionsDuTicket`) et renvoie tel quel (`optionsVersTicket`).
	 *   Trois liaisons distinctes obligeraient chaque hôte à défaire puis refaire
	 *   le même objet — et le premier qui en oublierait une la remettrait à son
	 *   défaut sans que personne le voie. */
	export let options = { epingle: false, urgente: false, brouillon: false };
	export let modeSaisiPour: ModeSaisiPour = 'moi';
	export let saisiPourUserId: number | null = null;
	export let saisiPourNom = '';
	export let saisiPourEmail = '';
</script>

<!--  2. Champs spécifiques — DEUX champs nommés, dans cet ordre : la
	      catégorie, puis « Saisi pour ». Ce dernier était rendu APRÈS les pièces
	      jointes, entre les documents et la diffusion : le seul champ du site à
	      être hors de sa section (signalé le 16/08/2026).
	      ⚠️ La SECTION est présente en édition — la catégorie s'y corrige comme
	      le titre —, mais « Saisi pour » n'y est pas : `TicketUpdate` ne sait pas
	      EFFACER les `saisi_pour_*`, et « En mon nom » serait un choix sans effet.
	      R4 ne déclare que des sections, pas des champs : ce motif `api` (#431)
	      vit dans la déclaration en commentaire, faute de pouvoir s'y écrire. -->
{#if sectionPresente(TICKET, etat, 'specifiques')}
	<SectionFormulaire titre="Catégorie" requis idTitre="ticket-categorie-titre">
		<!--  🔴 `ChoixPastilles` en mode radio depuis le 30/08/2026, signalé à
			      l'écran : *« dans tickets tu ne peux pas réduire ces pastilles à la
			      même taille que nouveau prestataire »*. C'étaient des cartes maison,
			      deux fois plus hautes que les pastilles du même site pour la même
			      question posée.
			      `ux-patterns` refusait la conversion — à raison : `Pastille` rendait
			      un `<button>`, et un `radiogroup` y aurait perdu ses flèches. La
			      réponse a été d'ENRICHIR l'objet plutôt que de le contourner : la
			      pastille sait désormais porter un `<input type="radio">`, masqué à
			      l'œil mais pas à l'accessibilité. -->
		<ChoixPastilles
			options={OPTIONS_CATEGORIE}
			bind:valeur={categorie}
			tous={false}
			radio="ticket-categorie"
			libelle="Catégorie"
			avecDetail
		/>
	</SectionFormulaire>
{/if}

{#if $isCS && sectionPresente(TICKET, etat, 'specifiques')}
	<ChampSaisiPour
		bind:mode={modeSaisiPour}
		bind:userId={saisiPourUserId}
		bind:nom={saisiPourNom}
		bind:email={saisiPourEmail}
		residents={usersActifs}
	/>

	<!--  LE MÊME COMPOSANT QUE L'ACTUALITÉ (05/09/2026) : *« faire ces
		      évolutions au niveau de l'objet pour ne pas dupliquer le code »*. Une
		      seule option ici — le ticket n'a ni colonne d'épinglage ni colonne
		      d'urgence (l'urgence est une CATÉGORIE), et déclarer une case sans
		      donnée derrière serait une promesse vide. Sa colonne `confidentiel`
		      se branche sur la clé d'affichage `brouillon` : même notion, deux
		      colonnes historiques (voir `$lib/options-publication`). -->
	<SectionOptionsPublication
		objet="ticket"
		options={OPTIONS_TICKET}
		bind:epingle={options.epingle}
		bind:urgente={options.urgente}
		bind:brouillon={options.brouillon}
	/>
{/if}

<!--  3. Workflow — où en est le ticket. À distinguer de la diffusion, qui
	      dit qui le voit et où (section 9). IDENTIQUE en création et en
	      édition depuis le cadre #430 : une correction corrige l'état comme
	      elle corrige un titre, et c'est le `PATCH` qui a changé de nature
	      côté serveur (voir le bloc de commentaires du script). -->
<SectionFormulaire titre="Workflow" requis idTitre="ticket-workflow-titre">
	<div class="field champ-large">
		<!--  🔴 PASTILLES, jamais un `<select>` nu (R3, #423). « Ouvert » est
			      active par défaut à la création — l'état de départ se voit, il ne
			      se devine pas. Un résident ne peut pas faire avancer le suivi :
			      la rangée est alors en lecture, et le serveur refait le contrôle
			      (liste blanche CS) — ce que l'interface interdit n'est qu'un
			      confort. -->
		<WorkflowPastilles
			options={STATUT_TICKET_OPTIONS}
			valeur={statut}
			lecture={!$isCS}
			idTitre="ticket-workflow-titre"
			on:choisir={(e) => (statut = e.detail)}
		/>
		{#if !$isCS}
			<p class="aide-champ">
				{modeEdition
					? 'Seul le conseil syndical fait avancer le suivi d’un ticket.'
					: 'Votre demande part en « Ouvert ». Le conseil syndical fait ensuite avancer son suivi.'}
			</p>
		{/if}
	</div>
</SectionFormulaire>

<style>
	/*  Le style PART AVEC le balisage (05/09/2026) : il est resté ici quand les
	    sections 2 et 3 ont été extraites, et `lint:classes-nues` l'a vu tout de
	    suite — c'est la régression des pastilles nues (v2.67.11), qui s'était
	    reproduite trois fois le 19/08. Svelte scope au FICHIER : une classe
	    employée ici doit être définie ici. */
	.aide-champ {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		line-height: 1.45;
		margin: 0.25rem 0 0;
	}
</style>
