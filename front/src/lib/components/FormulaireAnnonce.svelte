<!--
  Le formulaire de dépôt d'une petite annonce — extrait de `sondages/+page.svelte`
  le 16/08/2026, pour la même raison que `FormulaireSondage` : la page dépassait
  le plafond de modularité (`standards/02` §6).

  Deux défauts corrigés au passage, tous deux signalés par l'utilisateur :

    • les cases à cocher (« Prix négociable », « Afficher mes coordonnées ») étaient
      séparées de leur libellé par toute la largeur du formulaire. Cause unique et
      partagée avec le sondage : la page portait `input, textarea { width: 100% }`,
      un sélecteur d'ÉLÉMENT nu qui atteignait aussi les cases à cocher ;
    • les sections n'étaient ni nommées ni séparées, et « Afficher mes coordonnées »
      — une décision de DIFFUSION — flottait après le prix.

  L'annonce n'a ni périmètre ni destinataires : elle s'adresse à tous les résidents
  par nature. Ses photos s'ajoutent après publication, depuis la carte de l'annonce
  (l'endpoint a besoin de son identifiant) — c'est inchangé.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import { CATEGORIES_ANNONCE, TYPES_ANNONCE } from '$lib/annonces';
	import { annonces as annoncesApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';

	const dispatch = createEventDispatcher<{ cree: any }>();

	let titre = '';
	let description = '';
	let typeAnnonce = 'vente';
	let categorie = 'divers';
	let prix = '';
	let negotiable = false;
	let contactVisible = true;
	let submitting = false;

	function reinitialiser() {
		titre = '';
		description = '';
		typeAnnonce = 'vente';
		categorie = 'divers';
		prix = '';
		negotiable = false;
		contactVisible = true;
	}

	async function creer() {
		if (!titre || !description) {
			toast('error', 'Titre et description obligatoires');
			return;
		}
		submitting = true;
		try {
			const cree: any = await annoncesApi.create({
				titre,
				description,
				type_annonce: typeAnnonce,
				categorie,
				prix: prix ? parseFloat(prix) : null,
				negotiable,
				contact_visible: contactVisible,
			});
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

<FormulaireCreation titre="Déposer une annonce">
	<form on:submit|preventDefault={creer}>
		<!--  1. Titre. -->
		<SectionFormulaire premiere>
			<div class="field champ-large">
				<label for="annonce-titre">Titre *</label>
				<input id="annonce-titre" bind:value={titre} required
					placeholder="Ex. Lave-linge Samsung presque neuf" />
			</div>
		</SectionFormulaire>

		<!--  2. Champs spécifiques de l'annonce. -->
		<SectionFormulaire titre="L'objet">
			<div class="form-grid">
				<div class="field">
					<label for="annonce-type">Type</label>
					<select id="annonce-type" bind:value={typeAnnonce}>
						{#each TYPES_ANNONCE as t}<option value={t.val}>{t.label}</option>{/each}
					</select>
				</div>
				<div class="field">
					<label for="annonce-categorie">Catégorie</label>
					<select id="annonce-categorie" bind:value={categorie}>
						{#each CATEGORIES_ANNONCE as c}<option value={c.val}>{c.label}</option>{/each}
					</select>
				</div>
				{#if typeAnnonce === 'vente'}
					<div class="field">
						<label for="annonce-prix">Prix (€)</label>
						<input id="annonce-prix" type="number" min="0" step="0.01"
							bind:value={prix} placeholder="0.00" />
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

		<!--  4 à 9 : le composant partagé. Une annonce n'a ni périmètre, ni
		      destinataires, ni pièces jointes à la création — mais elle a bien une
		      décision de diffusion, et c'est là qu'elle se range. -->
		<ChampsCommuns
			idPrefixe="annonce"
			avecDescription descriptionRequise bind:description
			descriptionPlaceholder="Décrivez l'objet, son état, conditions de remise…"
			avecDiffusion
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

		<div class="form-actions">
			<button class="btn btn-primary" disabled={submitting}>
				{submitting ? 'Envoi…' : "Publier l'annonce"}
			</button>
		</div>
	</form>
</FormulaireCreation>

<style>
	.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr)); gap: .75rem; }
	.form-grid .field { margin-bottom: 0; }

	/*  La case et son libellé, côte à côte — voir l'en-tête de ce fichier pour
	    ce qui les séparait. */
	.case { display: flex; align-items: center; gap: .5rem; cursor: pointer; font-size: .875rem; }
	.case input[type="checkbox"] { width: auto; margin: 0; flex-shrink: 0; }
</style>
