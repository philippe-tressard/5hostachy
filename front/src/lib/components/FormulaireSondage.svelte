<!--
  Le formulaire de création d'un sondage — extrait de `sondages/+page.svelte` le
  16/08/2026.

  POURQUOI. La page portait encore DEUX formulaires (sondage et annonce) et 812
  lignes : le garde-fou de modularité refuse qu'un fichier déjà au-dessus de 500
  grossisse (`standards/02` §6). La règle est de découper quand on y touche.

  ⚠️ CE QUI CHANGE VRAIMENT ICI, et qui n'est pas un déplacement de code : le
  ciblage du sondage rejoint le STANDARD du site.

  Jusqu'ici, cet écran était le seul à cibler avec ses propres notions —
  `batiments_ids` (des identifiants de bâtiments) et `profils_autorises` (des
  statuts bruts) — servies par un composant qui n'existait que pour lui. Deux
  conséquences visibles, l'une esthétique et l'autre fonctionnelle :

    • son sélecteur avait sa propre typographie et un bouton « Réinitialiser »
      que ni `PerimetrePicker` ni `DestinatairePicker` n'ont ;
    • on ne pouvait cibler NI le parking, NI l'AFUL, NI un espace de bâtiment —
      l'arborescence complète des périmètres lui était inaccessible.

  Le modèle a suivi (migration 0147) : `perimetre_cible` + `public_cible`, comme
  les publications, et `sondage_accessible` applique désormais exactement la même
  règle que `publication_visible`. Décision de l'utilisateur le 16/08/2026, après
  qu'on lui a présenté le choix « apparence seulement » ou « modèle compris ».
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import { sondages as sondagesApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { perimetreDefautListe } from '$lib/perimetres';

	//  L'API des sondages ne rend pas de type dédié : la page recharge sa liste.
	const dispatch = createEventDispatcher<{ cree: unknown }>();

	type OptionForm = { libelle: string; champ_libre: boolean };

	let question = '';
	let description = '';
	let clotureLe = '';
	let resultatsPublics = true;
	let options: OptionForm[] = [
		{ libelle: '', champ_libre: false },
		{ libelle: '', champ_libre: false },
	];
	let perimetreCible: string[] = perimetreDefautListe();
	let publicCible: string[] = ['résidents'];
	let partagerWhatsapp = false;
	let envoyerSyndic = false;
	let envoyerCs = false;
	let submitting = false;

	function ajouterOption() {
		options = [...options, { libelle: '', champ_libre: false }];
	}
	function retirerOption(i: number) {
		options = options.filter((_, idx) => idx !== i);
	}
	function monter(i: number) {
		if (i === 0) return;
		const arr = [...options];
		[arr[i - 1], arr[i]] = [arr[i], arr[i - 1]];
		options = arr;
	}
	function descendre(i: number) {
		if (i === options.length - 1) return;
		const arr = [...options];
		[arr[i], arr[i + 1]] = [arr[i + 1], arr[i]];
		options = arr;
	}

	function reinitialiser() {
		question = '';
		description = '';
		clotureLe = '';
		resultatsPublics = true;
		options = [{ libelle: '', champ_libre: false }, { libelle: '', champ_libre: false }];
		perimetreCible = perimetreDefautListe();
		publicCible = ['résidents'];
		partagerWhatsapp = false;
		envoyerSyndic = false;
		envoyerCs = false;
	}

	async function creer() {
		const opts = options
			.map((o, i) => ({ libelle: o.libelle, ordre: i, champ_libre: o.champ_libre }))
			.filter((o) => o.libelle.trim());
		if (!question || opts.length < 2) {
			toast('error', 'Question et au moins 2 options requises');
			return;
		}
		submitting = true;
		try {
			const cree = await sondagesApi.create({
				question,
				description: description || undefined,
				cloture_le: clotureLe ? new Date(clotureLe).toISOString() : undefined,
				resultats_publics: resultatsPublics,
				options: opts,
				//  Comme les publications : un ciblage vide vaut « aucune
				//  restriction », c'est le serveur qui en décide (`visibility.py`).
				perimetre_cible: perimetreCible.length > 0 ? perimetreCible : null,
				public_cible: publicCible.length > 0 ? publicCible : null,
				partager_whatsapp: partagerWhatsapp,
				envoyer_syndic: envoyerSyndic,
				envoyer_cs: envoyerCs,
			});
			reinitialiser();
			toast('success', 'Sondage créé');
			dispatch('cree', cree);
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			submitting = false;
		}
	}
</script>

<FormulaireCreation titre="Nouveau sondage">
	<form on:submit|preventDefault={creer}>
		<!--  1. Titre — ici, la question posée. -->
		<SectionFormulaire premiere>
			<div class="field champ-large">
				<label for="sondage-question">Question *</label>
				<input id="sondage-question" bind:value={question} required />
			</div>
		</SectionFormulaire>

		<!--  2. Champs spécifiques du sondage : sa clôture et ses options. -->
		<SectionFormulaire titre="Réponses possibles">
			<div class="options">
				{#each options as opt, i (i)}
					<div class="option">
						<div class="option-ligne">
							<span class="option-rang">{i + 1}.</span>
							<input class="option-saisie" bind:value={options[i].libelle}
								placeholder="Option {i + 1}" aria-label="Libellé de l'option {i + 1}" />
							<button type="button" class="btn btn-sm btn-outline" title="Monter"
								aria-label="Monter l'option {i + 1}"
								disabled={i === 0} on:click={() => monter(i)}>↑</button>
							<button type="button" class="btn btn-sm btn-outline" title="Descendre"
								aria-label="Descendre l'option {i + 1}"
								disabled={i === options.length - 1} on:click={() => descendre(i)}>↓</button>
							{#if options.length > 2}
								<button type="button" class="btn btn-sm btn-outline option-supprimer"
									title="Supprimer" aria-label="Supprimer l'option {i + 1}"
									on:click={() => retirerOption(i)}>✕</button>
							{/if}
						</div>
						<label class="case case-secondaire">
							<input type="checkbox" bind:checked={options[i].champ_libre} />
							<span>Champ libre (le répondant pourra préciser sa réponse par écrit)</span>
						</label>
					</div>
				{/each}
				<button type="button" class="btn btn-sm btn-outline" on:click={ajouterOption}>
					+ Ajouter une option
				</button>
			</div>
		</SectionFormulaire>

		<SectionFormulaire titre="Clôture">
			<div class="form-grid">
				<div class="field">
					<label for="sondage-cloture">Date de clôture</label>
					<input id="sondage-cloture" type="datetime-local" bind:value={clotureLe} />
				</div>
				<div class="field">
					<label class="case">
						<input type="checkbox" bind:checked={resultatsPublics} />
						<span>Résultats visibles avant clôture</span>
					</label>
				</div>
			</div>
		</SectionFormulaire>

		<!--  4 à 9 : ordre, intitulés et séparations hérités du composant partagé.
		      Le sondage n'a ni photos ni documents. -->
		<ChampsCommuns
			idPrefixe="sondage"
			avecPerimetre bind:perimetre={perimetreCible}
			avecDestinataires bind:destinataires={publicCible}
			avecDescription bind:description
			descriptionPlaceholder="Description du sondage…"
			avecDiffusion
			bind:whatsapp={partagerWhatsapp}
			bind:syndic={envoyerSyndic}
			bind:cs={envoyerCs}
		/>

		<!--  Pas de bouton « Annuler » ici : la commande vit dans l'en-tête de page,
		      où le bouton d'ouverture bascule (#367). -->
		<div class="form-actions">
			<button class="btn btn-primary" disabled={submitting}>
				{submitting ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
	</form>
</FormulaireCreation>

<style>
	.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr)); gap: .75rem; }
	.form-grid .field { margin-bottom: 0; }

	.options { display: flex; flex-direction: column; gap: .5rem; align-items: flex-start; }
	.option {
		width: 100%;
		display: flex;
		flex-direction: column;
		gap: .25rem;
		padding: .6rem .75rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-bg-subtle, #fafafa);
	}
	.option-ligne { display: flex; gap: .4rem; align-items: center; }
	.option-rang { font-size: .78rem; color: var(--color-text-muted); min-width: 1.1rem; text-align: right; }
	.option-saisie {
		flex: 1;
		min-width: 0;
		padding: .45rem .6rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		font-size: .9rem;
		background: var(--color-bg);
	}
	.option-supprimer { color: var(--color-danger, #dc2626); }

	/*  ⚠️ Une case et son libellé, NOMMÉS. La page portait un `input, textarea {
	    width: 100% }` — un sélecteur d'ÉLÉMENT nu, qui atteignait donc aussi les
	    cases à cocher : chacune s'étirait sur toute la largeur et repoussait son
	    texte à l'autre bout de la ligne. C'est le défaut que l'utilisateur a
	    signalé sur le sondage ET sur l'annonce le 16/08/2026 — un seul sélecteur,
	    deux écrans. `npm run lint:styles` le refuse désormais. */
	.case { display: flex; align-items: center; gap: .5rem; cursor: pointer; font-size: .875rem; }
	.case input[type="checkbox"] { width: auto; margin: 0; flex-shrink: 0; }
	.case-secondaire { padding-left: 1.6rem; font-size: .8rem; color: var(--color-text-muted); }
</style>
