<!--
  La CARTE D'UN CONTRAT d'entretien — sa ligne de titre, ses actions, son détail
  déplié, et le formulaire qui prend sa place quand on la corrige.

  Extraite de `prestataires/+page.svelte` le 10/09/2026, au fil de l'eau : cet
  écran était à 1 777 lignes et devait accueillir l'édition en place. Le plafond
  de modularité (rang 1) refuse qu'un fichier déjà au-dessus de 500 grossisse, et
  c'est cette carte qui s'en détache le plus proprement — un objet, ses gestes,
  aucun état partagé avec le reste de la page.

  🔴 **La correction s'ouvre DANS LA CARTE, à la place de son corps** — le motif
  des tickets, des annonces et des actualités (`AnnonceCard`, `CarteActualite`),
  désigné à l'écran : *« l'affaire modifiée passe en premier ! prends exemple sur
  tickets »*.

  Quatre positions auront été essayées en une journée, et les trois premières
  déplaçaient quelque chose : la boîte en bas de page, puis en haut, puis à la
  place de la carte ENTIÈRE — cette dernière effaçait la ligne du contrat, et
  `FormulaireCreation` ramenait sa boîte en HAUT de la fenêtre dès qu'elle n'y
  tenait pas. L'objet corrigé quittait donc sa place dans la liste.

  Le motif des tickets ne déplace rien : **l'en-tête reste**, avec son titre et
  ses actions, et seul le CORPS de la carte cède la place au formulaire. Le mode
  se lit sur le crayon (`aria-pressed`, `ux-patterns` §13 bis), et aucune `cle`
  n'est nécessaire — rien n'a bougé, il n'y a rien à ramener à l'écran.

  ⚠️ §14 bis n'est pas remis en cause : c'est toujours LA MÊME BOÎTE — même
  composant, même format. Ce qui changeait était sa position ; elle est désormais
  celle de l'objet, sans que l'objet s'efface.

  🔴 **Le composant existait en DEUX exemplaires** — `AnnonceCard` et
  `CarteActualite` portent tous deux un `formulaireOuvert` qui fait exactement
  cela. Je ne suis pas allé les lire : j'ai inventé une troisième façon, et c'est
  Philippe qui a nommé la première. Chercher la NOTION, pas le nom demandé.
-->
<script lang="ts">
	import { frequenceLabel } from '$lib/prestataires';
	import { fmtDateShort } from '$lib/date';
	import { safeHtml } from '$lib/sanitize';
	import FormulaireCreation from './FormulaireCreation.svelte';
	import ListeDocuments from './ListeDocuments.svelte';
	import FormulaireContrat from './FormulaireContrat.svelte';
	import GesteEnPlace from './GesteEnPlace.svelte';
	import NoteEtoiles from './NoteEtoiles.svelte';

	export let contrat: any;
	export let prest: any = null;
	export let expanded = false;
	export let enRetard = false;
	export let documents: any[] = [];
	export let peutModifier = false;

	/**  Le contrat en cours de correction — `null` quand aucun ne l'est. La carte
	 *   cède sa place au formulaire quand c'est le sien. */
	export let editContratId: number | null = null;
	export let contratForm: any = undefined;
	export let prestataires: any[] = [];
	export let equipements: readonly { val: string; label: string }[] = [];
	export let submitting = false;

	export let onBasculer: (id: number) => void = () => {};
	export let onModifier: (c: any) => void = () => {};
	export let onArchiver: (id: number) => void = () => {};
	export let onSupprimerDoc: (contratId: number, docId: number) => void = () => {};
	export let onAjouteDoc: (contratId: number) => void = () => {};
	export let onAnnuler: () => void = () => {};
	export let onEnregistrer: () => void = () => {};
	/**  Noter le prestataire depuis la carte du contrat — le geste ne vivait
	 *   QUE dans l'onglet Visites retiré (#603), et un affichage sans son geste
	 *   de saisie ne se voit pas. */
	/**  Les notes dépliées — état LOCAL depuis l'extraction (10/09/2026) : il ne
	 *   concerne que cette carte, alors que le `Set` du parent retenait l'état de
	 *   toutes. Une carte qui sait se déplier n'a pas besoin qu'on le lui dise. */
	let notesOuvertes = false;

	export let onNoter: (prestataireId: number, contratId: number) => void = () => {};
	/**  La notation ouverte sur CE contrat — l'état vit dans la page, qui porte
	 *   l'appel réseau ; la carte ne fait que le rendre au bon endroit. */
	export let noteEnCours = false;
	export let noteValeur: number | null = null;
	export let noteCommentaire = '';
	export let noteSaving = false;
	export let onAnnulerNote: () => void = () => {};
	export let onEnregistrerNote: () => void = () => {};

	/**  🔴 Le geste ✨ — MANUEL, et il le reste (11/09/2026, demandé à l'écran :
	 *   « comment on lance l'IA ? cela doit être manuel par une icône »).
	 *
	 *   Rien ne le déclenche seul : ni la création d'un contrat, ni le dépôt d'un
	 *   document, ni une tâche planifiée. Chaque synthèse est facturée, et chacune
	 *   doit être voulue.
	 *
	 *   ⚠️ `contrat.synthese_disponible` vient du SERVEUR : l'écran ne sait pas si
	 *   l'assistant est configuré, et n'a pas à le savoir — cette configuration ne
	 *   regarde pas la session d'un membre du conseil syndical. */
	export let onSynthetiser: (c: any) => void = () => {};
	/** Le contrat dont la synthèse est en cours de rédaction, s'il y en a un. */
	export let syntheseEnCoursId: number | null = null;

	/**  Cette carte est-elle celle qu'on corrige ? Son corps cède alors la place au
	 *   formulaire, et le crayon s'inverse. */
	$: enEdition = editContratId === contrat.id;
</script>

<!--  L'ancre `contrat-{id}` : le carnet d'entretien y renvoie (#870 → carnet,
     10/09/2026), et `test_liens_front` refuse un lien vers une ancre qu'aucun
     onglet ne rend — il a attrapé celui-ci avant la production. -->
<div
	class="carte-liste"
	class:expanded={expanded || enEdition}
	class:urgent={enRetard}
	id="contrat-{contrat.id}"
>
	<!--  Pendant la correction, la ligne de titre ne replie plus : le corps montre
	      le formulaire quoi qu'il arrive, et basculer un état invisible ferait
	      croire à un geste mort. On sort de l'édition par le crayon ou par
	      « Annuler ». -->
	<div
		class="contrat-row"
		role="button"
		tabindex="0"
		on:click|stopPropagation={() => !enEdition && onBasculer(contrat.id)}
		on:keydown|stopPropagation={(e) => e.key === 'Enter' && !enEdition && onBasculer(contrat.id)}
	>
		<div class="contrat-body-inner">
			<strong class="contrat-titre">{contrat.libelle}</strong>
			{#if prest}
				<span class="contrat-meta">— {prest.nom}</span>
			{:else}
				<!--  Un contrat sans intervenant avait sa propre section, qui le
			      rendait une SECONDE fois : le groupement par équipement
			      retombe déjà sur `type_equipement` quand le prestataire
			      manque. Le fait se dit ici, sur la ligne (#603). -->
				<span class="badge badge-gray" style="font-size:.72rem">sans intervenant</span>
			{/if}
			{#if contrat.numero_contrat}<span class="contrat-meta">🔖 {contrat.numero_contrat}</span>{/if}
		</div>
		<div class="contrat-infos">
			{#if contrat.prochaine_visite}
				<div class="contrat-echeance" class:contrat-echeance--retard={enRetard}>
					{enRetard ? '⚠️' : '🗓'}
					{fmtDateShort(contrat.prochaine_visite)}
				</div>
			{:else}
				<div>📅 {fmtDateShort(contrat.date_debut)}</div>
			{/if}
			{#if contrat.frequence_type}
				<span class="badge badge-blue" style="font-size:.75rem">{frequenceLabel(contrat)}</span>
			{/if}
		</div>
		<div class="contrat-meta-right">
			<span class="badge" style="font-size:.8rem">📄 {documents?.length ?? 0}</span>
			<!--  ✨ puis ✏️ puis 🗑️, sur la ligne du titre (`ux-patterns` §3) : du
			      moins destructeur au plus. Proposer un texte l'est moins qu'ouvrir la
			      correction, qui l'est moins qu'archiver. -->
			{#if peutModifier}
				{#if contrat.synthese_disponible}
					<button
						class="btn-icon"
						aria-label="Proposer une synthèse de ce contrat"
						title={syntheseEnCoursId === contrat.id
							? 'Rédaction en cours…'
							: 'Proposer une synthèse'}
						disabled={syntheseEnCoursId !== null}
						on:click|stopPropagation={() => onSynthetiser(contrat)}
						>{syntheseEnCoursId === contrat.id ? '⏳' : '✨'}</button
					>
				{/if}
				<!--  Le mode se lit sur l'icône qui a ouvert le formulaire, jamais sur un
				      titre au-dessus (`ux-patterns` §13 bis) : elle est déjà là, déjà
				      regardée, et son inversion se lit sans être lue. -->
				<button
					class="btn-icon-edit"
					aria-label="Modifier ce contrat"
					title="Modifier"
					aria-pressed={enEdition}
					on:click|stopPropagation={() => (enEdition ? onAnnuler() : onModifier(contrat))}
					>&#x270F;&#xFE0F;</button
				>
				<button
					class="btn-icon-danger"
					aria-label="Archiver"
					title="Archiver"
					on:click|stopPropagation={() => onArchiver(contrat.id)}>🗑️</button
				>
			{/if}
			<span class="toggle-arrow">{expanded || enEdition ? '▲' : '▼'}</span>
		</div>
	</div>
	{#if enEdition}
		<!--  Le corps ne referme pas la carte : sans `stopPropagation`, un clic dans
		      le formulaire remonterait à la ligne de titre et replierait ce qu'on est
		      en train de corriger (`ux-patterns` §3). -->
		<div
			class="contrat-detail-body"
			role="presentation"
			on:click|stopPropagation
			on:keydown|stopPropagation
		>
			<!--  `encadre={false}` : la carte EST le cadre, et sa ligne de titre en est
			      l'en-tête. Une carte dans une carte, c'est deux bordures pour un seul
			      objet (#425). -->
			<FormulaireCreation titre="Modifier le contrat" encadre={false}>
				<FormulaireContrat
					bind:contratForm
					{prestataires}
					{equipements}
					contratId={contrat.id}
					{documents}
					onSupprimer={onSupprimerDoc}
					onAjoute={onAjouteDoc}
					{submitting}
					{onAnnuler}
					{onEnregistrer}
				/>
			</FormulaireCreation>
		</div>
	{:else if expanded}
		<div class="contrat-detail-body">
			<div class="contrat-section">
				<!--  🔴 « Le contrat », comme en édition — et non « Infos contrat ».
					      Signalé le 12/09/2026 : *« la zone en lecture n'a pas les mêmes
					      noms que l'édition »*. C'est R3 du cadre, appliqué entre DEUX
					      RENDUS du même objet : un champ garde son libellé qu'on le lise
					      ou qu'on le corrige. L'intitulé vient de la déclaration
					      (`entites/contrat`, `titreEcran`), pas d'un choix local. -->
				<div class="contrat-section-title">Le contrat</div>
				<div class="detail-grid">
					<div>
						<span class="detail-label">Début</span>📅 {fmtDateShort(contrat.date_debut)}
					</div>
					{#if contrat.duree_initiale_valeur}<div>
							<span class="detail-label">Durée initiale</span>{contrat.duree_initiale_valeur}
							{contrat.duree_initiale_unite}
						</div>{/if}
					{#if contrat.frequence_type}
						<div><span class="detail-label">Fréquence</span>{frequenceLabel(contrat)}</div>
					{/if}
					{#if contrat.prochaine_visite}<div>
							<span class="detail-label">Prochaine visite</span><span
								style="color:var(--color-primary);font-weight:600"
								>🗓 {fmtDateShort(contrat.prochaine_visite)}</span
							>
						</div>{/if}
				</div>
			</div>
			{#if contrat.notes}
				<div class="contrat-section">
					<!--  « Description », comme en édition — c'est le MÊME champ
				      (`contrat.notes`), et il portait deux noms selon qu'on le lisait ou
				      qu'on le corrigeait (signalé le 12/09/2026). Que la synthèse IA
				      atterrisse ici est vrai, mais c'est ce que le champ CONTIENT
				      souvent, pas ce qu'il EST : le nommer par son contenu le rendait
				      introuvable depuis l'écran de saisie. -->
					<div
						class="contrat-section-title clickable"
						role="button"
						tabindex="0"
						on:click|stopPropagation={() => (notesOuvertes = !notesOuvertes)}
						on:keydown|stopPropagation={(e) =>
							(e.key === 'Enter' || e.key === ' ') && (notesOuvertes = !notesOuvertes)}
					>
						Description {notesOuvertes ? '▲' : '▼'}
					</div>
					{#if notesOuvertes}
						<div class="rich-content" style="font-size:.875rem">
							{@html safeHtml(contrat.notes)}
						</div>
					{/if}
				</div>
			{/if}
			<!--  🔴 Les documents sont rendus par `ListeDocuments` — le rendu des
			      tickets, pastilles « PDF: nom », et rien d'autre (12/09/2026).

			      Cette liste était écrite ICI **et** dans `DocumentsContrat`, avec
			      les mêmes styles en ligne au caractère près : une duplication
			      invisible à tout contrôle inter-fichiers, puisque chacune vivait
			      chez elle. Elles auraient divergé à la première retouche — c'est
			      exactement ce qui est arrivé au titre, présent deux fois à
			      l'écran en édition. -->
			<div class="contrat-section">
				<div class="contrat-section-title">Documents ({documents?.length ?? 0})</div>
				<ListeDocuments
					{documents}
					peutSupprimer={peutModifier}
					onSupprimer={(docId) => onSupprimerDoc(contrat.id, docId)}
				/>
			</div>
			{#if peutModifier}
				<div style="display:flex;gap:.4rem;margin-top:.25rem;flex-wrap:wrap">
					<!--  🔴 « Noter » ne vivait QUE dans `CarteVisite`, donc dans le
					      seul onglet Visites : retirer cet onglet sans porter le geste
					      ici aurait rendu la notation d'un prestataire IMPOSSIBLE à
					      saisir, alors que la fiche et le reporting continuaient d'en
					      afficher la moyenne. Un affichage sans son geste de saisie ne
					      se voit pas — rien ne lève, la note reste simplement à jamais
					      celle d'hier (#603).
					      Sans intervenant, il n'y a personne à noter : le bouton
					      n'apparaît pas plutôt que d'ouvrir une modale sans cible. -->
					{#if contrat.prestataire_id}
						<button
							class="btn btn-sm btn-outline contrat-noter"
							aria-pressed={noteEnCours}
							on:click|stopPropagation={() =>
								noteEnCours ? onAnnulerNote() : onNoter(contrat.prestataire_id, contrat.id)}
							>⭐ Noter</button
						>
					{/if}
					<!--  🔴 Le geste s'ouvre DANS la carte (#889) : il était en fenêtre, pour
					      cinq étoiles et un commentaire. Les étoiles viennent de
					      `NoteEtoiles` en mode saisie — saisir et lire une note sont deux
					      rendus du même objet (R3), pas deux composants. -->
					{#if noteEnCours}
						<div role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
							<GesteEnPlace
								enCours={noteSaving}
								onAnnuler={onAnnulerNote}
								onValider={onEnregistrerNote}
							>
								<NoteEtoiles saisie bind:note={noteValeur} />
								<label class="field">
									Commentaire
									<textarea bind:value={noteCommentaire} rows="3"></textarea>
								</label>
							</GesteEnPlace>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	/*  Ces règles ont SUIVI le balisage (10/09/2026). Svelte scope les styles au
	    composant : les laisser dans la page les rendait inertes ici et orphelines
	    là-bas. C'est la régression de #356, et ce sont `lint:css-orphelin` et
	    `lint:classes-nues` qui l'ont refusée — la relecture, elle, ne l'avait pas
	    vue. */
	.contrat-echeance {
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--color-primary);
	}
	.contrat-echeance--retard {
		color: var(--color-danger);
	}
	.contrat-noter {
		color: #f59e0b;
	}
	.contrat-detail-body {
		padding: 0.75rem 1rem 1rem;
		border-top: 1px solid var(--color-border);
		background: var(--color-bg-secondary, #f8f9fa);
	}
	.contrat-section {
		margin-bottom: 1rem;
	}
	.contrat-section:last-child {
		margin-bottom: 0;
	}
	.contrat-section-title {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin-bottom: 0.4rem;
		padding-bottom: 0.25rem;
		border-bottom: 1px solid var(--color-border);
	}
	.contrat-section-title.clickable {
		cursor: pointer;
		user-select: none;
	}
	.contrat-section-title.clickable:hover {
		color: var(--color-primary);
	}
	.contrat-row {
		display: flex;
		gap: 0.75rem;
		align-items: flex-start;
		padding: 0.55rem 0.75rem;
		cursor: pointer;
		transition: background 0.12s;
	}
	.contrat-row:hover {
		background: var(--color-bg-secondary, #f8f9fa);
	}
	.contrat-body-inner {
		flex: 1;
		min-width: 0;
	}
	.contrat-titre {
		font-size: 0.9rem;
	}
	.contrat-meta {
		font-size: 0.78rem;
		color: var(--color-text-muted);
		margin-left: 0.5rem;
	}
	.contrat-infos {
		text-align: right;
		font-size: 0.82rem;
		min-width: 100px;
		flex-shrink: 0;
	}
	.contrat-meta-right {
		display: flex;
		align-items: flex-start;
		gap: 0.3rem;
		flex-shrink: 0;
	}
	.rich-content {
		font-size: 0.85rem;
		line-height: 1.6;
		color: var(--color-text);
		margin-bottom: 0.5rem;
	}
	.rich-content :global(p) {
		margin: 0 0 0.5em;
	}
	.rich-content :global(ul),
	.rich-content :global(ol) {
		padding-left: 1.4em;
		margin: 0 0 0.5em;
	}
	.rich-content :global(strong) {
		font-weight: 600;
	}
	.rich-content :global(em) {
		font-style: italic;
	}
	.contrat-infos {
		min-width: 80px;
	}
</style>
