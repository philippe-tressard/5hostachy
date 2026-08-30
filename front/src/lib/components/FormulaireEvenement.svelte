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
	import WorkflowPastilles from '$lib/components/WorkflowPastilles.svelte';
	import { sectionPresente, type Etat } from '$lib/entites/types';
	import { EVENEMENT } from '$lib/entites/evenement';
	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher<{ annule: void }>();

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
	/**  Corrige-t-on un événement existant, ou en crée-t-on un ? La page le sait
	 *   (`editId`), le formulaire non — il reçoit le même `form` dans les deux cas.
	 *   C'est le seul discriminant du cadre ici : création et édition ne divergent
	 *   sur AUCUNE section (recouvrement de 100 %, mesuré par #432). La prop existe
	 *   pour que ce fait soit **déclaré et vérifié**, et non simplement vrai. */
	export let modeEdition = false;

	/**  🔴 La présence d'une section ne se décide plus ici : elle se lit dans la
	 *   déclaration `EVENEMENT`, via `sectionPresente(EVENEMENT, etat, …)`. Les six
	 *   sections de `ChampsCommuns` étaient posées **en dur** — ce que `lint:etats`
	 *   refuse, mais sans jamais le voir : le contrôle ignore les fichiers qui
	 *   n'importent aucune entité. L'écran n'était pas conforme, il était hors de
	 *   portée du contrôle (#432). */
	$: etat = (modeEdition ? 'edition' : 'creation') as Etat;
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
	{#if sectionPresente(EVENEMENT, etat, 'specifiques')}
		<SectionFormulaire titre="Détails">
			<div class="form-grid">
				<div class="field">
					<label for="ev-type">Type</label>
					<select id="ev-type" bind:value={form.type}>
						{#each types as t (t.val)}<option value={t.val}>{t.label}</option>{/each}
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
						<option value="">— Aucun —</option>
						{#each prestataires.filter((p) => p.actif !== false) as p (p.id)}
							<option value={String(p.id)}>{p.nom}</option>
						{/each}
					</select>
				</div>
				{#if form.prestataire_id && form.type !== 'maintenance_recurrente'}
					<div class="field">
						<label for="ev-frequence">Fréquence (optionnelle)</label>
						<select id="ev-frequence" bind:value={form.frequence_type}>
							<option value="">— Pas de récurrence —</option>
							<option value="fois_par_an">× / an</option>
							<option value="mois">Tous les N mois</option>
							<option value="semaines">Toutes les N semaines</option>
						</select>
					</div>
					{#if form.frequence_type}
						<div class="field">
							<label for="ev-frequence-valeur">Valeur</label>
							<input
								id="ev-frequence-valeur"
								type="number"
								min="1"
								bind:value={form.frequence_valeur}
								placeholder="ex: 2"
							/>
						</div>
					{/if}
				{/if}
			</div>
		</SectionFormulaire>
	{/if}

	<!--  3. Workflow — où en est cet événement.
	      🔴 LE KANBAN *EST* LE WORKFLOW (18/08/2026) : ses colonnes répondent
	      exactement à la question de la section 3 du cadre — « où en est cet
	      objet ? ». La section s'appelait « Suivi Kanban », ce qui nommait
	      l'écran où on le voit plutôt que la notion ; et avant cela elle était
	      rangée dans la DIFFUSION, qui dit qui le voit et non où il en est.
	      Aucun second champ d'état n'a été créé : deux notions de suivi sur le
	      même objet se contredisent au premier écart. -->
	{#if sectionPresente(EVENEMENT, etat, 'workflow')}
		<SectionFormulaire titre="Workflow" idTitre="ev-kanban-titre">
			<div class="field champ-large">
				<!--  🔴 PASTILLES, jamais un `<select>` nu (R3, #423). Norme posée sur
			      Tickets, constatée, puis étendue ici (R5).
			      ⚠️ « Pas de suivi Kanban » est une pastille comme les autres, et elle
			      est active par défaut : l'absence de suivi est un choix qui se voit,
			      pas une option vide en tête d'une liste déroulante. La section n'est
			      donc PAS requise — un événement peut légitimement n'avoir aucun
			      suivi, à la différence de l'état d'un ticket.

			      ⚠️ Le mot « Kanban » est dans le libellé depuis le 19/08/2026,
			      demandé à l'écran. Sans lui, « Pas de suivi » se lisait comme « ce
			      dossier n'est pas suivi » — alors que les six autres pastilles
			      nomment des COLONNES du Kanban, et que l'événement reste évidemment
			      suivi par son fil d'historique. -->
				<WorkflowPastilles
					valeur={form.statut_kanban ?? ''}
					idTitre="ev-kanban-titre"
					options={[
						{ value: '', label: '— Pas de suivi Kanban' },
						...kanbanCols.map((c) => ({ value: c.id, label: c.label })),
					]}
					on:choisir={(e) => (form.statut_kanban = e.detail)}
				/>
			</div>
		</SectionFormulaire>
	{/if}

	<!--  4 à 9 : ordre, intitulés et séparations hérités du composant partagé.
	      Leur PRÉSENCE, elle, se lit dans la déclaration — plus aucune n'est
	      posée en dur (R4). -->
	<ChampsCommuns
		idPrefixe="ev"
		avecPerimetre={sectionPresente(EVENEMENT, etat, 'perimetre')}
		bind:perimetre={formPerimetreCible}
		avecDescription={sectionPresente(EVENEMENT, etat, 'description')}
		bind:description={form.description}
		descriptionPlaceholder="Description de l'événement…"
		avecPhotos={sectionPresente(EVENEMENT, etat, 'photos')}
		bind:photos={photosUrls}
		avecDocuments={sectionPresente(EVENEMENT, etat, 'documents')}
		bind:documents={fichiersUrls}
		avecDiffusion={sectionPresente(EVENEMENT, etat, 'diffusion')}
		bind:whatsapp={form.partager_whatsapp}
		bind:syndic={form.envoyer_syndic}
		bind:cs={form.envoyer_cs}
	>
		<svelte:fragment slot="diffusion">
			<div class="field champ-large">
				<label class="case">
					<input
						type="checkbox"
						bind:checked={form.affichable}
						disabled={form.type === 'maintenance_recurrente'}
					/>
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
						Les maintenances récurrentes restent hors du fil d'activité : elles se suivent dans le
						Kanban.
					</p>
				{/if}
			</div>
		</svelte:fragment>
	</ChampsCommuns>

	<!--  « Annuler » est À CÔTÉ d'« Enregistrer » — norme du 18/08/2026, posée sur
	      Tickets puis étendue. L'en-tête de page ne porte plus de seconde commande
	      d'annulation (#367). -->
	<div class="form-actions">
		<button type="button" class="btn btn-outline" on:click={() => dispatch('annule')}
			>Annuler</button
		>
		<button class="btn btn-primary" disabled={submitting}
			>{submitting ? 'Enregistrement…' : 'Enregistrer'}</button
		>
	</div>
</form>

<style>
	/*  Mêmes règles, même raison que dans `FormulairePrestation` : le balisage
	    part avec ses styles, sinon la grille reste dans la page et le formulaire
	    s'affiche en une colonne écrasée (#344, reproduit le 15/08/2026). */
	.form-grid {
		grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr));
	}
	.form-grid .field {
		margin-bottom: 0;
	}

	/*  Une case et son libellé : ils étaient écrits en `style=` en ligne, avec un
	    `width:auto` posé à la main sur chaque `<input type="checkbox">` pour
	    annuler le `width:100%` des champs de saisie. Nommés ici, ils cessent
	    d'être à réécrire — c'est la même famille de défaut que le sélecteur nu
	    qui a étiré les cases de l'écran Communauté (16/08/2026). */
	.case + .case {
		margin-top: 0.4rem;
	}
	.desactive {
		opacity: 0.55;
		cursor: not-allowed;
	}
	/*  `.aide-case` est passée dans app.css le 17/08/2026 : FormulaireSondage en
	    avait besoin, et Svelte scope les styles — la reprendre ici en aurait fait
	    une seconde définition libre de diverger. */
</style>
