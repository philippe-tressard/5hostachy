<!--
  **L'onglet « Annonces Hall » de l'Espace CS** — création d'une affiche, aperçu
  avant envoi, et archives des affiches déjà produites.

  ## Pourquoi ce composant (#522)

  Extrait de `espace-cs/+page.svelte` quand le garde-fou de modularité a refusé
  que la page grossisse en recevant le bandeau de chargement partiel
  (1 922 → 1 935 lignes). Le refus disait vrai, et depuis longtemps : cette page
  portait **quatre onglets** et n'en avait extrait qu'un (`OngletReporting`).
  C'est la dette nommée par #453 — *« deux pages géantes forcent à contourner le
  garde-fou au lieu de le respecter »*.

  L'onglet était le meilleur candidat : trente-et-un symboles `ah*` qui ne
  servaient qu'à lui, et aucun état partagé avec le reste de la page.

  ## Ce qu'il porte, et ce qu'il ne porte pas

  Il **charge lui-même** ses données au montage : la page n'a plus à savoir
  qu'un onglet doit être amorcé quand on l'ouvre. Le bouton d'onglet ne fait plus
  que changer de vue.

  ⚠️ Le formulaire de création reste dans `FormulaireAnnonceHall` — il était déjà
  extrait, et le cadre #430 en fait l'état « création » de l'entité. Ce composant
  est la RUBRIQUE ; celui-là est le formulaire.

  ## 🔴 Les styles voyagent avec le balisage

  Les trente-six règles `.ah-*` vivaient dans le `<style>` de la page. Svelte
  scope les styles au composant qui rend l'élément : les y laisser aurait livré
  l'onglet entièrement NU en production — la panne des pastilles de la v2.67.11,
  refaite deux fois depuis.
-->
<script lang="ts">
	import EnteteCarte from '$lib/components/EnteteCarte.svelte';
	import Pastille from '$lib/components/Pastille.svelte';
	import { onMount } from 'svelte';
	import FormulaireAnnonceHall from '$lib/components/FormulaireAnnonceHall.svelte';
	import { annoncesHall as annoncesHallApi, publications as pubsApi, ApiError } from '$lib/api';
	import type { AnnonceHall, Publication } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { stripHtml, perimetreDefautListe } from '$lib/utils';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDateShort as fmtDate, fmtDatetimeShort as fmtDatetime } from '$lib/date';
	import { fichiersApi } from '$lib/api';
	import { isAdmin } from '$lib/stores/auth';
	import Vignette from '$lib/components/Vignette.svelte';
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';

	/** Le plafond de fichiers du site — porté par la page, source unique. */
	export let MAX_FICHIERS: number;

	//  L'onglet s'amorce SEUL. Avant, la page appelait `loadAnnoncesHall()` et
	//  `loadAhPublications()` à deux endroits (au montage et au clic d'onglet) :
	//  deux appelants pour un seul besoin, et une occasion de plus d'en oublier un.
	onMount(() => {
		loadAnnoncesHall();
		loadAhPublications();
	});

	// -- Annonces Hall ------------------------------------------------------
	let ahVue: 'nouvelle' | 'historique' = 'nouvelle';
	let ahList: AnnonceHall[] = [];
	let ahLoading = false;
	let ahLoaded = false;
	let ahArchivees = false;
	let ahExpandedId: number | null = null;

	// Formulaire de création
	let ahTitre = '';
	let ahMessage = '';
	let ahPerimetre: string[] = perimetreDefautListe();
	let ahFormat: AhFormat = 'auto';
	let ahPhotos: string[] = [];
	let ahEnvoyerCs = false;
	let ahSaving = false;

	// Aperçu avant envoi
	let ahApercuHtml = '';
	let ahApercuFormat = '';
	let ahApercuLoading = false;

	// Pré-remplissage depuis une actualité
	let ahPubs: Publication[] = [];
	let ahPubsLoaded = false;
	let ahSourceId: number | '' = '';
	const AH_PUBS_MAX = 10;

	type AhFormat = 'auto' | 'a4' | 'a5' | 'a6' | 'a7' | 'a8';
	const AH_FORMATS: { val: AhFormat; label: string }[] = [
		{ val: 'auto', label: 'Auto' },
		{ val: 'a4', label: 'A4' },
		{ val: 'a5', label: 'A5' },
		{ val: 'a6', label: 'A6' },
		{ val: 'a7', label: 'A7' },
		{ val: 'a8', label: 'A8' },
	];

	// Miroir front des seuils serveur (app/utils/annonce_hall.py) — indicatif seulement,
	// le format retenu est toujours celui calculé par l'API.
	//  ⚠️ `ahLongueur` et `ahFormatPrevu` sont partis dans `FormulaireAnnonceHall` :
	//  ce sont des calculs de PRÉSENTATION — combien de caractères, quel format en
	//  résulte — et ils n'ont d'intérêt que pour l'aide affichée sous les pastilles.
	//  La page garde ce qu'elle seule sait : la validité, qui commande son bouton.
	$: ahFormulaireValide =
		ahTitre.trim().length > 0 && stripHtml(ahMessage).length + ahTitre.trim().length > 0;

	/** Les 10 actualités publiées les plus récentes, pour le pré-remplissage. */
	async function loadAhPublications() {
		if (ahPubsLoaded) return;
		try {
			const pubs = await pubsApi.list();
			ahPubs = pubs
				.filter((p) => !p.brouillon)
				.sort((a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime())
				.slice(0, AH_PUBS_MAX);
			ahPubsLoaded = true;
		} catch {
			/* non bloquant : la saisie manuelle reste possible */
		}
	}

	async function ahPrefillDepuisPublication(pubId: number | '') {
		ahSourceId = pubId;
		if (pubId === '') return;
		try {
			// Le serveur résout aussi les photos jointes à l'actualité (documents image).
			const src = await annoncesHallApi.depuisPublication(pubId);
			ahTitre = src.titre;
			ahMessage = src.message;
			ahPerimetre = src.perimetre_cible?.length ? [...src.perimetre_cible] : perimetreDefautListe();
			ahPhotos = (src.images ?? []).slice(0, MAX_FICHIERS);
			ahFormat = 'auto';
			ahApercuHtml = '';
			ahApercuFormat = '';
			const nb = ahPhotos.length;
			toast(
				'info',
				nb > 0
					? `Annonce pré-remplie (${nb} image${nb > 1 ? 's' : ''}) — ajustez avant de valider`
					: 'Annonce pré-remplie — ajustez le texte avant de valider',
			);
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur lors du pré-remplissage');
		}
	}

	async function loadAnnoncesHall(force = false) {
		if (ahLoaded && !force) return;
		ahLoading = true;
		try {
			ahList = await annoncesHallApi.list(ahArchivees);
			ahLoaded = true;
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur de chargement des annonces');
		} finally {
			ahLoading = false;
		}
	}

	function ahPayload() {
		return {
			titre: ahTitre.trim(),
			message: ahMessage,
			perimetre_cible: ahPerimetre,
			envoyer_cs: ahEnvoyerCs,
			format_demande: ahFormat,
			images: ahPhotos,
		};
	}

	function ahResetForm() {
		ahTitre = '';
		ahMessage = '';
		ahPerimetre = perimetreDefautListe();
		ahFormat = 'auto';
		ahPhotos = [];
		ahApercuHtml = '';
		ahApercuFormat = '';
		ahSourceId = '';
	}

	async function ahPrevisualiser() {
		if (!ahFormulaireValide) return;
		ahApercuLoading = true;
		try {
			const r = await annoncesHallApi.previsualiser(ahPayload());
			ahApercuHtml = r.html;
			ahApercuFormat = r.format_label;
		} catch (e) {
			toast(
				'error',
				e instanceof ApiError ? e.message : "Erreur lors de la génération de l'aperçu",
			);
		} finally {
			ahApercuLoading = false;
		}
	}

	async function ahCreer() {
		if (!ahFormulaireValide) return;
		ahSaving = true;
		try {
			const annonce = await annoncesHallApi.create(ahPayload());
			const nb = annonce.destinataires.length;
			toast(
				'success',
				nb > 0
					? `Annonce ${annonce.format_label} créée et envoyée à ${nb} membre${nb > 1 ? 's' : ''} du CS`
					: `Annonce ${annonce.format_label} créée — aucun membre du CS à notifier sur ce périmètre`,
			);
			ahResetForm();
			await loadAnnoncesHall(true);
			ahVue = 'historique';
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : "Erreur lors de la création de l'annonce");
		} finally {
			ahSaving = false;
		}
	}

	async function ahArchiver(annonce: AnnonceHall) {
		try {
			await annoncesHallApi.archiver(annonce.id, !annonce.archivee);
			toast('success', annonce.archivee ? 'Annonce restaurée' : 'Annonce archivée');
			await loadAnnoncesHall(true);
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : "Erreur lors de l'archivage");
		}
	}

	async function ahRenvoyer(annonce: AnnonceHall) {
		try {
			await annoncesHallApi.renvoyerEmail(annonce.id);
			toast('success', 'Annonce renvoyée au CS du périmètre');
			await loadAnnoncesHall(true);
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur lors du renvoi');
		}
	}

	async function ahSupprimer(annonce: AnnonceHall) {
		if (!confirm(`Supprimer définitivement « ${annonce.titre} » ? Le PDF sera effacé.`)) return;
		try {
			await annoncesHallApi.delete(annonce.id);
			toast('success', 'Annonce supprimée');
			await loadAnnoncesHall(true);
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur lors de la suppression');
		}
	}

	function ahPoids(octets: number | null): string {
		if (!octets) return '';
		return octets < 1024 * 1024
			? `${Math.round(octets / 1024)} Ko`
			: `${(octets / (1024 * 1024)).toFixed(1)} Mo`;
	}
</script>

<div class="ah-panel">
	<div class="perimetre-pills" style="margin-bottom:1rem">
		<Pastille active={ahVue === 'nouvelle'} on:click={() => (ahVue = 'nouvelle')}
			>&#x1F4DD; Nouvelle annonce</Pastille
		>
		<Pastille
			active={ahVue === 'historique'}
			on:click={() => {
				ahVue = 'historique';
				loadAnnoncesHall();
			}}>&#x1F4C1; Archives</Pastille
		>
	</div>

	{#if ahVue === 'nouvelle'}
		<!-- ── Création d'une annonce ──────────────────────────────────── -->
		<div class="ah-layout">
			<section class="card ah-form">
				<FormulaireAnnonceHall
					bind:titre={ahTitre}
					bind:message={ahMessage}
					bind:perimetre={ahPerimetre}
					bind:format={ahFormat}
					bind:photos={ahPhotos}
					pubs={ahPubs}
					sourceId={ahSourceId}
					formats={AH_FORMATS}
					maxPhotos={MAX_FICHIERS}
					bind:envoyerCs={ahEnvoyerCs}
					valide={ahFormulaireValide}
					saving={ahSaving}
					apercuLoading={ahApercuLoading}
					onPrefill={ahPrefillDepuisPublication}
					onApercu={ahPrevisualiser}
					onCreer={ahCreer}
					onUpload={async (f) => (await fichiersApi.upload(f)).url}
					onPhotosChange={() => {
						ahApercuHtml = '';
						ahApercuFormat = '';
					}}
				/>
			</section>

			<section class="card ah-apercu">
				<h3 class="ah-apercu-titre">
					Aperçu {#if ahApercuFormat}<span class="badge badge-blue">{ahApercuFormat}</span>{/if}
				</h3>
				{#if ahApercuHtml}
					<div class="ah-apercu-cadre">
						<iframe
							class="ah-apercu-frame"
							title="Aperçu de l'annonce"
							sandbox=""
							srcdoc={ahApercuHtml}
						></iframe>
					</div>
				{:else}
					<div class="empty-state" style="margin:0">
						<p>
							Renseignez le titre et le message, puis cliquez sur <strong>Aperçu</strong> pour voir l'affiche
							telle qu'elle sortira de l'imprimante.
						</p>
					</div>
				{/if}
			</section>
		</div>
	{:else}
		<!-- ── Historique ──────────────────────────────────────────────── -->
		<div class="perimetre-pills" style="margin-bottom:.85rem">
			<Pastille
				active={!ahArchivees}
				on:click={() => {
					ahArchivees = false;
					loadAnnoncesHall(true);
				}}>Annonces</Pastille
			>
			<Pastille
				active={ahArchivees}
				on:click={() => {
					ahArchivees = true;
					loadAnnoncesHall(true);
				}}>Archives</Pastille
			>
		</div>

		{#if ahLoading}
			<p style="color:var(--color-text-muted)">Chargement…</p>
		{:else if ahList.length === 0}
			<div class="empty-state">
				<h3>{ahArchivees ? 'Aucune annonce archivée' : 'Aucune annonce'}</h3>
				<p>
					{ahArchivees
						? "Les annonces archivées depuis l'historique apparaîtront ici."
						: "Créez la première annonce depuis l'onglet « Nouvelle annonce »."}
				</p>
			</div>
		{:else}
			{#each ahList as annonce}
				<!--  🔴 `EnteteCarte` + `Vignette`, la NORME des cartes du site depuis le
					      18/08/2026 (#480). Cette liste recomposait son en-tête à la main —
					      titre après les badges, méta sur sa propre ligne — alors que les cinq
					      autres listes passent par le composant. Deux cartes du même site ne
					      se lisaient pas pareil, et surtout : c'est en recomposant un en-tête
					      que le titre avait disparu sur téléphone.

					      ⚠️ `basculable` : le titre déplie, comme partout ailleurs. Le bouton
					      ▼ reste — il porte l'affordance pour qui ne devine pas qu'un titre
					      clique —, mais il n'est plus le seul chemin. -->
				<div class="card ah-card">
					<div class="ah-card-top">
						<Vignette
							src={annonce.images?.[0] ?? null}
							alt={annonce.titre}
							placeholder={annonce.format_label}
							count={Math.max(0, (annonce.images?.length ?? 0) - 1)}
							title="Format {annonce.format_label}"
						/>
						<div class="ah-card-body">
							<EnteteCarte
								titre={annonce.titre}
								date={fmtDate(annonce.cree_le)}
								basculable
								on:toggle={() => (ahExpandedId = ahExpandedId === annonce.id ? null : annonce.id)}
							>
								<svelte:fragment slot="tags">
									<span class="badge badge-blue">{annonce.format_label}</span>
									<span class="badge badge-gray">&#x1F539; {annonce.perimetre_label}</span>
									{#if annonce.publication_id}<span
											class="badge badge-gray"
											title="Générée depuis une actualité">&#x1F4F0; Actualité</span
										>{/if}
									{#if annonce.archivee}<span class="badge badge-gray">Archivée</span>{/if}
								</svelte:fragment>
								<svelte:fragment slot="actions">
									<a
										class="btn btn-sm btn-outline"
										href={annoncesHallApi.pdfUrl(annonce.id)}
										target="_blank"
										rel="noopener"
									>
										&#x1F4C4; PDF{#if annonce.taille_octets}
											<span class="ah-poids">{ahPoids(annonce.taille_octets)}</span>{/if}
									</a>
									<button
										class="btn btn-sm btn-outline"
										aria-label={ahExpandedId === annonce.id ? 'Replier' : 'Déplier'}
										on:click|stopPropagation={() =>
											(ahExpandedId = ahExpandedId === annonce.id ? null : annonce.id)}
									>
										{ahExpandedId === annonce.id ? '▲' : '▼'}
									</button>
								</svelte:fragment>
							</EnteteCarte>
							<!--  La méta reste SOUS l'en-tête : elle porte l'envoi, qui n'est ni
								      un tag ni une date de création. -->
							<small class="ah-card-meta">
								{#if annonce.auteur_nom}{annonce.auteur_nom} ·
								{/if}
								{#if annonce.destinataires.length}
									&#x2709; {annonce.destinataires.length} destinataire{annonce.destinataires
										.length > 1
										? 's'
										: ''}
								{:else}
									<span style="color:var(--color-warning,#B07D1E)">non envoyée</span>
								{/if}
							</small>
							<p class="ah-card-apercu clamp-5">{annonce.apercu}</p>
						</div>
					</div>

					{#if ahExpandedId === annonce.id}
						<div class="ah-card-details">
							<div class="rich-content" style="font-size:.88rem">
								{@html safeHtml(annonce.message)}
							</div>
							{#if annonce.images?.length}
								<div style="margin-top:.6rem">
									<FichiersUpload urls={annonce.images} readonly size={64} />
								</div>
							{/if}
							{#if annonce.destinataires.length}
								<p class="ah-card-meta" style="margin-top:.6rem">
									Envoyée le {fmtDatetime(annonce.envoye_le ?? annonce.cree_le)} à
									{annonce.destinataires.join(', ')}
								</p>
							{/if}
							<div class="ah-card-actions" style="margin-top:.75rem">
								<button class="btn btn-sm btn-outline" on:click={() => ahRenvoyer(annonce)}>
									&#x2709; Renvoyer au CS
								</button>
								<button
									class="btn-icon-warn"
									title={annonce.archivee ? 'Restaurer' : 'Archiver'}
									aria-label={annonce.archivee
										? 'Restaurer cette annonce'
										: 'Archiver cette annonce'}
									on:click={() => ahArchiver(annonce)}
								>
									{annonce.archivee ? '↩️' : '\u{1F4E6}'}
								</button>
								{#if $isAdmin && annonce.archivee}
									<button
										class="btn-icon-danger"
										title="Supprimer définitivement"
										aria-label="Supprimer définitivement cette annonce"
										on:click={() => ahSupprimer(annonce)}>&#x1F5D1;&#xFE0F;</button
									>
								{/if}
							</div>
						</div>
					{/if}
				</div>
			{/each}
		{/if}
	{/if}
</div>

<style>
	.ah-panel {
		display: flex;
		flex-direction: column;
	}
	.ah-layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 1rem;
		align-items: start;
	}
	.ah-form {
		padding: 1rem 1.1rem;
	}
	/*  `.ah-form label` et `.ah-form input` sont partis avec le formulaire, dans
	    `FormulaireAnnonceHall` — un style n'atteint pas le balisage d'un enfant. */
	.ah-apercu {
		padding: 1rem 1.1rem;
	}
	.ah-apercu-titre {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.95rem;
		font-weight: 600;
		margin-bottom: 0.75rem;
	}
	.ah-apercu-cadre {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
		background: #fff;
	}
	.ah-apercu-frame {
		width: 100%;
		height: 640px;
		border: none;
		display: block;
	}

	.ah-card {
		padding: 0.85rem 1.1rem;
		margin-bottom: 0.5rem;
	}
	.ah-card-top {
		display: flex;
		gap: 0.85rem;
		align-items: flex-start;
	}
	.ah-card-body {
		flex: 1;
		min-width: 0;
	}
	/*  `.ah-card-badges` et `.ah-card-titre` retirées le 29/08/2026 (#480) :
	    `EnteteCarte` porte désormais les tags et le titre, avec leur mise en
	    forme. Les laisser aurait fait deux vocabulaires pour une seule notion. */
	.ah-card-meta {
		color: var(--color-text-muted);
		font-size: 0.78rem;
	}
	.ah-card-apercu {
		font-size: 0.82rem;
		color: var(--color-text-muted);
		margin-top: 0.35rem;
	}
	.ah-card-actions {
		display: flex;
		gap: 0.4rem;
		align-items: center;
		flex-wrap: wrap;
	}
	.ah-poids {
		font-size: 0.72rem;
		color: var(--color-text-muted);
	}
	.ah-card-details {
		border-top: 1px solid var(--color-border);
		margin-top: 0.75rem;
		padding-top: 0.75rem;
	}

	@media (max-width: 900px) {
		.ah-layout {
			grid-template-columns: 1fr;
		}
		.ah-apercu-frame {
			height: 460px;
		}
	}
</style>
