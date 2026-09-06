<!--
  Le formulaire d'une petite annonce — celui qu'on remplit pour la DÉPOSER, et
  celui qu'on rouvre pour la CORRIGER. Un seul fichier pour les deux gestes.

  Extrait de `sondages/+page.svelte` le 16/08/2026 (plafond de modularité), rendu
  **paramétrable** le 18/08/2026 sur demande : *« pour les petites annonces tu
  peux ajouter le périmètre et il manque le mode édition »*.

  ## Le mode édition n'existait pas du tout

  Une fois l'annonce déposée, on pouvait changer son statut, gérer ses photos, la
  supprimer — mais **pas corriger une faute de frappe, ni baisser un prix**. Le
  seul recours était supprimer et redéposer, ce qui perdait les réponses des
  voisins.

  Ce n'était pas une contrainte serveur : `PATCH /annonces/{id}` existait, avec
  ses sept champs, **et personne ne l'appelait**.

  ## Le périmètre : une absence de notion qu'un ÉCRAN avait décrétée

  L'en-tête de ce fichier disait, jusqu'à aujourd'hui :

  > « L'annonce n'a ni périmètre ni destinataires : elle s'adresse à tous les
  >   résidents par nature. »

  🔴 C'est ce que `sansObjet` sert à dire, et **ça se déclare dans l'entité, pas
  dans un commentaire de formulaire** : un commentaire n'est lu par aucun
  contrôle. Le périmètre est ouvert (migration 0151) ; les destinataires, eux,
  restent `sansObjet` — et cette fois c'est écrit là où `lint:etats` le lit.

  ## Ce qui n'est PAS gouverné par `modeEdition`

  Aucune section. Les six props de `ChampsCommuns` passent par
  `sectionPresente(ANNONCE, etat, …)`, et `npm run lint:etats` refuse qu'on
  remette une condition en dur. Le mode ne décide plus que du **geste** : `POST`
  ou `PATCH`, et l'intitulé de la boîte.

  ⚠️ **Les PHOTOS ne sont pas ici, et c'est une dette déclarée** (motif `api`,
  #441) : `POST /annonces/{id}/photo` exige l'identifiant de l'annonce. Elles se
  gèrent depuis la carte, dans les deux gestes — la rouvrir ici en correction
  donnerait deux chemins concurrents vers la même liste.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import CadreFormulaire from '$lib/components/CadreFormulaire.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import WorkflowPastilles from '$lib/components/WorkflowPastilles.svelte';
	import { CATEGORIES_ANNONCE, OPTIONS_STATUT_ANNONCE, TYPES_ANNONCE } from '$lib/annonces';
	import { annonces as annoncesApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { perimetreDefautListe } from '$lib/utils';
	import type { Etat } from '$lib/entites/types';
	import { sectionPresente } from '$lib/entites/types';
	import { ANNONCE } from '$lib/entites/annonce';

	/**  L'annonce à CORRIGER, avec ses valeurs déjà saisies. `null` (défaut) =
	 *   dépôt. Le mode ne change pas pendant la vie du composant : l'appelant la
	 *   remonte à neuf (`{#key}`) quand il passe d'une annonce à l'autre — même
	 *   contrat que `FormulaireActualite` et `FormulaireTicket`. */
	export let annonce: any = null;

	const modeEdition = annonce !== null;

	/**  L'état du cadre #430 que ce formulaire rend. C'est LUI qui décide des
	 *   sections — voir `$lib/entites/annonce`, qui porte chaque divergence avec
	 *   son motif. */
	const etat: Etat = modeEdition ? 'edition' : 'creation';

	const dispatch = createEventDispatcher<{ cree: any; modifie: any; annule: void }>();

	//  ── 1. Titre ────────────────────────────────────────────────────────────
	let titre = annonce?.titre ?? '';

	//  ── 2. Champs spécifiques : ce qui décrit l'objet ───────────────────────
	let typeAnnonce = annonce?.type_annonce ?? 'vente';
	let categorie = annonce?.categorie ?? 'divers';
	let prix = annonce?.prix !== null && annonce?.prix !== undefined ? String(annonce.prix) : '';
	let negotiable = annonce?.negotiable ?? false;

	//  ── 3. Workflow ─────────────────────────────────────────────────────────
	//  Absent à la CRÉATION (motif `geste`) : une annonce qu'on dépose est en
	//  cours par construction. La déclaration le dit, ce fichier ne le décide pas.
	let statut = annonce?.statut ?? 'en_cours';

	//  ── 4 à 9 ───────────────────────────────────────────────────────────────
	//  Copie défensive du périmètre : le tableau vient de l'annonce affichée dans
	//  la liste. Lié tel quel, une sélection abandonnée resterait visible sur la
	//  carte alors que rien n'a été enregistré.
	let perimetreCible: string[] = [...(annonce?.perimetre_cible ?? perimetreDefautListe())];
	//  Section 5 (#782). Vide = tous les résidents, des DEUX côtés : c'est ce
	//  que `concerneTousLesResidents` lit ici et `public_cible_visible` côté
	//  serveur. Ne pas initialiser à une liste de codes « par défaut » —
	//  ce serait choisir un ciblage à la place de l'auteur.
	let publicCible: string[] = [...(annonce?.public_cible ?? [])];
	let description = annonce?.description ?? '';
	let contactVisible = annonce?.contact_visible ?? true;

	let submitting = false;

	const titreBoite = modeEdition ? "Modifier l'annonce" : 'Déposer une annonce';

	function reinitialiser() {
		titre = '';
		description = '';
		typeAnnonce = 'vente';
		categorie = 'divers';
		prix = '';
		negotiable = false;
		contactVisible = true;
		perimetreCible = perimetreDefautListe();
	}

	async function enregistrer() {
		if (!titre.trim() || !description) {
			toast('error', 'Titre et description obligatoires');
			return;
		}
		//  Le prix ne concerne que la vente : le champ disparaît pour un don ou une
		//  recherche, et la valeur doit disparaître avec lui. Sans cette remise à
		//  zéro, passer une vente en don garderait le montant en base — la carte
		//  n'afficherait plus « Gratuit » mais l'ancien prix.
		const prixEnvoye = typeAnnonce === 'vente' && prix ? parseFloat(prix) : null;
		submitting = true;
		try {
			const charge = {
				titre: titre.trim(),
				description,
				type_annonce: typeAnnonce,
				categorie,
				prix: prixEnvoye,
				negotiable: typeAnnonce === 'vente' ? negotiable : false,
				contact_visible: contactVisible,
				perimetre_cible: perimetreCible,
				public_cible: publicCible,
				//  L'état ne part QU'EN correction : à la création, la section est
				//  absente et le serveur pose le défaut. L'envoyer quand même ferait
				//  écrire un `statut_change_le` pour une transition qui n'a pas eu lieu.
				...(modeEdition ? { statut } : {}),
			};
			if (annonce) {
				const maj: any = await annoncesApi.update(annonce.id, charge);
				toast('success', 'Annonce mise à jour');
				dispatch('modifie', maj);
				return;
			}
			const cree: any = await annoncesApi.create(charge);
			reinitialiser();
			toast('success', 'Annonce publiée !');
			dispatch('cree', cree);
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			submitting = false;
		}
	}
</script>

<!--
	Le cadre suit le GESTE (`ux-patterns` §14 bis) : boîte dans la page au dépôt,
	fenêtre à la correction. Le choix vit dans `CadreFormulaire`, écrit une fois
	pour les six formulaires concernés.

	🔴 Ce fichier était le SEPTIÈME écran de #640, et le seul jamais listé dans
	son « Reste » : il éditait DANS la carte, en remplaçant le corps de l'annonce.
	Le ticket citait deux écrans déjà conformes et oubliait celui-ci — c'est ce
	qui a décidé l'écriture de `lint:cadre-geste`, qui le recense désormais.
-->
<CadreFormulaire edition={modeEdition} titre={titreBoite}>
	<form on:submit|preventDefault={enregistrer}>
		<!--  1. Titre. -->
		<SectionFormulaire premiere>
			<div class="field champ-large">
				<label for="annonce-titre-{annonce?.id ?? 'new'}">Titre *</label>
				<input
					id="annonce-titre-{annonce?.id ?? 'new'}"
					bind:value={titre}
					required
					placeholder="Ex. Lave-linge Samsung presque neuf"
				/>
			</div>
		</SectionFormulaire>

		<!--  2. Champs spécifiques de l'annonce. -->
		{#if sectionPresente(ANNONCE, etat, 'specifiques')}
			<SectionFormulaire titre="L'objet">
				<div class="form-grid">
					<div class="field">
						<label for="annonce-type-{annonce?.id ?? 'new'}">Type</label>
						<select id="annonce-type-{annonce?.id ?? 'new'}" bind:value={typeAnnonce}>
							{#each TYPES_ANNONCE as t (t.val)}<option value={t.val}>{t.label}</option>{/each}
						</select>
					</div>
					<div class="field">
						<label for="annonce-categorie-{annonce?.id ?? 'new'}">Catégorie</label>
						<select id="annonce-categorie-{annonce?.id ?? 'new'}" bind:value={categorie}>
							{#each CATEGORIES_ANNONCE as c (c.val)}<option value={c.val}>{c.label}</option>{/each}
						</select>
					</div>
					{#if typeAnnonce === 'vente'}
						<div class="field">
							<label for="annonce-prix-{annonce?.id ?? 'new'}">Prix (€)</label>
							<input
								id="annonce-prix-{annonce?.id ?? 'new'}"
								type="number"
								min="0"
								step="0.01"
								bind:value={prix}
								placeholder="0.00"
							/>
						</div>
						<div class="field">
							<label class="case">
								<input type="checkbox" bind:checked={negotiable} />
								<span>Prix négociable</span>
							</label>
						</div>
					{/if}
				</div>
			</SectionFormulaire>
		{/if}

		<!--  3. Workflow — des PASTILLES, jamais un `<select>` nu (R3 / #423).
		      La liste vient de `$lib/annonces`, source unique : la carte la rend
		      aussi, dans son raccourci. -->
		{#if sectionPresente(ANNONCE, etat, 'workflow')}
			<SectionFormulaire titre="Où en est cette annonce ?">
				<WorkflowPastilles
					options={OPTIONS_STATUT_ANNONCE}
					valeur={statut}
					on:choisir={(e) => (statut = e.detail)}
				/>
			</SectionFormulaire>
		{/if}

		<!--  4 à 9 : le composant partagé. Aucune de ces sections n'est gouvernée
		      par `modeEdition` — elles le sont par la DÉCLARATION, qui porte chaque
		      divergence avec son motif. -->
		<ChampsCommuns
			idPrefixe="annonce-{annonce?.id ?? 'new'}"
			avecPerimetre={sectionPresente(ANNONCE, etat, 'perimetre')}
			bind:perimetre={perimetreCible}
			avecDestinataires={sectionPresente(ANNONCE, etat, 'destinataires')}
			bind:destinataires={publicCible}
			avecDescription={sectionPresente(ANNONCE, etat, 'description')}
			descriptionRequise
			bind:description
			descriptionPlaceholder="Décrivez l'objet, son état, conditions de remise…"
			avecPhotos={sectionPresente(ANNONCE, etat, 'photos')}
			avecDocuments={sectionPresente(ANNONCE, etat, 'documents')}
			avecDiffusion={sectionPresente(ANNONCE, etat, 'diffusion')}
			avecCanaux={false}
		>
			<svelte:fragment slot="diffusion">
				<div class="field champ-large">
					<label class="case">
						<input type="checkbox" bind:checked={contactVisible} />
						<span>Afficher mes coordonnées aux autres résidents</span>
					</label>
				</div>
			</svelte:fragment>
		</ChampsCommuns>

		<!--  « Annuler » est À CÔTÉ d'« Enregistrer » — norme du 18/08/2026, posée
		      sur Tickets, constatée, puis étendue. L'en-tête de page ne porte plus
		      de seconde commande d'annulation (#367). -->
		<div class="form-actions">
			<button type="button" class="btn btn-outline" on:click={() => dispatch('annule')}
				>Annuler</button
			>
			<button class="btn btn-primary" disabled={submitting}>
				{submitting ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
	</form>
</CadreFormulaire>

<style>
	.form-grid .field {
		margin-bottom: 0;
	}

	/*  La case et son libellé, côte à côte. Ce qui les séparait : la page portait
	    `input, textarea { width: 100% }`, un sélecteur d'ÉLÉMENT nu qui atteignait
	    aussi les cases à cocher — c'est `npm run lint:styles` qui refuse désormais
	    ce genre de sélecteur (v2.65.0). */
</style>
