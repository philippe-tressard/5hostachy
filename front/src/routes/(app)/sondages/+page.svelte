<script lang="ts">
import EntetePage from '$lib/components/EntetePage.svelte';
import Reponses from '$lib/components/Reponses.svelte';
import FichiersUpload from '$lib/components/FichiersUpload.svelte';
import AnnonceCard from '$lib/components/AnnonceCard.svelte';
import { CATEGORIES_ANNONCE, TYPES_ANNONCE } from '$lib/annonces';
import { onMount } from 'svelte';
import { goto } from '$app/navigation';
import { api, sondages as sondagesApi, idees as ideesApi, annonces as annoncesApi, signalements as signalementsApi, ApiError } from '$lib/api';
import { isCS, isAdmin, currentUser } from '$lib/stores/auth';
import RichEditor from '$lib/components/RichEditor.svelte';
import CanauxNotification from '$lib/components/CanauxNotification.svelte';
import { toast } from '$lib/components/Toast.svelte';
import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
import { safeHtml } from '$lib/sanitize';
import { fmtDateShort, isNouveau } from '$lib/date';
import { trackTabView } from '$lib/telemetry';
import { cibleDuHash, ongletDeLUrl, revelerCible } from '$lib/deepLink';

$: _pc = getPageConfig($configStore, 'communaute', { titre: 'Communauté', navLabel: 'Communauté', icone: 'users-round', descriptif: 'Sondages, boîte à idées et petites annonces entre résidents.', onglets: { sondages: { label: '\u{1F4CA} Sondages', descriptif: 'Participez aux votes et consultations de la copropriété.' }, idees: { label: '\u{1F4A1} Boîte à idées', descriptif: 'Proposez et soutenez des idées pour améliorer la vie en résidence.' }, annonces: { label: '\u{1F3F7}\uFE0F Petites annonces', descriptif: 'Achetez, vendez ou donnez des objets entre résidents.' } } });
$: _siteNom = $siteNomStore;

// Liste explicite : elle sert aussi à valider le `?onglet=` d'un lien profond
// (fil d'activité, notification) — cf. $lib/deepLink.ts.
const ONGLETS = ['sondages', 'idees', 'annonces'] as const;
type Tab = (typeof ONGLETS)[number];
let activeTab: Tab = 'sondages';
$: trackTabView(activeTab);

// Bâtiments disponibles pour le ciblage
let batimentsList: { id: number; numero: string }[] = [];

// Profils disponibles
const PROFILS = [
	{ val: 'copropriétaire_résident', label: 'Copropriétaire résident' },
	{ val: 'copropriétaire_bailleur', label: 'Copropriétaire bailleur' },
	{ val: 'locataire', label: 'Locataire' },
];

// Ban communauté
let banMessage = '';

// Sondages
let sondages: any[] = [];
let sondagesLoading = true;
let showFormSondage = false;
let submittingSondage = false;
type OptionForm = { libelle: string; champ_libre: boolean };
let formSondage = {
	question: '',
	description: '',
	cloture_le: '',
	resultats_publics: true,
	options: [{ libelle: '', champ_libre: false }, { libelle: '', champ_libre: false }] as OptionForm[],
	partager_whatsapp: false,
	envoyer_syndic: false,
	envoyer_cs: false,
};

// Ciblage
let selectedProfils: string[] = [];   // vide = tous
let selectedBatiments: number[] = []; // vide = toute la résidence
$: tousProfils = selectedProfils.length === 0;
$: tousBatiments = selectedBatiments.length === 0;

function toggleProfil(val: string) {
	selectedProfils = selectedProfils.includes(val)
		? selectedProfils.filter(p => p !== val)
		: [...selectedProfils, val];
}
function toggleBatiment(id: number) {
	selectedBatiments = selectedBatiments.includes(id)
		? selectedBatiments.filter(b => b !== id)
		: [...selectedBatiments, id];
}

function addOption() { formSondage.options = [...formSondage.options, { libelle: '', champ_libre: false }]; }
function removeOption(i: number) { formSondage.options = formSondage.options.filter((_, idx) => idx !== i); }
function moveOptionUp(i: number) {
	if (i === 0) return;
	const arr = [...formSondage.options];
	[arr[i - 1], arr[i]] = [arr[i], arr[i - 1]];
	formSondage.options = arr;
}
function moveOptionDown(i: number) {
	if (i === formSondage.options.length - 1) return;
	const arr = [...formSondage.options];
	[arr[i], arr[i + 1]] = [arr[i + 1], arr[i]];
	formSondage.options = arr;
}

async function creerSondage() {
	const opts = formSondage.options.map((o, i) => ({ libelle: o.libelle, ordre: i, champ_libre: o.champ_libre })).filter(o => o.libelle.trim());
	if (!formSondage.question || opts.length < 2) { toast('error', 'Question et au moins 2 options requises'); return; }
	submittingSondage = true;
	try {
		await sondagesApi.create({
			question: formSondage.question,
			description: formSondage.description || undefined,
			cloture_le: formSondage.cloture_le ? new Date(formSondage.cloture_le).toISOString() : undefined,
			resultats_publics: formSondage.resultats_publics,
			options: opts,
			profils_autorises: selectedProfils.length > 0 ? selectedProfils : null,
			batiments_ids: selectedBatiments.length > 0 ? selectedBatiments : null,
			partager_whatsapp: formSondage.partager_whatsapp,
			envoyer_syndic: formSondage.envoyer_syndic,
			envoyer_cs: formSondage.envoyer_cs,
		});
		sondages = await sondagesApi.list();
		showFormSondage = false;
		formSondage = {
			question: '',
			description: '',
			cloture_le: '',
			resultats_publics: true,
			options: [{ libelle: '', champ_libre: false }, { libelle: '', champ_libre: false }],
			partager_whatsapp: false,
			envoyer_syndic: false,
			envoyer_cs: false,
		};
		selectedProfils = [];
		selectedBatiments = [];
		toast('success', 'Sondage créé');
	} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
	finally { submittingSondage = false; }
}

function estCloture(s: any) { return s.cloture_forcee || (s.cloture_le && new Date(s.cloture_le) < new Date()); }

async function arreterSondage(s: any, e: Event) {
	e.preventDefault();
	if (!confirm(`Stopper le sondage "${s.question}" maintenant ?`)) return;
	try {
		await sondagesApi.cloturer(s.id);
		sondages = sondages.map(x => x.id === s.id ? { ...x, cloture_forcee: true } : x);
		toast('success', 'Sondage stoppé');
	} catch (err) { toast('error', err instanceof ApiError ? err.message : 'Erreur'); }
}

async function supprimerSondage(s: any, e: Event) {
	e.preventDefault();
	if (!confirm(`Supprimer définitivement le sondage "${s.question}" ?`)) return;
	try {
		await sondagesApi.supprimer(s.id);
		sondages = sondages.filter(x => x.id !== s.id);
		toast('success', 'Sondage supprimé');
	} catch (err) { toast('error', err instanceof ApiError ? err.message : 'Erreur'); }
}

// Idées
let idees: any[] = [];
let ideesLoading = true;
let showFormIdee = false;
let submittingIdee = false;
let formIdee = { titre: '', description: '' };
let filtreStatut = '';

// Annonces
let annonces: any[] = [];
let annoncesLoading = true;
let showFormAnnonce = false;
let submittingAnnonce = false;
let formAnnonce = { titre: '', description: '', type_annonce: 'vente', categorie: 'divers', prix: '', negotiable: false, contact_visible: true };
let filtreTypeAnnonce = '';
let filtreCatAnnonce = '';
let filtreTriAnnonce = 'recent';
let expandedAnnonce: number | null = null;
/** Annonce dont l'auteur a demandé à GÉRER les photos — voir le bloc de rendu. */
let gestionPhotos: number | null = null;
$: filteredAnnonces = annonces
	.filter(a => !filtreTypeAnnonce || a.type_annonce === filtreTypeAnnonce)
	.filter(a => !filtreCatAnnonce || a.categorie === filtreCatAnnonce);
$: sortedAnnonces = [...filteredAnnonces].sort((a, b) => {
	if (filtreTriAnnonce === 'prix_asc') return (a.prix ?? 999999) - (b.prix ?? 999999);
	if (filtreTriAnnonce === 'prix_desc') return (b.prix ?? 0) - (a.prix ?? 0);
	return new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime();
});


async function creerAnnonce() {
	if (!formAnnonce.titre || !formAnnonce.description) { toast('error', 'Titre et description obligatoires'); return; }
	submittingAnnonce = true;
	try {
		const created: any = await annoncesApi.create({
			titre: formAnnonce.titre,
			description: formAnnonce.description,
			type_annonce: formAnnonce.type_annonce,
			categorie: formAnnonce.categorie,
			prix: formAnnonce.prix ? parseFloat(formAnnonce.prix) : null,
			negotiable: formAnnonce.negotiable,
			contact_visible: formAnnonce.contact_visible,
		});
		annonces = [created, ...annonces];
		showFormAnnonce = false;
		formAnnonce = { titre: '', description: '', type_annonce: 'vente', categorie: 'divers', prix: '', negotiable: false, contact_visible: true };
		expandedAnnonce = created.id;
		toast('success', 'Annonce publiée !');
	} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
	finally { submittingAnnonce = false; }
}

/** Téléverse une photo et retourne son URL (contrat attendu par FichiersUpload). */
async function uploadPhotoAnnonce(id: number, file: File): Promise<string> {
	const res: any = await annoncesApi.uploadPhoto(id, file);
	annonces = annonces.map(a => a.id === id ? { ...a, photos: res.photos } : a);
	return res.url;
}

/** Supprime une photo et retourne la liste à jour (contrat attendu par FichiersUpload). */
async function supprimerPhotoAnnonce(id: number, url: string): Promise<string[]> {
	const res: any = await annoncesApi.deletePhoto(id, url);
	annonces = annonces.map(a => a.id === id ? { ...a, photos: res.photos } : a);
	return res.photos;
}

async function changeStatutAnnonce(id: number, statut: string) {
	try {
		await annoncesApi.updateStatut(id, statut);
		if (statut === 'archive') {
			annonces = annonces.filter(a => a.id !== id);
		} else {
			annonces = annonces.map(a => a.id === id ? { ...a, statut } : a);
		}
		toast('success', 'Statut mis à jour');
	} catch { toast('error', 'Erreur'); }
}

async function supprimerAnnonce(id: number) {
	if (!confirm('Supprimer définitivement cette annonce ?')) return;
	try {
		await annoncesApi.supprimer(id);
		annonces = annonces.filter(a => a.id !== id);
		toast('success', 'Annonce supprimée');
	} catch { toast('error', 'Erreur'); }
}

const statuts = [
{ val: '', label: 'Toutes' },
		{ val: 'ouverte', label: '\u{1F4A1} Ouverte' },
		{ val: 'retenue', label: '✅ Retenue' },
		{ val: 'realisee', label: '\u{1F389} Réalisée' },
		{ val: 'rejetee', label: '❌ Rejetée' },
];
function statutClass(s: string) {
return { ouverte: 'badge-blue', retenue: 'badge-green', realisee: 'badge-purple', rejetee: 'badge-gray' }[s] ?? 'badge-gray';
}

$: filteredIdees = filtreStatut ? idees.filter(i => i.statut === filtreStatut) : idees;
$: sortedIdees = [...filteredIdees].sort((a, b) => b.nb_votes - a.nb_votes);

async function creerIdee() {
if (!formIdee.titre || !formIdee.description) { toast('error', 'Titre et description obligatoires'); return; }
submittingIdee = true;
try {
await ideesApi.create(formIdee);
idees = await ideesApi.list();
showFormIdee = false;
formIdee = { titre: '', description: '' };
toast('success', 'Idée soumise !');
} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
finally { submittingIdee = false; }
}

async function voter(id: number) {
try {
const res: any = await ideesApi.voter(id);
idees = await ideesApi.list();
toast('success', res.message ?? 'Vote enregistré');
} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
}

async function changeStatut(id: number, statut: string) {
try {
await ideesApi.updateStatut(id, statut);
idees = idees.map(i => i.id === id ? { ...i, statut } : i);
toast('success', 'Statut mis à jour');
} catch { toast('error', 'Erreur'); }
}

async function deleteIdee(id: number) {
if (!confirm('Supprimer cette idée définitivement ?')) return;
try {
await ideesApi.delete(id);
idees = idees.filter(i => i.id !== id);
toast('success', 'Idée supprimée');
} catch { toast('error', 'Erreur lors de la suppression'); }
}

// ── Réponses (idées + annonces) — composant partagé Reponses.svelte ──────────
async function repondreIdee(id: number, contenu: string) {
try {
await ideesApi.repondre(id, contenu);
idees = await ideesApi.list();
toast('success', 'Réponse publiée');
} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); throw e; }
}

async function supprimerReponseIdee(ideeId: number, repId: number) {
try {
await ideesApi.supprimerReponse(ideeId, repId);
idees = await ideesApi.list();
toast('success', 'Réponse supprimée');
} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
}

async function repondreAnnonce(id: number, contenu: string) {
try {
await annoncesApi.repondre(id, contenu);
annonces = await annoncesApi.list();
toast('success', 'Réponse publiée');
} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); throw e; }
}

async function supprimerReponseAnnonce(annonceId: number, repId: number) {
try {
await annoncesApi.supprimerReponse(annonceId, repId);
annonces = await annoncesApi.list();
toast('success', 'Réponse supprimée');
} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
}

// ── Signalements / modération ────────────────────────────────────────────────
let signalements: any[] = [];
let showModeration = false;

async function chargerSignalements() {
if (!$isCS) return;
try { signalements = await signalementsApi.liste('en_attente'); }
catch { /* silencieux */ }
}

async function signaler(cibleType: string, cibleId: number) {
const motif = prompt('Pourquoi signalez-vous ce contenu au conseil syndical ?');
if (motif === null) return;
if (!motif.trim()) { toast('error', 'Le motif est obligatoire'); return; }
try {
await signalementsApi.creer(cibleType, cibleId, motif.trim());
toast('success', 'Signalement transmis au conseil syndical');
if ($isCS) chargerSignalements();
} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
}

async function resoudreSignalement(id: number, statut: 'traite' | 'rejete') {
try {
await signalementsApi.resoudre(id, statut);
signalements = signalements.filter(s => s.id !== id);
toast('success', statut === 'traite' ? 'Signalement traité' : 'Signalement ignoré');
} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
}

// Garde réactive : redirige dès que le user est connu (garde contre la race condition async layout)
$: if ($currentUser && ($currentUser.statut === 'syndic' || $currentUser.statut === 'mandataire')) {
	toast('error', 'La rubrique Communauté n\'est pas accessible à votre profil.');
	goto('/tableau-de-bord', { replaceState: true });
}

onMount(async () => {
if ($currentUser?.communaute_interdit) {
	banMessage = 'Votre accès à la Communauté a été définitivement suspendu.';
	sondagesLoading = false; ideesLoading = false; annoncesLoading = false;
	return;
}
if ($currentUser?.communaute_ban_jusqu_au && new Date($currentUser.communaute_ban_jusqu_au) > new Date()) {
	banMessage = 'Votre accès à la Communauté est suspendu pour une période probatoire d\u2019un mois. À la 2ᵉ infraction, vous serez banni définitivement.';
	sondagesLoading = false; ideesLoading = false; annoncesLoading = false;
	return;
}
[[sondages, idees, annonces], batimentsList] = await Promise.all([
	Promise.all([
		sondagesApi.list().catch(() => []),
		ideesApi.list().catch(() => []),
		annoncesApi.list().catch(() => []),
	]),
	api.get<{ id: number; numero: string }[]>('/auth/batiments').catch(() => []),
]);
sondagesLoading = false;
ideesLoading = false;
annoncesLoading = false;
chargerSignalements();

// ── Lien profond ────────────────────────────────────────────────────────────
// Trois rubriques cohabitent ici sous trois onglets. Sans cela, « Voir l'annonce → »
// déposait l'utilisateur sur l'onglet Sondages (bug signalé le 26/07/2026) : la page
// était la bonne, l'annonce introuvable. L'ancre prime sur `?onglet=`, elle est plus
// précise.
const ongletDemande = ongletDeLUrl(ONGLETS);
if (ongletDemande) activeTab = ongletDemande;

const idAnnonce = cibleDuHash('annonce');
if (idAnnonce !== null) {
	activeTab = 'annonces';
	expandedAnnonce = idAnnonce; // détails dépliés, comme après un dépôt
	revelerCible(`annonce-${idAnnonce}`);
}

const idIdee = cibleDuHash('idee');
if (idIdee !== null) {
	activeTab = 'idees';
	revelerCible(`idee-${idIdee}`);
}
});
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} icone={_pc.icone || 'users-round'}>
	{#if activeTab === 'sondages' && $isCS}
		<button class="btn btn-primary page-header-btn" on:click={() => { showFormSondage = !showFormSondage; }}>
			{showFormSondage ? '✕ Annuler' : '+ Nouveau sondage'}
		</button>
	{:else if activeTab === 'idees'}
		<button class="btn btn-primary page-header-btn" on:click={() => { showFormIdee = !showFormIdee; }}>
			{showFormIdee ? '✕ Annuler' : '+ Nouvelle idée'}
		</button>
	{:else if activeTab === 'annonces'}
		<button class="btn btn-primary page-header-btn" on:click={() => { showFormAnnonce = !showFormAnnonce; }}>
			{showFormAnnonce ? '✕ Annuler' : '+ Déposer une annonce'}
		</button>
	{/if}
</EntetePage>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

{#if banMessage}
<div class="alert alert-danger" style="margin:2rem 0;padding:1.5rem;border-radius:10px;text-align:center;font-size:1.1rem">
	⛔ {banMessage}
</div>
{:else}
<!-- Onglets -->
<div class="tabs" role="tablist" style="margin-bottom:1.5rem">
<button role="tab" class:active={activeTab === 'sondages'} on:click={() => activeTab = 'sondages'}>
	{_pc.onglets?.sondages?.label ?? '\u{1F4CA} Sondages'}
</button>
<button role="tab" class:active={activeTab === 'idees'} on:click={() => activeTab = 'idees'}>
	{_pc.onglets?.idees?.label ?? '\u{1F4A1} Boîte à idées'}
</button>
<button role="tab" class:active={activeTab === 'annonces'} on:click={() => activeTab = 'annonces'}>
	{_pc.onglets?.annonces?.label ?? '\u{1F3F7}\uFE0F Petites annonces'}
</button>
</div>
{#if _pc.onglets?.[activeTab]?.descriptif}
<p class="tab-descriptif">{@html safeHtml(_pc.onglets[activeTab].descriptif)}</p>
{/if}

{#if $isCS && signalements.length > 0}
<div class="moderation-panel">
<button type="button" class="moderation-tete" on:click={() => showModeration = !showModeration}
aria-expanded={showModeration}>
🚩 {signalements.length} signalement{signalements.length > 1 ? 's' : ''} à modérer
<span class="moderation-chevron">{showModeration ? '▲' : '▼'}</span>
</button>
{#if showModeration}
<div class="moderation-liste">
{#each signalements as sig (sig.id)}
<div class="moderation-item">
<div class="moderation-meta">
<span class="badge badge-blue">{sig.cible_type_label}</span>
<strong>« {sig.apercu}</strong>
{#if sig.auteur_cible}<span style="color:var(--color-text-muted)">— par {sig.auteur_cible}</span>{/if}
</div>
<div class="moderation-motif">Motif : {sig.motif} <span style="color:var(--color-text-muted)">(signalé par {sig.signale_par})</span></div>
<div class="moderation-actions">
<button class="btn btn-sm btn-outline" on:click={() => resoudreSignalement(sig.id, 'traite')}>✓ Marquer traité</button>
<button class="btn btn-sm btn-outline" on:click={() => resoudreSignalement(sig.id, 'rejete')}>Ignorer</button>
</div>
</div>
{/each}
<p class="moderation-aide">Pour retirer un contenu, utilisez le bouton 🗑️ sur le contenu concerné, puis marquez le signalement « traité ». Les récidives se gèrent via Admin → bannissement Communauté.</p>
</div>
{/if}
</div>
{/if}

{#if activeTab === 'sondages'}
{#if showFormSondage && $isCS}
<div class="card largeur-saisie" style="padding:1.25rem;margin-bottom:1.5rem">
<h2 style="font-size:1rem;font-weight:600;margin-bottom:1rem">Nouveau sondage</h2>
<form on:submit|preventDefault={creerSondage}>
<label style="display:flex;flex-direction:column;gap:.3rem;margin-bottom:.75rem">
Question *
<input bind:value={formSondage.question} required />
</label>
<div class="field">
<label>Description</label>
<RichEditor bind:value={formSondage.description} placeholder="Description du sondage…" minHeight="80px" />
</div>
<div class="form-row-2" style="margin-bottom:.75rem">
<label style="display:flex;flex-direction:column;gap:.3rem">
Date de clôture
<input type="datetime-local" bind:value={formSondage.cloture_le} />
</label>
<label style="display:flex;align-items:center;gap:.5rem;cursor:pointer">
<input type="checkbox" bind:checked={formSondage.resultats_publics} />
Résultats visibles avant clôture
</label>
</div>
<div style="margin-bottom:.75rem">
<div style="font-size:.9rem;font-weight:600;margin-bottom:.4rem">Options ({formSondage.options.length})</div>
{#each formSondage.options as opt, i}
<div style="display:flex;flex-direction:column;gap:.25rem;margin-bottom:.5rem;padding:.6rem .75rem;border:1px solid var(--color-border);border-radius:var(--radius);background:var(--color-bg-subtle,#fafafa)">
	<div style="display:flex;gap:.4rem;align-items:center">
		<span style="font-size:.78rem;color:var(--color-text-muted);min-width:1.1rem;text-align:right">{i + 1}.</span>
		<input class="flex1" bind:value={formSondage.options[i].libelle} placeholder="Option {i + 1}" />
		<button type="button" class="btn btn-sm btn-outline" title="Monter" disabled={i === 0} on:click={() => moveOptionUp(i)}>↑</button>
		<button type="button" class="btn btn-sm btn-outline" title="Descendre" disabled={i === formSondage.options.length - 1} on:click={() => moveOptionDown(i)}>↓</button>
		{#if formSondage.options.length > 2}
		<button type="button" class="btn btn-sm btn-outline" style="color:var(--color-danger,#dc2626)" title="Supprimer" on:click={() => removeOption(i)}>✕</button>
		{/if}
	</div>
	<label style="display:flex;align-items:center;gap:.4rem;font-size:.8rem;color:var(--color-text-muted);cursor:pointer;padding-left:1.6rem">
		<input type="checkbox" bind:checked={formSondage.options[i].champ_libre} />
		Champ libre (le répondant pourra préciser sa réponse par écrit)
	</label>
</div>
{/each}
<button type="button" class="btn btn-sm btn-outline" on:click={addOption}>+ Ajouter une option</button>
</div>

<!-- Ciblage profils -->
<div style="margin-bottom:.75rem">
	<div style="font-size:.9rem;font-weight:600;margin-bottom:.4rem">
		Profils destinataires
		{#if tousProfils}<span class="badge badge-green" style="font-size:.72rem;margin-left:.4rem">Tous</span>{/if}
	</div>
	<div class="ciblage-grid">
		{#each PROFILS as p}
			<label class="ciblage-option" class:selected={selectedProfils.includes(p.val)}>
				<input type="checkbox" checked={selectedProfils.includes(p.val)} on:change={() => toggleProfil(p.val)} />
				{p.label}
			</label>
		{/each}
	</div>
	{#if !tousProfils}
		<button type="button" class="btn btn-sm btn-outline" style="margin-top:.35rem" on:click={() => selectedProfils = []}>
			Réinitialiser (tous)
		</button>
	{/if}
</div>

<!-- Ciblage bâtiments -->
{#if batimentsList.length > 0}
<div style="margin-bottom:.75rem">
	<div style="font-size:.9rem;font-weight:600;margin-bottom:.4rem">
		Périmètre géographique
		{#if tousBatiments}<span class="badge badge-green" style="font-size:.72rem;margin-left:.4rem">Toute la résidence</span>{/if}
	</div>
	<div class="ciblage-grid">
		{#each batimentsList as b}
			<label class="ciblage-option" class:selected={selectedBatiments.includes(b.id)}>
				<input type="checkbox" checked={selectedBatiments.includes(b.id)} on:change={() => toggleBatiment(b.id)} />
				Bâtiment {b.numero}
			</label>
		{/each}
	</div>
	{#if !tousBatiments}
		<button type="button" class="btn btn-sm btn-outline" style="margin-top:.35rem" on:click={() => selectedBatiments = []}>
			Réinitialiser (toute la résidence)
		</button>
	{/if}
</div>
{/if}

<div class="field" style="margin-bottom:.75rem">
	<CanauxNotification
		bind:whatsapp={formSondage.partager_whatsapp}
		bind:syndic={formSondage.envoyer_syndic}
		bind:cs={formSondage.envoyer_cs}
	/>
</div>
<button class="btn btn-primary" disabled={submittingSondage}>{submittingSondage ? '' : 'Créer le sondage'}</button>
</form>
</div>
{/if}

{#if sondagesLoading}
<p style="color:var(--color-text-muted)">Chargement</p>
{:else if sondages.length === 0}
<div class="empty-state">
<h3>Aucun sondage</h3>
<p>Les sondages du conseil syndical apparaîtront ici.</p>
</div>
{:else}
{#each sondages as s}
<a href="/sondages/{s.id}" class="sondage-card card">
<div class="sondage-body">
<strong class="sondage-question">{s.question}
{#if isNouveau(s.cree_le, s.mis_a_jour_le)}<span class="badge badge-gray" style="margin-left:.5em;font-size:.82em;font-weight:500;vertical-align:middle">New</span>{/if}
</strong>
{#if s.description}<div class="sondage-desc rich-content clamp-5">{@html safeHtml(s.description)}</div>{/if}
<small style="color:var(--color-text-muted)">
{fmtDateShort(s.cree_le)}
{#if s.cloture_le}
· {estCloture(s) ? '🔒 Clôturé' : `Clôture le ${fmtDateShort(s.cloture_le)}`}
{/if}
· <span class="sondage-votants">{s.nb_votants ?? 0} votant{(s.nb_votants ?? 0) !== 1 ? 's' : ''}</span>
</small>
{#if s.profils_autorises || s.batiments_ids}
<div class="sondage-ciblage">
	{#if s.profils_autorises}
		{#each s.profils_autorises.split(',') as p}
			<span class="badge badge-orange" style="font-size:.7rem">{p.trim()}</span>
		{/each}
	{/if}
	{#if s.batiments_ids}
		{#each s.batiments_ids.split(',') as bid}
			<span class="badge badge-blue" style="font-size:.7rem">Bât. {bid.trim()}</span>
		{/each}
	{/if}
</div>
{/if}
</div>
<div class="sondage-actions">
  {#if estCloture(s) || s.cloture_forcee}
<span class="badge badge-gray">Clôturé</span>
{:else}
<span class="badge badge-green">Ouvert</span>
{/if}
{#if ($currentUser?.id === s.auteur_id || $isAdmin) && !(estCloture(s) || s.cloture_forcee)}
<button class="btn-icon-warn" aria-label="Stopper ce sondage" title="Stopper" on:click={e => arreterSondage(s, e)}>⏹️</button>
{/if}
{#if $currentUser?.id === s.auteur_id || $isAdmin}
<button class="btn-icon-danger" aria-label="Supprimer" title="Supprimer" on:click={e => supprimerSondage(s, e)}>&#x1F5D1;️</button>
{/if}
</div>
</a>
{/each}
{/if}
{/if}

{#if activeTab === 'idees'}

{#if showFormIdee}
<div class="card largeur-saisie" style="padding:1.25rem;margin-bottom:1.5rem">
<form on:submit|preventDefault={creerIdee}>
<label style="display:flex;flex-direction:column;gap:.3rem;margin-bottom:.75rem">
Titre *
<input bind:value={formIdee.titre} placeholder="Ex. Vélos électriques en libre-service" required />
</label>
<div class="field">
<label>Description *</label>
<RichEditor bind:value={formIdee.description} placeholder="Décrivez votre idée…" minHeight="100px" />
</div>
<button class="btn btn-primary" disabled={submittingIdee}>{submittingIdee ? 'Envoi' : 'Soumettre'}</button>
</form>
</div>
{/if}

<div class="filters" style="margin-bottom:1.25rem">
{#each statuts as s}
<button class="btn btn-sm" class:btn-primary={filtreStatut === s.val} on:click={() => filtreStatut = s.val}>{s.label}</button>
{/each}
</div>

{#if ideesLoading}
<p style="color:var(--color-text-muted)">Chargement</p>
{:else if sortedIdees.length === 0}
<div class="empty-state">
<h3>Aucune idée pour l'instant</h3>
<p>Soyez le premier à proposer une idée !</p>
</div>
{:else}
{#each sortedIdees as idee}
<div class="idee-card card" id="idee-{idee.id}">
<button class="vote-btn" class:voted={idee.mon_vote} on:click={() => voter(idee.id)}
title={idee.mon_vote ? 'Retirer mon vote' : 'Voter pour cette idée'}>
<span class="vote-icon">{idee.mon_vote ? '❤️' : '\u{1F90D}'}</span>
<span class="vote-count">{idee.nb_votes}</span>
</button>
<div class="idee-body">
<div class="idee-header">
<strong class="idee-titre">{idee.titre}
{#if isNouveau(idee.cree_le, idee.mis_a_jour_le)}<span class="badge badge-gray" style="margin-left:.5em;font-size:.82em;font-weight:500;vertical-align:middle">New</span>{/if}
</strong>
<span class="badge {statutClass(idee.statut)}">{idee.statut}</span>
</div>
<div class="idee-desc rich-content clamp-5">{@html safeHtml(idee.description)}</div>
<small style="color:var(--color-text-muted)">{fmtDateShort(idee.cree_le)}</small>
{#if idee.auteur_id !== $currentUser?.id}
<button class="signaler-inline" title="Signaler cette idée au conseil syndical" aria-label="Signaler cette idée" on:click={() => signaler('idee', idee.id)}>🚩</button>
{/if}

<Reponses
reponses={idee.reponses ?? []}
currentUserId={$currentUser?.id}
isCS={$isCS}
placeholder="Votre réponse à cette idée…"
onSubmit={(c) => repondreIdee(idee.id, c)}
onDelete={(rid) => supprimerReponseIdee(idee.id, rid)}
onReport={(rid) => signaler('reponse', rid)}
/>
</div>
{#if $isCS}
<div class="idee-actions">
<select value={idee.statut} on:change={e => changeStatut(idee.id, (e.target as HTMLSelectElement).value)}>
<option value="ouverte">Ouverte</option>
<option value="retenue">Retenue</option>
<option value="realisee">Réalisée</option>
<option value="rejetee">Rejetée</option>
</select>
{#if $isAdmin}
<button class="btn-icon-danger" title="Supprimer cette idée" on:click={() => deleteIdee(idee.id)}>🗑️</button>
{/if}
</div>
{/if}
</div>
{/each}
{/if}
{/if}

{#if activeTab === 'annonces'}
{#if showFormAnnonce}
<div class="card largeur-saisie" style="padding:1.25rem;margin-bottom:1.5rem">
<h2 style="font-size:1rem;font-weight:600;margin-bottom:1rem">Déposer une annonce</h2>
<form on:submit|preventDefault={creerAnnonce}>
<label style="display:flex;flex-direction:column;gap:.3rem;margin-bottom:.75rem">
Titre *
<input bind:value={formAnnonce.titre} placeholder="Ex. Lave-linge Samsung presque neuf" required />
</label>
<div class="field" style="margin-bottom:.75rem">
<label>Description *</label>
<RichEditor bind:value={formAnnonce.description} placeholder="Décrivez l'objet, son état, conditions de remise…" minHeight="90px" />
</div>
<div class="form-row-2" style="margin-bottom:.75rem">
<label style="display:flex;flex-direction:column;gap:.3rem">
Type
<select bind:value={formAnnonce.type_annonce}>
{#each TYPES_ANNONCE as t}<option value={t.val}>{t.label}</option>{/each}
</select>
</label>
<label style="display:flex;flex-direction:column;gap:.3rem">
Catégorie
<select bind:value={formAnnonce.categorie}>
{#each CATEGORIES_ANNONCE as c}<option value={c.val}>{c.label}</option>{/each}
</select>
</label>
</div>
{#if formAnnonce.type_annonce === 'vente'}
<div class="form-row-2" style="margin-bottom:.75rem">
<label style="display:flex;flex-direction:column;gap:.3rem">
Prix (€)
<input type="number" min="0" step="0.01" bind:value={formAnnonce.prix} placeholder="0.00" />
</label>
<label style="display:flex;align-items:center;gap:.5rem;cursor:pointer;margin-top:1.6rem">
<input type="checkbox" bind:checked={formAnnonce.negotiable} />
Prix négociable
</label>
</div>
{/if}
<label style="display:flex;align-items:center;gap:.5rem;cursor:pointer;margin-bottom:.75rem">
<input type="checkbox" bind:checked={formAnnonce.contact_visible} />
Afficher mes coordonnées aux autres résidents
</label>
<button class="btn btn-primary" disabled={submittingAnnonce}>{submittingAnnonce ? '⏳' : "Publier l'annonce"}</button>
</form>
</div>
{/if}

<!-- Filtres annonces -->
<div class="filters" style="margin-bottom:1.25rem">
<select bind:value={filtreTypeAnnonce} class="filter-select">
<option value="">Tous types</option>
{#each TYPES_ANNONCE as t}<option value={t.val}>{t.label}</option>{/each}
</select>
<select bind:value={filtreCatAnnonce} class="filter-select">
<option value="">Toutes catégories</option>
{#each CATEGORIES_ANNONCE as c}<option value={c.val}>{c.label}</option>{/each}
</select>
<select bind:value={filtreTriAnnonce} class="filter-select">
<option value="recent">Plus récentes</option>
<option value="prix_asc">Prix croissant</option>
<option value="prix_desc">Prix décroissant</option>
</select>
</div>

{#if annoncesLoading}
<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if sortedAnnonces.length === 0}
<div class="empty-state">
<h3>Aucune annonce</h3>
<p>Déposez la première annonce en cliquant sur « Déposer une annonce ».</p>
</div>
{:else}
{#each sortedAnnonces as annonce}
<AnnonceCard
	{annonce}
	expanded={expandedAnnonce === annonce.id}
	gestionOuverte={gestionPhotos === annonce.id}
	estCS={$isCS}
	estAdmin={$isAdmin}
	currentUserId={$currentUser?.id}
	onToggle={() => (expandedAnnonce = expandedAnnonce === annonce.id ? null : annonce.id)}
	onToggleGestion={() => (gestionPhotos = gestionPhotos === annonce.id ? null : annonce.id)}
	onUpload={(f) => uploadPhotoAnnonce(annonce.id, f)}
	onRemove={(url) => supprimerPhotoAnnonce(annonce.id, url)}
	onStatut={(statut) => changeStatutAnnonce(annonce.id, statut)}
	onSupprimer={() => supprimerAnnonce(annonce.id)}
	onRepondre={(c) => repondreAnnonce(annonce.id, c)}
	onSupprimerReponse={(rid) => supprimerReponseAnnonce(annonce.id, rid)}
	onSignalerAnnonce={() => signaler('annonce', annonce.id)}
	onSignalerReponse={(rid) => signaler('reponse', rid)}
/>
{/each}
{/if}
{/if}

{/if}
<!-- /banMessage else -->

<style>
.tabs { display: flex; gap: .4rem; border-bottom: 2px solid var(--color-border); padding-bottom: .1rem; }
.tabs button {
padding: .45rem 1rem; border: none; background: none; cursor: pointer;
font-size: .9rem; color: var(--color-text-muted); border-bottom: 2px solid transparent;
margin-bottom: -2px; border-radius: var(--radius) var(--radius) 0 0;
}
.tabs button:hover { color: var(--color-text); background: var(--color-bg); }
.tabs button.active { color: var(--color-primary); font-weight: 600; border-bottom-color: var(--color-primary); }
.form-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.flex1 { flex: 1; padding: .45rem .6rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: .9rem; background: var(--color-bg); }
input, textarea { padding: .45rem .6rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: .9rem; background: var(--color-bg); width: 100%; }
.sondage-card { display: flex; justify-content: space-between; align-items: flex-start; padding: 1rem 1.25rem; margin-bottom: .5rem; text-decoration: none; color: var(--color-text); transition: border-color .12s; }
.sondage-card:hover { border-color: var(--color-primary); }
.sondage-actions { display: flex; flex-direction: column; align-items: flex-end; gap: .35rem; flex-shrink: 0; }
.sondage-question { font-size: .95rem; font-weight: 600; display: block; margin-bottom: .2rem; }
.sondage-desc { font-size: .85rem; color: var(--color-text-muted); margin: .2rem 0 .3rem; }
.sondage-votants { font-weight: 600; }
.sondage-ciblage { display: flex; flex-wrap: wrap; gap: .25rem; margin-top: .35rem; }
.filters { display: flex; gap: .4rem; flex-wrap: wrap; }
.idee-card { display: flex; gap: 1rem; align-items: flex-start; padding: 1rem 1.25rem; margin-bottom: .5rem; }
.vote-btn { display: flex; flex-direction: column; align-items: center; gap: .2rem; background: none; border: 1px solid var(--color-border); border-radius: var(--radius); padding: .5rem .6rem; cursor: pointer; transition: border-color .12s; min-width: 3.5rem; }
.vote-btn:hover { border-color: var(--color-primary); }
.vote-btn.voted { border-color: var(--color-primary); background: var(--color-primary-light); }
.vote-icon { font-size: 1.1rem; }
.vote-count { font-size: .85rem; font-weight: 700; color: var(--color-primary); }
.idee-body { flex: 1; }
.idee-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: .3rem; flex-wrap: wrap; gap: .4rem; }
.idee-titre { font-size: .95rem; }
.idee-desc { font-size: .85rem; color: var(--color-text-muted); margin: .2rem 0 .3rem; }
.idee-actions select { padding: .35rem .5rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: .8rem; background: var(--color-bg); }
/* Les styles des réponses sont dans le composant partagé Reponses.svelte */
/* Signalement + modération */
.signaler-inline { background: none; border: none; cursor: pointer; font-size: .78rem; color: var(--color-text-muted); opacity: .7; padding: 0 0 0 .5rem; }
.signaler-inline:hover { opacity: 1; color: var(--color-danger); }
.moderation-panel { border: 1px solid var(--color-warning); border-radius: var(--radius); background: #fffbeb; margin-bottom: 1.25rem; overflow: hidden; }
.moderation-tete { width: 100%; text-align: left; background: none; border: none; padding: .7rem 1rem; font-weight: 600; font-size: .9rem; cursor: pointer; color: var(--color-text); display: flex; align-items: center; gap: .5rem; }
.moderation-chevron { margin-left: auto; font-size: .75rem; }
.moderation-liste { padding: 0 1rem 1rem; display: flex; flex-direction: column; gap: .6rem; }
.moderation-item { border: 1px solid var(--color-border); border-radius: var(--radius); padding: .6rem .8rem; background: var(--color-surface); }
.moderation-meta { display: flex; flex-wrap: wrap; gap: .4rem; align-items: center; font-size: .85rem; margin-bottom: .25rem; }
.moderation-motif { font-size: .82rem; margin-bottom: .4rem; }
.moderation-actions { display: flex; gap: .5rem; flex-wrap: wrap; }
.moderation-aide { font-size: .75rem; color: var(--color-text-muted); margin-top: .3rem; }
/* Ciblage */
.ciblage-grid { display: flex; flex-wrap: wrap; gap: .4rem; }
.ciblage-option {
	display: flex; align-items: center; gap: .35rem;
	padding: .3rem .65rem; border: 1px solid var(--color-border); border-radius: 9999px;
	font-size: .82rem; cursor: pointer; background: var(--color-bg);
	transition: border-color .12s, background .12s;
}
.ciblage-option:hover { border-color: var(--color-primary); }
.ciblage-option.selected { border-color: var(--color-primary); background: var(--color-primary-light); color: var(--color-primary); font-weight: 600; }
.ciblage-option input[type="checkbox"] { display: none; }
/* Annonces */
.filter-select { padding: .35rem .5rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: .85rem; background: var(--color-bg); }
</style>