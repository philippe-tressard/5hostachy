<!--
  **Section 2 — « Saisi pour »**, prête à poser dans n'importe quel formulaire.

  Trois entités portent cette notion : le ticket depuis l'origine, l'actualité et
  l'événement depuis le 15/09/2026. Ce composant porte ce qui les entoure toutes
  les trois, et qui n'a aucune raison d'être écrit trois fois :

    • la GARDE — réservé au conseil syndical, et seulement là où la déclaration
      rend la section (`sectionPresente`) ;
    • le CHARGEMENT des résidents proposables, et son échec sans conséquence.

  La saisie elle-même reste dans `ChampSaisiPour` ; les deux conversions
  (objet → mode, mode → charge utile) dans `$lib/saisiPour`. Trois fichiers, trois
  responsabilités, et la notion n'est écrite qu'une fois dans chacun.

  ## 🔴 Pourquoi il existe

  `FormulaireActualite` est passé de 483 à 547 lignes en recevant cette section
  en ligne, et le garde-fou de modularité (rang 1) l'a refusé. La règle répond
  alors « découper avant d'ajouter » — et les trois réponses possibles
  (`ux-patterns` §0) désignaient ici la deuxième : **remonter la règle d'un
  cran**, parce que ce que j'ajoutais ne parlait pas de l'actualité, il parlait de
  « Saisi pour ».

  Raboter n'en est jamais une : c'est la seule des trois qui satisfait le
  contrôle sans rien améliorer.

  ⚠️ **La garde est ici, pas chez l'appelant.** Un écran qui la recopierait
  pourrait l'oublier — et proposerait alors à un résident de déposer au nom d'un
  autre. Elle n'est pas une commodité d'affichage : c'est la règle.
-->
<script lang="ts">
	import { onMount } from 'svelte';

	import { admin as adminApi } from '$lib/api';
	import ChampSaisiPour from '$lib/components/ChampSaisiPour.svelte';
	import type { ModeSaisiPour, SaisiPourValeurs } from '$lib/saisiPour';
	import { chargeUtile, modeDepuis, motifIncomplet } from '$lib/saisiPour';
	import { isCS } from '$lib/stores/auth';

	/**  La section 2 est-elle rendue dans cet état&nbsp;? **Calculé par l'appelant.**
	 *
	 *   🔴 Et c'est délibéré, sur refus de `lint:etats` : ce contrôle vérifie que
	 *   toute divergence entre états est déclarée, et il lit `sectionPresente(X, …)`
	 *   où X doit être une entité **nommée**. Recevoir l'entité en variable ici
	 *   sortait l'appel de son champ de vision — le composant aurait décidé du
	 *   rendu sans qu'aucun contrôle ne sache pour quelle entité.
	 *
	 *   L'appelant écrit donc `presente={sectionPresente(PUBLICATION, etat,
	 *   'specifiques')}`, le contrôle le voit, et ce composant ne connaît plus que
	 *   la réponse. Le garde-fou a eu raison contre ma première écriture. */
	export let presente = false;

	/**  L'objet déjà enregistré, d'où vient l'état initial. `null` en création.
	 *
	 *   ⚠️ Sans lui, la section proposerait « En mon nom » sur un objet déposé
	 *   pour quelqu'un — et l'effacerait au premier enregistrement. */
	export let objet: SaisiPourValeurs | null = null;

	/**  🔴 CE QUE L'APPELANT LIT, et la seule chose dont il a besoin : les trois
	 *   champs prêts à transmettre, et le motif qui empêche d'enregistrer.
	 *
	 *   L'état de saisie — mode, identifiant, nom, courriel — reste ICI. Le
	 *   formulaire ne s'en sert jamais séparément : le lui faire porter en
	 *   quatre variables liées ne lui apprenait rien et l'allongeait d'autant,
	 *   sur trois écrans. */
	export let charge: Required<SaisiPourValeurs> = chargeUtile('moi', null, '', '');
	export let motif: string | null = null;

	let mode: ModeSaisiPour = modeDepuis(objet);
	let userId: number | null = objet?.saisi_pour_user_id ?? null;
	let nom = objet?.saisi_pour_nom ?? '';
	let email = objet?.saisi_pour_email ?? '';

	/**  Les résidents proposables. Chargés ICI parce que la liste ne sert qu'à
	 *   cette section : la demander depuis trois écrans reviendrait à écrire trois
	 *   fois le même filtre, et à le voir diverger au premier tri changé. */
	let residents: { id: number; prenom: string; nom: string; email: string }[] = [];

	$: rendue = $isCS && presente;
	$: charge = chargeUtile(mode, userId, nom, email);
	//  ⚠️ `null` quand la section n'est pas rendue : un formulaire ne peut pas
	//  être bloqué par un champ qu'il n'affiche pas. C'est le pendant exact de la
	//  garde ci-dessus — la même condition décide de montrer ET d'exiger.
	$: motif = rendue ? motifIncomplet(mode, userId, nom) : null;

	onMount(async () => {
		//  Rien à charger quand la section n'est pas rendue : un appel dont
		//  personne ne lit le résultat est un appel de trop.
		if (!rendue) return;
		try {
			const tous = await adminApi.utilisateurs();
			residents = tous
				.filter((u: any) => u.actif)
				.sort((a: any, b: any) => `${a.prenom} ${a.nom}`.localeCompare(`${b.prenom} ${b.nom}`));
		} catch {
			//  ⚠️ Échec SANS conséquence, et c'est délibéré : « En mon nom » et
			//  « personne extérieure » restent utilisables sans cette liste. Bloquer
			//  tout le formulaire parce qu'un annuaire n'a pas répondu serait
			//  disproportionné — et la section dirait alors quelque chose de faux sur
			//  ce que le serveur sait faire.
		}
	});
</script>

{#if rendue}
	<ChampSaisiPour bind:mode bind:userId bind:nom bind:email {residents} />
{/if}
