<!--
  La section **Quand** du cadre — quand ça se passe, et pour quand c'est attendu.

  Née du chantier v2.0.0 (#1092) : le Calendrier cesse d'être un objet pour
  devenir une vue — « tout ce qui porte une date ». Pour cela, une actualité et
  une affaire doivent pouvoir dire *quand*, ce que seul `Evenement` savait faire.

  ## 🔴 L'ÉCHÉANCE a été retirée le 21/09/2026, signalée à l'écran

  > « L'échéance pour la relance c'est non, il y a un mécanisme automatique de
  >   relance d'une affaire non résolue chaque mois »

  Le champ promettait : *« Une échéance déclenche une relance si rien n'a
  bougé »*. **C'était faux deux fois.**

  1. **Personne ne la lisait.** `Ticket.echeance` était écrit par
     `routers/tickets/crud.py` et relu par aucun code — ni relance, ni alerte,
     ni affichage. Un contrôle que le serveur ne consomme pas est exactement ce
     que le cadre #430 interdit, et il a été posé ici même (#1092).
  2. **Le suivi existait déjà, et sur un autre critère.** Ce qui repère une
     affaire qui traîne est son **inactivité** — `relance_syndic_delai_jours`,
     lu par `flux/sante.py` : affaires adressées au syndic, non closes, non
     relançables exclues, et *sans modification depuis le délai*. Une date que
     l'auteur aurait saisie n'y entrait pour rien.

  ⚠️ Nuance à ne pas perdre : le repérage est automatique, **l'envoi ne l'est
  pas**. C'est le conseil syndical qui déclenche la relance groupée depuis le
  reporting. Écrire « relance automatique » ailleurs serait la deuxième
  promesse fausse sur le même sujet.

  🔴 La colonne `ticket.echeance` RESTE en base : elle est vide, personne ne la
  lit, et une migration appliquée ne se modifie jamais. La retirer est un geste
  à part — pas un effet de bord d'une correction d'écran.

  ## 🔴 « Visible jusqu'au » a existé une demi-journée (22/09/2026)

  Livré le matin en v2.11.0 pour la troisième famille d'actualités — « à durée de
  vie choisie » —, retiré l'après-midi, arbitré à l'écran :

  > « Visible jusqu'au ne doit pas être demandé à l'utilisateur. Cette date est
  >   à enlever. Elle est calculée par l'appli. »

  La péremption se déduit donc de `fin`, sinon `debut`, sinon jamais. Ce qui n'a
  pas de date d'événement ne périme pas — et n'en a pas besoin : l'archivage
  automatique à trente jours couvre ce cas depuis le 19/08/2026, pour les sept
  objets du site. **Le champ faisait saisir ce que le produit savait déjà
  décider**, ce qui est la définition même du champ en trop.

  ## Ce que la date dispense d'écrire

  Renseigner `debut` rend la **description facultative** : « Coupure d'eau —
  jeudi 9h-12h » se suffit. La règle est au serveur (`app/utils/quand.py`), et
  l'écran ne fait que la refléter — c'est ce qui a manqué jusqu'ici, l'astérisque
  de « Description * » ne vivant QUE dans le formulaire.
-->
<script lang="ts">
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import { fmtDate } from '$lib/date';
	import { SECTIONS_LIBELLE } from '$lib/entites/types';

	/** Préfixe des identifiants — l'écran en ouvre parfois plusieurs à la fois. */
	export let idPrefixe: string;

	export let premiere = false;

	/** `datetime-local` rend `''` quand le champ est vide, jamais `null`. */
	export let debut = '';
	export let fin = '';

	/** Repliée par défaut — la valeur vient de la déclaration (#1095). */
	export let pliable = false;

	/**  🔴 « Sans date » est le DÉFAUT : une date saisie rouvre la section.
	 *
	 *   ⚠️ Comparer à vide et non à « renseigné » : c'est la nuance qui a fait
	 *   que rien ne pliait à la première écriture (21/09/2026). */
	$: resume = debut ? `à partir du ${fmtDate(debut)}` : 'sans date';
</script>

<SectionFormulaire
	titre={SECTIONS_LIBELLE.quand}
	{premiere}
	{pliable}
	{resume}
	ouvrirSiRenseignee={!!debut || !!fin}
	idTitre="{idPrefixe}-quand"
>
	<div class="quand-grille">
		<div class="field">
			<label for="{idPrefixe}-debut">Début</label>
			<input id="{idPrefixe}-debut" type="datetime-local" bind:value={debut} />
		</div>
		<div class="field">
			<label for="{idPrefixe}-fin">Fin</label>
			<input id="{idPrefixe}-fin" type="datetime-local" bind:value={fin} />
		</div>
	</div>
	<p class="quand-aide">
		Une <strong>date de début</strong> fait paraître l'entrée au calendrier — et dispense d'écrire une
		description.
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
