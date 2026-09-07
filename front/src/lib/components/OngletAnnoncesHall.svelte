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
	import Pastille from '$lib/components/Pastille.svelte';
	import { onMount } from 'svelte';
	import FormulaireAnnonceHall from '$lib/components/FormulaireAnnonceHall.svelte';
	import HistoriqueAnnoncesHall from '$lib/components/HistoriqueAnnoncesHall.svelte';
	import { MAX_PHOTOS_AFFICHE } from '$lib/annonces';
	import { annoncesHall as annoncesHallApi, publications as pubsApi, ApiError } from '$lib/api';
	import type { Publication } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { stripHtml, perimetreDefautListe } from '$lib/utils';
	import { fichiersApi } from '$lib/api';

	//  L'onglet s'amorce SEUL. Avant, la page appelait `loadAnnoncesHall()` et
	//  `loadAhPublications()` à deux endroits (au montage et au clic d'onglet) :
	//  deux appelants pour un seul besoin, et une occasion de plus d'en oublier un.
	onMount(() => {
		loadAhPublications();
	});

	// -- Annonces Hall ------------------------------------------------------
	/** Le composant d'historique, pour lui demander un rechargement. */
	let refHistorique: HistoriqueAnnoncesHall | undefined;
	let ahVue: 'nouvelle' | 'historique' = 'nouvelle';

	// Formulaire de création
	let ahTitre = '';
	let ahMessage = '';
	let ahPerimetre: string[] = perimetreDefautListe();
	let ahFormat: AhFormat = 'auto';
	let ahPhotos: string[] = [];
	let ahEnvoyerCs = false;
	//  Les deux canaux qui manquaient (#480, 01/09/2026). L'écran portait UNE
	//  case, au motif que « WhatsApp et le syndic n'ont pas d'objet ici » —
	//  arbitrage renversé : la Diffusion est un objet du site, elle se rend
	//  partout pareil.
	let ahEnvoyerSyndic = false;
	let ahPartagerWhatsapp = false;
	let ahEnvoyerAuteur = false;
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
			ahPhotos = (src.images ?? []).slice(0, MAX_PHOTOS_AFFICHE);
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

	function ahPayload() {
		return {
			titre: ahTitre.trim(),
			message: ahMessage,
			perimetre_cible: ahPerimetre,
			envoyer_cs: ahEnvoyerCs,
			envoyer_syndic: ahEnvoyerSyndic,
			partager_whatsapp: ahPartagerWhatsapp,
			envoyer_auteur: ahEnvoyerAuteur,
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
		//  🔴 LES CANAUX AUSSI. Ils ne l'étaient pas : après une affiche envoyée au
		//  CS, la case restait cochée, et la suivante partait sans qu'on l'ait
		//  redemandé. C'est l'envoi implicite sous un autre nom — la valeur par
		//  défaut d'un envoi est « ne pas envoyer » (01/09/2026).
		ahEnvoyerCs = false;
		ahEnvoyerSyndic = false;
		ahPartagerWhatsapp = false;
		ahEnvoyerAuteur = false;
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
			await refHistorique?.recharger();
			ahVue = 'historique';
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : "Erreur lors de la création de l'annonce");
		} finally {
			ahSaving = false;
		}
	}
</script>

<div class="ah-panel">
	<div class="perimetre-pills" style="margin-bottom:1rem">
		<Pastille active={ahVue === 'nouvelle'} on:click={() => (ahVue = 'nouvelle')}
			>&#x1F4DD; Nouvelle annonce</Pastille
		>
		<Pastille active={ahVue === 'historique'} on:click={() => (ahVue = 'historique')}
			>&#x1F4C1; Archives</Pastille
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
					maxPhotos={MAX_PHOTOS_AFFICHE}
					bind:envoyerCs={ahEnvoyerCs}
					bind:envoyerSyndic={ahEnvoyerSyndic}
					bind:partagerWhatsapp={ahPartagerWhatsapp}
					bind:envoyerAuteur={ahEnvoyerAuteur}
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
		<!--  L'historique vit dans son propre composant (01/09/2026) : cet onglet
		      portait deux vues sans rapport, et seule la création avait la sienne. -->
		<HistoriqueAnnoncesHall bind:this={refHistorique} />
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

	/*  `.ah-card-badges` et `.ah-card-titre` retirées le 29/08/2026 (#480) :
	    `EnteteCarte` porte désormais les tags et le titre, avec leur mise en
	    forme. Les laisser aurait fait deux vocabulaires pour une seule notion. */

	@media (max-width: 900px) {
		.ah-layout {
			grid-template-columns: 1fr;
		}
		.ah-apercu-frame {
			height: 460px;
		}
	}
</style>
