<!--
  **L'historique des affiches de hall** — la liste, ses archives, et les gestes
  qui s'y appliquent : archiver, renvoyer au CS, télécharger, supprimer.

  Extrait d'`OngletAnnoncesHall` le 01/09/2026, sur refus du contrôle de
  modularité quand l'onglet a reçu les trois canaux de la Diffusion (#480).
  Le refus désignait un **placement** : cet onglet portait deux vues sans rapport
  — un formulaire de création et une liste d'archives —, et seule la première
  avait déjà son composant (`FormulaireAnnonceHall`).

  ⚠️ Il **charge lui-même** sa liste : l'onglet n'a plus à savoir qu'une vue doit
  être amorcée quand on l'ouvre. Après une création, l'hôte appelle `recharger()`
  — c'est le seul lien qui subsiste, et il va dans un seul sens.

  🔴 Les styles voyagent avec le balisage qui les emploie : Svelte scope au
  composant qui rend l'élément, et les laisser chez l'hôte livrerait cette liste
  entièrement NUE (la panne des pastilles de la v2.67.11, refaite deux fois).
-->
<script lang="ts">
	import { onMount } from 'svelte';

	import { annoncesHall as annoncesHallApi, ApiError } from '$lib/api';
	import type { AnnonceHall } from '$lib/api';
	import EnteteCarte from '$lib/components/EnteteCarte.svelte';
	import Pastille from '$lib/components/Pastille.svelte';
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import Vignette from '$lib/components/Vignette.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { fmtDateShort as fmtDate, fmtDatetimeShort as fmtDatetime } from '$lib/date';
	import { safeHtml } from '$lib/sanitize';
	import { isAdmin } from '$lib/stores/auth';

	let ahList: AnnonceHall[] = [];
	let ahLoading = false;
	let ahLoaded = false;
	let ahArchivees = false;
	let ahExpandedId: number | null = null;

	onMount(() => loadAnnoncesHall());

	/** Rechargement demandé par l'hôte — après une création, par exemple. */
	export async function recharger() {
		await loadAnnoncesHall(true);
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
	{#each ahList as annonce (annonce.id)}
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
							&#x2709; {annonce.destinataires.length} destinataire{annonce.destinataires.length > 1
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
							aria-label={annonce.archivee ? 'Restaurer cette annonce' : 'Archiver cette annonce'}
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

<style>
	/*  Les règles suivent le balisage qui les emploie : un style laissé chez
	    l'hôte n'atteint pas un enfant (Svelte scope au composant, v2.67.11). */

	/*  Les règles suivent le balisage qui les emploie : Svelte scope au composant
	    qui rend l'élément, et les laisser chez l'hôte livrerait cette liste NUE.
	    C'est la panne des pastilles de la v2.67.11, refaite deux fois depuis. */
	.ah-card-actions {
		display: flex;
		gap: 0.4rem;
		align-items: center;
		flex-wrap: wrap;
	}
	.ah-card-apercu {
		font-size: 0.82rem;
		color: var(--color-text-muted);
		margin-top: 0.35rem;
	}
	.ah-card-body {
		flex: 1;
		min-width: 0;
	}
	.ah-card-details {
		border-top: 1px solid var(--color-border);
		margin-top: 0.75rem;
		padding-top: 0.75rem;
	}
	.ah-card-meta {
		color: var(--color-text-muted);
		font-size: 0.78rem;
	}
	.ah-card-top {
		display: flex;
		gap: 0.85rem;
		align-items: flex-start;
	}
	.ah-card {
		padding: 0.85rem 1.1rem;
		margin-bottom: 0.5rem;
	}
	.ah-poids {
		font-size: 0.72rem;
		color: var(--color-text-muted);
	}
</style>
