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

<!-- ── Sélection du type (masqué en mode édition) ──────────────────────── -->
{#if !editMode}
	<div style="display:flex;gap:.5rem;margin-bottom:.6rem;flex-wrap:wrap">
		<button type="button" class="pill" class:pill-active={evolType === 'commentaire'}
			on:click={() => (evolType = 'commentaire')}>&#x1F4AC; Commentaire</button>
		{#if statutOptions.length > 0}
			<button type="button" class="pill" class:pill-active={evolType === 'etat'}
				on:click={() => (evolType = 'etat')}>&#x1F504; Changement d'état</button>
		{/if}
	</div>

	<!-- Sélecteur de statut -->
	{#if evolType === 'etat' && statutOptions.length > 0}
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
	<div style="margin-bottom:.6rem;display:flex;flex-wrap:wrap;gap:.75rem">
		<label class="checkbox-field">
			<input type="checkbox" bind:checked={partagerWhatsapp} />
			<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="#25D366"
				style="flex-shrink:0" aria-label="WhatsApp">
				<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51a12.66 12.66 0 0 0-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413Z" />
			</svg>
			<span style="font-size:.82rem">Partager sur le groupe</span>
		</label>
		<label class="checkbox-field">
			<input type="checkbox" bind:checked={envoyerSyndic} />
			<span style="font-size:.82rem">✉️ Envoyer au syndic</span>
		</label>
		<label class="checkbox-field">
			<input type="checkbox" bind:checked={envoyerCs} />
			<span style="font-size:.82rem">✉️ Envoyer au CS</span>
		</label>
	</div>
{/if}

<!-- ── Fichiers (masqués si !showFiles ou si type=etat en mode ajout) ── -->
{#if showFiles && (editMode || evolType === 'commentaire')}
	{#if separatePhotosAndDocs}
		<div style="margin:.4rem 0">
			<label for="evol-photos" style="font-size:.8rem;font-weight:500;color:var(--color-text-muted)">&#x1F4F7; Photos</label>
			<FichiersUpload id="evol-photos" bind:urls={photos} max={5}
				label="Ajouter une photo" accept={ACCEPT_PHOTOS} />
		</div>
		<div style="margin:.4rem 0">
			<label for="evol-docs" style="font-size:.8rem;font-weight:500;color:var(--color-text-muted)">&#x1F4CE; Documents (PDF, Word, Excel)</label>
			<FichiersUpload id="evol-docs" bind:urls={docs} max={5}
				label="Ajouter un document" accept={ACCEPT_DOCUMENTS} />
		</div>
	{:else}
		<div class="field" style="margin-bottom:.6rem">
			<label for="evol-fichiers" style="font-size:.8rem;font-weight:500;color:var(--color-text-muted)">&#x1F4CE; Pièces jointes (photos, PDF, Word, Excel)</label>
			<FichiersUpload id="evol-fichiers" bind:urls={fichiers} max={5}
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
