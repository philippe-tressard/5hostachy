<!--
  **Enregistrer ou corriger un accès** — un badge Vigik, une télécommande.

  ## Pourquoi ce composant (14/09/2026, #953)

  L'écran du parc était en lecture seule depuis le 06/09 (#805). Les gestes ont
  été demandés en priorité haute — *« l'export, la suppression, l'ajout ou la
  modification d'un vigik / télécommande n'est pas (encore) possible »* — et le
  formulaire vit ici plutôt que dans la table : une table qui porte son
  formulaire dépasse le plafond de modularité au premier champ ajouté, et un
  formulaire est un objet à part entière (`Formulaire*.svelte`, quinze fois dans
  ce dépôt).

  ## Ce qu'il ne décide pas

  Il ne choisit ni son cadre ni sa place : l'écran appelant le fait, parce que
  c'est lui qui sait si l'on crée (en tête de liste) ou si l'on corrige (à la
  place de la ligne). C'est la règle de `ux-patterns` §14 ter, et la distinction
  que `CadreFormulaire` porte pour les six formulaires qui la connaissent.

  ⚠️ Il ne compose pas non plus le libellé d'un périmètre : `PerimetrePicker` à
  la saisie, `BadgePerimetre` à la lecture. Un troisième rendu du même objet
  serait la divergence de demain.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import CadreFormulaire from '$lib/components/CadreFormulaire.svelte';
	import PerimetrePicker from '$lib/components/PerimetrePicker.svelte';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import EtoileRequis from '$lib/components/EtoileRequis.svelte';
	import { libelleLotPourBadge, lotsPourBadge, type LotPourBadge } from '$lib/imports-acces';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import type { ChoixAcces } from '$lib/api/acces';

	const dispatch = createEventDispatcher<{ annule: void; enregistre: void }>();

	/** Les deux types d'accès — la liste vient de l'écran, qui la tient du serveur. */
	//  ⚠️ `readonly` : la liste vient d'un `as const` de l'écran appelant, et
	//  exiger un tableau mutable l'obligerait à en faire une copie — pour une
	//  liste que ce composant ne modifie jamais.
	export let types: readonly { val: string; label: string }[] = [];
	/** Les comptes de la copropriété — pour dire qui a l'objet en main. */
	export let porteurs: { id: number; affiche: string }[] = [];
	/**  🔴 Les lots, avec le copropriétaire que le fichier leur donne (#1194) :
	 *   un badge appartient au LOT, et ses porteurs s'en déduisent. */
	export let lots: LotPourBadge[] = [];

	/**  🔒 Ce que chaque type d'accès a le droit d'ouvrir, servi par le serveur.
	 *
	 *   ⚠️ Indexé par la clé du TYPE, et relu à chaque changement de type : la
	 *   rangée de pastilles suit alors la pastille de type, dans le même écran.
	 *   Un badge qui change de nature ne garde pas les portes de l'autre. */
	export let choixAcces: Record<string, ChoixAcces> = {};

	/**  L'objet en cours de saisie, lié en deux sens : l'écran porte son cycle.
	 *
	 *   ⚠️ `perimetre_cible` vide veut dire **« on ne sait pas »**, pas « toute la
	 *   copropriété ». Le serveur le distingue : champ absent ⇒ il déduit le
	 *   bâtiment ; liste vide ⇒ il respecte le vide. Une valeur généreuse par
	 *   défaut sur un droit d'accès se lirait comme une décision. */
	export let saisie: {
		type: string;
		code: string;
		porteur_id: number | null;
		lot_id: number | null;
		perimetre_cible: string[];
		statut: string;
		ticket_numero: string;
	};

	/** `true` quand on corrige : le TYPE ne se change plus, il identifie l'objet. */
	export let modeEdition = false;
	export let enregistrement = false;
	/**  Ce qui identifie l'objet corrigé — relayé à `FormulaireCreation`, qui
	 *   ramène le formulaire à l'écran s'il en est sorti. Inutile en édition
	 *   dans la ligne : rien n'a bougé. */
	export let cle: unknown = undefined;
	/** `false` quand le formulaire s'ouvre DANS une ligne : pas de cadre imbriqué. */
	export let encadre = true;

	//  Les états d'un accès, et leur libellé. Trois valeurs : sous le seuil des
	//  listes courtes, donc des pastilles (`ux-patterns` §0).
	const STATUTS = [
		{ val: 'actif', label: '✅ Actif' },
		{ val: 'suspendu', label: '⏸️ Suspendu' },
		{ val: 'perdu', label: '🔎 Perdu' },
	];

	//  Un lot OU un détenteur : le serveur accepte l'un ou l'autre (#1194).
	$: incomplet = !saisie.code.trim() || (!saisie.lot_id && !saisie.porteur_id);
	//  Les lots de la nature du badge d'abord : l'appartement pour un Vigik,
	//  le parking pour une télécommande — ce que dit le serveur (`types_lot`).
	$: natureLot = saisie.type === 'vigik' ? 'appartement' : 'parking';
	$: lotsTries = lotsPourBadge(lots, natureLot);
	//  ⚠️ `?? null` et non `?? []` : `null` dit « on ne restreint pas » — le temps
	//  que la liste arrive du serveur, le sélecteur reste celui de partout
	//  ailleurs. Une liste vide dirait « rien n'est possible », et l'écran
	//  paraîtrait cassé pendant le chargement.
	$: choixDuType = choixAcces[saisie.type];
	$: accesAutorises = choixDuType?.codes ?? null;
	//  L'aide se règle sur ce que le SERVEUR dit du type, jamais sur son nom :
	//  dire « il est déduit du lot » d'une télécommande décrirait un autre écran
	//  que celui qu'on a sous les yeux.
	$: accesSuitLeLot = choixDuType?.suit_le_lot ?? true;
</script>

<!--  🔴 LE CADRE EST POSÉ ICI, parce que ce composant CONNAÎT le geste
      (`modeEdition`). C'est la règle de `ux-patterns` §14, et ce que
      `lint:formulaires` vérifie — un écran qui poserait le cadre devrait
      monter deux fois le même formulaire avec les mêmes props, et les deux
      copies divergeraient au premier champ ajouté. -->
<CadreFormulaire
	edition={modeEdition}
	titre={modeEdition ? "Corriger l'accès" : 'Enregistrer un accès'}
	{encadre}
	{cle}
	on:fermer={() => dispatch('annule')}
>
	<!--  ⚠️ L'ordre suit `ux-patterns` §9 sexies : ce qui IDENTIFIE l'objet d'abord
	      (type, code, porteur), le périmètre ensuite, le reste après. Le ticket lié
	      vient en dernier parce qu'il ne décrit pas le badge — il dit pourquoi on
	      l'enregistre. -->
	{#if !modeEdition}
		<SectionFormulaire titre="Type" premiere>
			<!--  ⚠️ `tous={false}` : `ChoixPastilles` propose « Tous » par défaut, ce
			      qui a du sens pour un FILTRE et aucun pour une saisie — un accès est
			      d'un type ou de l'autre. La prop existe justement pour cela. -->
			<ChoixPastilles options={types} bind:valeur={saisie.type} tous={false} />
		</SectionFormulaire>
	{/if}

	<!--  🔴 CHAQUE champ dans sa section (#1329) : Code, Lot, En main et Affaire
	      liée étaient posés à plat entre les sections — ils se lisaient comme
	      une partie de la section d'au-dessus. -->
	<SectionFormulaire
		titre="Code"
		requis
		rempli={!!saisie.code.trim()}
		pour="acces-code"
		premiere={modeEdition}
	>
		<div class="field champ-large">
			<input id="acces-code" type="text" bind:value={saisie.code} placeholder="4521, 417D5927…" />
			<span class="aide">La référence gravée sur l'objet, telle qu'elle s'y lit.</span>
		</div>
	</SectionFormulaire>

	<SectionFormulaire titre="Lot et porteur">
		<label class="field champ-large">
			<span>Lot<EtoileRequis vide={!saisie.lot_id && !saisie.porteur_id} /></span>
			<select bind:value={saisie.lot_id}>
				<option value={null}>— aucun lot —</option>
				{#each lotsTries as l (l.id)}
					<option value={l.id}>{libelleLotPourBadge(l)}</option>
				{/each}
			</select>
			<span class="aide">
				Le badge appartient au lot : tous ses copropriétaires en sont porteurs, conjoint compris.
			</span>
		</label>

		<label class="field champ-large">
			En main
			<select bind:value={saisie.porteur_id}>
				<option value={null}>— personne de connu —</option>
				{#each porteurs as p (p.id)}
					<option value={p.id}>{p.affiche}</option>
				{/each}
			</select>
			<span class="aide">
				Qui a l'objet en main, s'il est connu. Il en est prévenu dans l'application.
			</span>
		</label>
	</SectionFormulaire>

	<!--  🔹 L'accès EST un périmètre, et se saisit donc comme tous les autres. -->
	<SectionFormulaire titre="Accès" idTitre="acces-perimetre-titre">
		<PerimetrePicker
			bind:value={saisie.perimetre_cible}
			titre=""
			requis={false}
			codesAutorises={accesAutorises}
		/>
		<!--  🔒 Les choix sont RESTREINTS par type (15/09/2026) : un badge ne
		      commande pas un local à poubelles. La liste vient du serveur, qui
		      l'oppose aussi à la requête — l'écran propose, il ne protège pas. -->
		<p class="aide">
			{#if accesSuitLeLot}
				Ce que le badge ouvre. Laissé vide à la création, il est déduit&nbsp;: le bâtiment du lot,
				ou celui du porteur si tous ses lots sont dans le même.
			{:else}
				Ce que la télécommande ouvre. Laissé vide, elle reçoit les portails d'accès de la résidence.
			{/if}
		</p>
	</SectionFormulaire>

	<SectionFormulaire titre="État">
		<ChoixPastilles options={STATUTS} bind:valeur={saisie.statut} tous={false} />
		<p class="aide">
			Un badge perdu ou suspendu reste dans le parc&nbsp;: c'est ce qui permet de savoir qu'il
			circule. Seul un administrateur peut retirer une ligne saisie par erreur.
		</p>
	</SectionFormulaire>

	<!--  Sans « Facultatif. » : l'absence d'étoile le dit (cadre R3). -->
	<SectionFormulaire titre="Affaire liée" pour="acces-affaire">
		<div class="field champ-large">
			<input
				id="acces-affaire"
				type="text"
				bind:value={saisie.ticket_numero}
				placeholder="TK-241422"
			/>
			<span class="aide">
				Le geste s'inscrit alors dans le fil de cette affaire. Un numéro inconnu refuse
				l'enregistrement plutôt que de perdre le lien en silence.
			</span>
		</div>
	</SectionFormulaire>

	<PiedFormulaire
		enCours={enregistrement}
		desactive={incomplet}
		soumission={false}
		on:annule={() => dispatch('annule')}
		on:enregistre={() => dispatch('enregistre')}
	/>
</CadreFormulaire>
