<!--
  Le formulaire d'un événement de calendrier.

  Extrait de `calendrier/+page.svelte` le 15/08/2026 : le fichier dépassait le
  plafond de modularité et le garde-fou a refusé qu'il grossisse en recevant le
  chevron et le survol de #362. La règle est « on découpe le fichier QUAND on y
  touche » — c'est ce qui est fait ici, et la frontière est nette : ce bloc n'est
  QUE de la saisie, la décision (`save`, `resetForm`) reste dans la page.

  Les champs passent par `.field`, dont `app.css` porte le style. Ils étaient
  écrits à la main dans une grille maison, et un sélecteur cassé depuis la v1.0
  les laissait SANS aucun style — apparence native du navigateur, blancs à
  bordure noire, là où tout le site est gris et arrondi (#372). Le défaut était
  masqué par la modale ; le passage à la boîte dans la page l'a révélé.
-->
<script lang="ts">
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import AlerteEpinglage from '$lib/components/AlerteEpinglage.svelte';

	/** L'objet de saisie, lié en deux sens : la page porte son cycle de vie. */
	export let form: any;
	export let photosUrls: string[] = [];
	export let fichiersUrls: string[] = [];
	export let types: { val: string; label: string }[] = [];
	export let prestataires: any[] = [];
	export let submitting = false;
	/** Périmètre ciblé, lié en deux sens comme `form`. */
	export let formPerimetreCible: string[] = [];
	/**  Épinglage à l'OUVERTURE : sans lui, l'avertissement de plafond compterait
	 *   une seconde fois un événement déjà épinglé. */
	export let epingleInitial = false;
	/**  Colonnes du kanban. Passées en prop et NON importées : elles sont une
	 *   constante locale de la page, pas un module partagé — les dupliquer ici
	 *   créerait la deuxième liste qui dérive. */
	export let kanbanCols: { id: string; label: string }[] = [];
	/** Appelé à la soumission. La page garde la décision d'enregistrer. */
	export let onSubmit: () => void;
</script>

<form on:submit|preventDefault={onSubmit}>
	<!--  1. Titre. -->
	<SectionFormulaire premiere>
		<div class="field champ-large">
			<label for="ev-titre">Titre *</label>
			<input id="ev-titre" bind:value={form.titre} required />
		</div>
	</SectionFormulaire>

	<!--  2. Champs spécifiques de l'événement. -->
	<SectionFormulaire titre="Détails">
		<div class="form-grid">
			<div class="field">
				<label for="ev-type">Type</label>
				<select id="ev-type" bind:value={form.type}>
					{#each types as t}<option value={t.val}>{t.label}</option>{/each}
				</select>
			</div>
			<div class="field">
				<label for="ev-debut">Date de début *</label>
				<input id="ev-debut" type="date" bind:value={form.debut} required />
			</div>
			<div class="field">
				<label for="ev-heure">Heure (optionnelle)</label>
				<input id="ev-heure" type="time" bind:value={form.debut_heure} />
			</div>
			<div class="field">
				<label for="ev-fin">Fin</label>
				<input id="ev-fin" type="datetime-local" bind:value={form.fin} />
			</div>
			<div class="field">
				<label for="ev-lieu">Lieu</label>
				<input id="ev-lieu" bind:value={form.lieu} />
			</div>
			<div class="field">
				<label for="ev-prestataire">Prestataire</label>
				<select id="ev-prestataire" bind:value={form.prestataire_id}>
					<option value=''>— Aucun —</option>
					{#each prestataires.filter(p => p.actif !== false) as p}
						<option value={String(p.id)}>{p.nom}</option>
					{/each}
				</select>
			</div>
			{#if form.prestataire_id && form.type !== 'maintenance_recurrente'}
				<div class="field">
					<label for="ev-frequence">Fréquence (optionnelle)</label>
					<select id="ev-frequence" bind:value={form.frequence_type}>
						<option value=''>— Pas de récurrence —</option>
						<option value='fois_par_an'>× / an</option>
						<option value='mois'>Tous les N mois</option>
						<option value='semaines'>Toutes les N semaines</option>
					</select>
				</div>
				{#if form.frequence_type}
					<div class="field">
						<label for="ev-frequence-valeur">Valeur</label>
						<input id="ev-frequence-valeur" type="number" min="1" bind:value={form.frequence_valeur} placeholder="ex: 2" />
					</div>
				{/if}
			{/if}
		</div>
	</SectionFormulaire>

	<!--  3. Workflow — où en est cet événement. Le Suivi Kanban était rangé avec
	      l'affichage au fil et les canaux, c'est-à-dire dans la DIFFUSION : il
	      dit où en est le travail, pas qui le voit (`ux-patterns` §9 sexies). -->
	<SectionFormulaire titre="Suivi Kanban" pour="ev-kanban">
		<div class="field champ-large">
			<select id="ev-kanban" bind:value={form.statut_kanban}>
				<option value="">— Pas de suivi Kanban —</option>
				{#each kanbanCols as col}
					<option value={col.id}>{col.label}</option>
				{/each}
			</select>
		</div>
	</SectionFormulaire>

	<!--  4 à 9 : ordre, intitulés et séparations hérités du composant partagé. -->
	<ChampsCommuns
		idPrefixe="ev"
		avecPerimetre bind:perimetre={formPerimetreCible}
		avecDescription bind:description={form.description}
		descriptionPlaceholder="Description de l'événement…"
		avecPhotos bind:photos={photosUrls}
		avecDocuments bind:documents={fichiersUrls}
		avecDiffusion
		bind:whatsapp={form.partager_whatsapp}
		bind:syndic={form.envoyer_syndic}
		bind:cs={form.envoyer_cs}
	>
		<svelte:fragment slot="diffusion">
			<div class="field champ-large">
				<label class="case">
					<input type="checkbox" bind:checked={form.affichable}
						disabled={form.type === 'maintenance_recurrente'} />
					<span>Afficher dans le fil d'activité du tableau de bord</span>
				</label>
				<label class="case" class:desactive={!form.affichable}>
					<input type="checkbox" bind:checked={form.epingle} disabled={!form.affichable} />
					<span>📌 Épingler dans le fil d'activité</span>
				</label>
				<AlerteEpinglage coche={form.epingle} dejaEpingle={epingleInitial} />
				{#if !form.affichable}
					<p class="aide-case">Un événement absent du fil ne peut pas y être épinglé.</p>
				{/if}
				{#if form.type === 'maintenance_recurrente'}
					<p class="aide-case">
						Les maintenances récurrentes restent hors du fil d'activité : elles se suivent dans le Kanban.
					</p>
				{/if}
			</div>
		</svelte:fragment>
	</ChampsCommuns>

	<div class="form-actions">
		<button class="btn btn-primary" disabled={submitting}>{submitting ? 'Enregistrement…' : 'Enregistrer'}</button>
	</div>
</form>

<style>
	/*  Mêmes règles, même raison que dans `FormulairePrestation` : le balisage
	    part avec ses styles, sinon la grille reste dans la page et le formulaire
	    s'affiche en une colonne écrasée (#344, reproduit le 15/08/2026). */
	.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr)); gap: .75rem; }
	.form-grid .field { margin-bottom: 0; }

	/*  Une case et son libellé : ils étaient écrits en `style=` en ligne, avec un
	    `width:auto` posé à la main sur chaque `<input type="checkbox">` pour
	    annuler le `width:100%` des champs de saisie. Nommés ici, ils cessent
	    d'être à réécrire — c'est la même famille de défaut que le sélecteur nu
	    qui a étiré les cases de l'écran Communauté (16/08/2026). */
	.case { display: flex; align-items: center; gap: .5rem; cursor: pointer; }
	.case + .case { margin-top: .4rem; }
	.case input[type="checkbox"] { width: auto; margin: 0; flex-shrink: 0; }
	.desactive { opacity: .55; cursor: not-allowed; }
	.aide-case { margin: .2rem 0 0 1.6rem; font-size: .8rem; color: var(--color-text-muted); }
</style>
