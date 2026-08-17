<!--
  EvolForm.svelte — Formulaire partagé d'ajout/édition d'évolution
  Utilisé par : tickets/[id], actualites, espace-cs

  Props clés :
    statutOptions      – liste des options de statut disponibles
    statutLabels       – map value→label pour afficher le statut actuel
    currentStatut      – statut actuel de l'item parent
    showNotifs         – afficher les cases WhatsApp/syndic/CS
    showEmail          – afficher le champ email externe
    showFiles          – afficher l'upload de fichiers
    separatePhotosAndDocs – true=tickets (photos + docs séparés), false=publications (fichiers unifiés)
    editMode           – masque le type/statut, pré-remplit contenu+fichiers
    initialContenu     – contenu initial (mode édition)
    initialFichiers    – fichiers initiaux (mode édition)
    saving             – contrôlé par le parent (en cours de sauvegarde API)

  Événements :
    submit(data)  – {type, contenu, nouveau_statut?, fichiers_urls, partager_whatsapp?, envoyer_syndic?, envoyer_cs?, email_externe?}
    cancel        – fermer le formulaire sans sauvegarder
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import CanauxNotification from '$lib/components/CanauxNotification.svelte';
	import { ACCEPT_DOCUMENTS, ACCEPT_FICHIERS, ACCEPT_PHOTOS, estImage } from '$lib/fichiers';

	// ── Props ─────────────────────────────────────────────────────────────────
	/** Options affichées dans le select "Nouvel état" */
	export let statutOptions: { value: string; label: string }[] = [];
	/** Map value→label pour afficher le statut actuel */
	export let statutLabels: Record<string, string> = {};
	/** Statut actuel de l'objet parent (affiché sous le label) */
	export let currentStatut = '';
	/** Afficher les cases de partage (WhatsApp / syndic / CS) */
	export let showNotifs = false;
	/** Valeurs par défaut des notifications */
	export let defaultPartagerWhatsapp = false;
	export let defaultEnvoyerSyndic = false;
	export let defaultEnvoyerCs = false;
	/** Afficher le champ email externe */
	export let showEmail = false;
	/** Afficher l'upload de fichiers */
	export let showFiles = false;
	/** true = tickets (photos séparées des docs), false = publications (fichiers unifiés) */
	export let separatePhotosAndDocs = false;
	/** Mode édition : masque type/statut, pré-remplit contenu+fichiers */
	export let editMode = false;
	/** Contenu initial (mode édition) */
	export let initialContenu = '';
	/** Fichiers initiaux (mode édition) */
	export let initialFichiers: { url: string; nom: string; type?: string }[] = [];
	/** Contrôlé par le parent : est-ce que la sauvegarde API est en cours */
	export let saving = false;

	// ── Events ────────────────────────────────────────────────────────────────
	const dispatch = createEventDispatcher<{
		submit: {
			type: 'commentaire' | 'etat';
			contenu: string;
			nouveau_statut?: string;
			fichiers_urls: string[];
			partager_whatsapp?: boolean;
			envoyer_syndic?: boolean;
			envoyer_cs?: boolean;
			email_externe?: string;
		};
		cancel: void;
	}>();

	// ── State ─────────────────────────────────────────────────────────────────
	let evolType: 'commentaire' | 'etat' = 'commentaire';
	let contenu = initialContenu;
	let nouveauStatut = '';
	let partagerWhatsapp = defaultPartagerWhatsapp;
	let envoyerSyndic = defaultEnvoyerSyndic;
	let envoyerCs = defaultEnvoyerCs;
	let emailExterne = '';

	// Fichiers séparés (separatePhotosAndDocs = true — mode ticket)
	let photos: string[] = editMode && separatePhotosAndDocs
		? initialFichiers.filter(f => estImage(f.url)).map(f => f.url)
		: [];
	let docs: string[] = editMode && separatePhotosAndDocs
		? initialFichiers.filter(f => !estImage(f.url)).map(f => f.url)
		: [];

	// Fichiers unifiés (separatePhotosAndDocs = false — mode publication / espace-cs)
	let fichiers: string[] =
		editMode && !separatePhotosAndDocs ? initialFichiers.map(f => f.url) : [];

	// ── Helpers ───────────────────────────────────────────────────────────────
	const richEmpty = (html: string) => !html || html.replace(/<[^>]+>/g, '').trim() === '';

	$: allFichiersUrls = separatePhotosAndDocs ? [...photos, ...docs] : fichiers;

	$: canSubmit = !saving && (
		editMode
			? !(richEmpty(contenu) && allFichiersUrls.length === 0)
			: evolType === 'etat'
				? !!nouveauStatut
				: !(richEmpty(contenu) && (!showFiles || allFichiersUrls.length === 0))
	);

	// Le téléversement lui-même vit dans `FichiersUpload` : trois copies de la
	// même fonction (photo, document, fichier unifié) ne différaient que par la
	// liste alimentée.

	// ── Submit ────────────────────────────────────────────────────────────────
	function handleSubmit() {
		if (!canSubmit) return;
		dispatch('submit', {
			type: editMode ? 'commentaire' : evolType,
			contenu,
			nouveau_statut: (!editMode && evolType === 'etat') ? nouveauStatut : undefined,
			fichiers_urls: allFichiersUrls,
			partager_whatsapp: showNotifs ? partagerWhatsapp : undefined,
			envoyer_syndic: showNotifs ? envoyerSyndic : undefined,
			envoyer_cs: showNotifs ? envoyerCs : undefined,
			email_externe: showEmail ? (emailExterne.trim() || undefined) : undefined,
		});
	}
</script>

<!-- ── Sélection du type (masquée en mode édition, et quand il n'y a rien à
     choisir : sans option d'état, la rangée se réduisait à une pastille unique,
     active et sans alternative — un choix à un seul choix. C'est le cas de la
     fiche d'un ticket depuis #415, où le changement d'état a ses boutons.) ── -->
{#if !editMode && statutOptions.length > 0}
	<div style="display:flex;gap:.5rem;margin-bottom:.6rem;flex-wrap:wrap">
		<button type="button" class="pill" class:pill-active={evolType === 'commentaire'}
			on:click={() => (evolType = 'commentaire')}>&#x1F4AC; Commentaire</button>
		<button type="button" class="pill" class:pill-active={evolType === 'etat'}
			on:click={() => (evolType = 'etat')}>&#x1F504; Changement d'état</button>
	</div>

	<!-- Sélecteur de statut -->
	{#if evolType === 'etat'}
		<div class="field" style="margin-bottom:.6rem">
			<label for="evol-statut">Nouvel état *</label>
			{#if currentStatut}
				<div style="font-size:.8rem;color:var(--color-text-muted);margin-bottom:.35rem">
					État actuel : <strong>{statutLabels[currentStatut] || currentStatut}</strong>
				</div>
			{/if}
			<select id="evol-statut" bind:value={nouveauStatut}>
				<option value="">— Choisir —</option>
				{#each statutOptions as opt}
					<option value={opt.value}>{opt.label}</option>
				{/each}
			</select>
		</div>
	{/if}
{/if}

<!-- ── Contenu RichEditor ─────────────────────────────────────────────── -->
<div class="field" style="margin-bottom:.6rem">
	<label>
		{#if editMode}
			Contenu
		{:else if evolType === 'etat'}
			Commentaire <span style="font-weight:normal;color:var(--color-text-muted)">(optionnel)</span>
		{:else}
			Commentaire *
		{/if}
	</label>
	<RichEditor bind:value={contenu}
		placeholder={editMode
			? 'Modifier le commentaire…'
			: evolType === 'etat'
				? 'Précisions sur ce changement…'
				: 'Ajoutez un commentaire de suivi…'}
		minHeight="90px" />
</div>

<!-- ── Notifications (WhatsApp / syndic / CS) ────────────────────────── -->
{#if showNotifs}
	<CanauxNotification
		bind:whatsapp={partagerWhatsapp}
		bind:syndic={envoyerSyndic}
		bind:cs={envoyerCs}
		compact
	/>
{/if}

<!-- ── Fichiers (masqués si !showFiles ou si type=etat en mode ajout) ── -->
{#if showFiles && (editMode || evolType === 'commentaire')}
	{#if separatePhotosAndDocs}
		<div style="margin:.4rem 0">
			<FichiersUpload id="evol-photos" bind:urls={photos}
				label="Ajouter une photo" accept={ACCEPT_PHOTOS} />
		</div>
		<div style="margin:.4rem 0">
			<FichiersUpload id="evol-docs" bind:urls={docs}
				label="Ajouter un document" accept={ACCEPT_DOCUMENTS} />
		</div>
	{:else}
		<div class="field" style="margin-bottom:.6rem">
			<FichiersUpload id="evol-fichiers" bind:urls={fichiers}
				label="Ajouter un fichier" accept={ACCEPT_FICHIERS} />
			{#if partagerWhatsapp && fichiers.length > 0}
				<div style="font-size:.75rem;color:var(--color-text-muted);margin-top:.3rem">
					⚠️ Les fichiers ne sont pas envoyés via WhatsApp, uniquement le texte.
				</div>
			{/if}
		</div>
	{/if}
{/if}

<!-- ── Email externe ─────────────────────────────────────────────────── -->
{#if showEmail}
	<div style="margin:.4rem 0 .6rem">
		<label for="evol-email-ext" style="font-size:.8rem;font-weight:500;color:var(--color-text-muted)">
			📧 Notifier une adresse email externe <span style="font-weight:normal">(optionnel)</span>
		</label>
		<input id="evol-email-ext" type="email" bind:value={emailExterne}
			placeholder="contact@exemple.fr"
			style="padding:.35rem .6rem;border:1px solid var(--color-border);border-radius:6px;font-size:.85rem;width:100%;max-width:320px;margin-top:.25rem;display:block" />
	</div>
{/if}

<!-- ── Actions ────────────────────────────────────────────────────────── -->
<div style="display:flex;justify-content:flex-end;gap:.5rem;margin-top:.5rem">
	<button type="button" class="btn btn-outline btn-sm" on:click={() => dispatch('cancel')}>Annuler</button>
	<button type="button" class="btn btn-primary btn-sm" disabled={!canSubmit} on:click={handleSubmit}>
		{saving ? (editMode ? 'Enregistrement…' : 'Envoi…') : (editMode ? 'Enregistrer' : 'Valider')}
	</button>
</div>
