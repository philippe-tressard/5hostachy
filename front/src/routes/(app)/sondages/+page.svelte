<script lang="ts">
import Icon from '$lib/components/Icon.svelte';
import { onMount } from 'svelte';
import { goto } from '$app/navigation';
import { api, sondages as sondagesApi, idees as ideesApi, annonces as annoncesApi, ApiError } from '$lib/api';
import { isCS, isAdmin, currentUser } from '$lib/stores/auth';
import RichEditor from '$lib/components/RichEditor.svelte';
import { toast } from '$lib/components/Toast.svelte';
import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
import { safeHtml } from '$lib/sanitize';
import { fmtDateShort } from '$lib/date';
import { trackTabView } from '$lib/telemetry';

$: _pc = getPageConfig($configStore, 'communaute', { titre: 'Communauté', navLabel: 'Communauté', icone: 'users-round', descriptif: 'Sondages, boîte à idées et petites annonces entre résidents.', onglets: { sondages: { label: '\u{1F4CA} Sondages', descriptif: 'Participez aux votes et consultations de la copropriété.' }, idees: { label: '\u{1F4A1} Boîte à idées', descriptif: 'Proposez et soutenez des idées pour améliorer la vie en résidence.' }, annonces: { label: '\u{1F3F7}\uFE0F Petites annonces', descriptif: 'Achetez, vendez ou donnez des objets entre résidents.' } } });
$: _siteNom = $siteNomStore;

type Tab = 'sondages' | 'idees' | 'annonces';
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
let formSondage = { question: '', description: '', cloture_le: '', resultats_publics: true, options: [{ libelle: '', champ_libre: false }, { libelle: '', champ_libre: false }] as OptionForm[] };

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
	question: formSondage.question, description: formSondage.description || undefined,
	cloture_le: formSondage.cloture_le ? new Date(formSondage.cloture_le).toISOString() : undefined,
	resultats_publics: formSondage.resultats_publics, options: opts,
	profils_autorises: selectedProfils.length > 0 ? selectedProfils : null,
	batiments_ids: selectedBatiments.length > 0 ? selectedBatiments : null,
});
sondages = await sondagesApi.list();
showFormSondage = false;
formSondage = { question: '', description: '', cloture_le: '', resultats_publics: true, options: [{ libelle: '', champ_libre: false }, { libelle: '', champ_libre: false }] };
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
let uploadingPhotoId: number | null = null;

const TYPES_ANNONCE = [
	{ val: 'vente', label: '\u{1F3F7}\uFE0F Vente' },
	{ val: 'don', label: '\u{1F381} Don' },
	{ val: 'recherche', label: '\u{1F50D} Recherche' },
];
const CATEGORIES_ANNONCE = [
	{ val: 'appartement', label: '\u{1F3E0} Appartement' },
	{ val: 'parking_cave', label: '\u{1F17F}\uFE0F Parking / Cave' },
	{ val: 'mobilier', label: '\u{1F6CB}\uFE0F Mobilier' },
	{ val: 'electromenager', label: '\u{1FAD9} Électroménager' },
	{ val: 'high_tech', label: '\u{1F4BB} High-tech' },
	{ val: 'vehicule', label: '\u{1F697} Véhicule' },
	{ val: 'vetements', label: '\u{1F457} Vêtements' },
	{ val: 'services', label: '\u{1F6E0}\uFE0F Services' },
	{ val: 'divers', label: '\u{1F4E6} Divers' },
];
const STATUTS_ANNONCE = [
	{ val: 'disponible', label: 'Disponible' },
	{ val: 'reserve', label: 'Réservé' },
	{ val: 'vendu', label: 'Vendu / Donné' },
	{ val: 'archive', label: 'Archiver' },
];

$: filteredAnnonces = annonces
	.filter(a => !filtreTypeAnnonce || a.type_annonce === filtreTypeAnnonce)
	.filter(a => !filtreCatAnnonce || a.categorie === filtreCatAnnonce);
$: sortedAnnonces = [...filteredAnnonces].sort((a, b) => {
	if (filtreTriAnnonce === 'prix_asc') return (a.prix ?? 999999) - (b.prix ?? 999999);
	if (filtreTriAnnonce === 'prix_desc') return (b.prix ?? 0) - (a.prix ?? 0);
	return new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime();
});

function typeAnnonceLabel(val: string) { return TYPES_ANNONCE.find(t => t.val === val)?.label ?? val; }
function categorieAnnonceLabel(val: string) { return CATEGORIES_ANNONCE.find(c => c.val === val)?.label ?? val; }
function typeAnnonceClass(val: string) { return ({ vente: 'badge-blue', don: 'badge-green', recherche: 'badge-orange' } as Record<string, string>)[val] ?? 'badge-gray'; }
function statutAnnonceClass(val: string) { return ({ disponible: 'badge-green', reserve: 'badge-orange', vendu: 'badge-gray', archive: 'badge-gray' } as Record<string, string>)[val] ?? 'badge-gray'; }

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

async function uploadPhotoAnnonce(id: number, file: File) {
	uploadingPhotoId = id;
	try {
		const res: any = await annoncesApi.uploadPhoto(id, file);
		annonces = annonces.map(a => a.id === id ? { ...a, photos: res.photos } : a);
	} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur upload'); }
	finally { uploadingPhotoId = null; }
}

async function supprimerPhotoAnnonce(id: number, url: string) {
	try {
		const res: any = await annoncesApi.deletePhoto(id, url);
		annonces = annonces.map(a => a.id === id ? { ...a, photos: res.photos } : a);
	} catch { toast('error', 'Erreur'); }
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
});
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<div class="page-header" style="justify-content:space-between;flex-wrap:wrap">
<h1 style="display:flex;align-items:center;gap:.4rem;font-size:1.4rem;font-weight:700"><Icon name={_pc.icone || 'users-round'} size={20} />{_pc.titre}</h1>
{#if activeTab === 'sondages' && $isCS}
<button class="btn btn-primary page-header-btn" on:click={() => { showFormSondage = !showFormSondage; }}>
{showFormSondage ? 'Annuler' : '+ Nouveau sondage'}
</button>
{:else if activeTab === 'idees'}
<button class="btn btn-primary page-header-btn" on:click={() => { showFormIdee = !showFormIdee; }}>
{showFormIdee ? 'Annuler' : '+ Nouvelle idée'}
</button>
{:else if activeTab === 'annonces'}
<button class="btn btn-primary page-header-btn" on:click={() => { showFormAnnonce = !showFormAnnonce; }}>
{showFormAnnonce ? 'Annuler' : '+ Déposer une annonce'}
</button>
{/if}
</div>
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

{#if activeTab === 'sondages'}
{#if showFormSondage && $isCS}
<div class="card" style="padding:1.25rem;margin-bottom:1.5rem">
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
<strong class="sondage-question">{s.question}</strong>
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
<div class="card" style="padding:1.25rem;margin-bottom:1.5rem">
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
<div class="idee-card card">
<button class="vote-btn" class:voted={idee.mon_vote} on:click={() => voter(idee.id)}
title={idee.mon_vote ? 'Retirer mon vote' : 'Voter pour cette idée'}>
<span class="vote-icon">{idee.mon_vote ? '❤️' : '\u{1F90D}'}</span>
<span class="vote-count">{idee.nb_votes}</span>
</button>
<div class="idee-body">
<div class="idee-header">
<strong class="idee-titre">{idee.titre}</strong>
<span class="badge {statutClass(idee.statut)}">{idee.statut}</span>
</div>
<div class="idee-desc rich-content clamp-5">{@html safeHtml(idee.description)}</div>
<small style="color:var(--color-text-muted)">{fmtDateShort(idee.cree_le)}</small>
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
<div class="card" style="padding:1.25rem;margin-bottom:1.5rem">
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
<div class="annonce-card card">
<div class="annonce-top">
{#if annonce.photos?.length > 0}
<div class="annonce-thumb">
<img src={annonce.photos[0]} alt={annonce.titre} />
{#if annonce.photos.length > 1}<span class="annonce-thumb-count">+{annonce.photos.length - 1}</span>{/if}
</div>
{:else}
<div class="annonce-thumb annonce-thumb-empty">{categorieAnnonceLabel(annonce.categorie).split(' ')[0]}</div>
{/if}

<div class="annonce-body">
<div class="annonce-header">
<span class="badge {typeAnnonceClass(annonce.type_annonce)}" style="font-size:.72rem">{typeAnnonceLabel(annonce.type_annonce)}</span>
<span class="badge {statutAnnonceClass(annonce.statut)}" style="font-size:.72rem">{annonce.statut}</span>
</div>
<strong class="annonce-titre">{annonce.titre}</strong>
<small style="color:var(--color-text-muted)">{categorieAnnonceLabel(annonce.categorie)} · {fmtDateShort(annonce.cree_le)}</small>
{#if annonce.prix !== null && annonce.prix !== undefined}
<div class="annonce-prix">{new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(annonce.prix)}{#if annonce.negotiable}&nbsp;<span class="badge badge-gray" style="font-size:.68rem">Négociable</span>{/if}</div>
{:else if annonce.type_annonce === 'don'}
<div class="annonce-prix" style="color:var(--color-success,#16a34a)">Gratuit</div>
{/if}
</div>

<div class="annonce-toggle-col">
<button class="btn btn-sm btn-outline" on:click={() => expandedAnnonce = expandedAnnonce === annonce.id ? null : annonce.id}>
{expandedAnnonce === annonce.id ? '▲' : '▼'}
</button>
</div>
</div>

{#if expandedAnnonce === annonce.id}
<div class="annonce-details">
<div class="rich-content" style="font-size:.88rem;margin-bottom:.75rem">{@html safeHtml(annonce.description)}</div>

{#if annonce.photos?.length > 1}
<div class="annonce-photos-row">
{#each annonce.photos as photo}
<div class="annonce-photo-thumb">
<img src={photo} alt="" />
{#if annonce.est_auteur}<button class="btn-photo-del" on:click={() => supprimerPhotoAnnonce(annonce.id, photo)} title="Supprimer">×</button>{/if}
</div>
{/each}
</div>
{:else if annonce.photos?.length === 1 && annonce.est_auteur}
<div class="annonce-photos-row">
<div class="annonce-photo-thumb">
<img src={annonce.photos[0]} alt="" />
<button class="btn-photo-del" on:click={() => supprimerPhotoAnnonce(annonce.id, annonce.photos[0])} title="Supprimer">×</button>
</div>
</div>
{/if}

<div class="annonce-contact">
{#if annonce.auteur_email}
<small>📬 <a href="mailto:{annonce.auteur_email}">{annonce.auteur_prenom} {annonce.auteur_nom}</a></small>
{:else}
<small>👤 {annonce.auteur_prenom} {annonce.auteur_nom}</small>
{/if}
</div>

{#if annonce.est_auteur}
<div class="annonce-actions">
{#if annonce.photos?.length < 5}
<label class="btn btn-sm btn-outline" style="cursor:pointer;display:inline-flex;align-items:center;gap:.3rem">
{uploadingPhotoId === annonce.id ? '⏳ Upload…' : '📷 Photo'}
<input type="file" accept="image/*" style="display:none"
	on:change={async (e) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) await uploadPhotoAnnonce(annonce.id, f); (e.target as HTMLInputElement).value = ''; }}
/>
</label>
{/if}
<select value={annonce.statut} on:change={e => changeStatutAnnonce(annonce.id, (e.target as HTMLSelectElement).value)}>
{#each STATUTS_ANNONCE as s}<option value={s.val}>{s.label}</option>{/each}
</select>
<button class="btn-icon-danger" title="Supprimer" on:click={() => supprimerAnnonce(annonce.id)}>🗑️</button>
</div>
{:else if $isCS || $isAdmin}
<div class="annonce-actions">
<button class="btn btn-sm btn-outline" style="color:var(--color-danger)" on:click={() => supprimerAnnonce(annonce.id)}>🗑️ Supprimer</button>
</div>
{/if}
</div>
{/if}
</div>
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
.annonce-card { padding: .85rem 1.1rem; margin-bottom: .5rem; }
.annonce-top { display: flex; gap: .85rem; align-items: flex-start; }
.annonce-thumb { width: 80px; height: 80px; flex-shrink: 0; border-radius: var(--radius); overflow: hidden; position: relative; border: 1px solid var(--color-border); background: var(--color-bg-alt, #f5f5f5); }
.annonce-thumb img { width: 100%; height: 100%; object-fit: cover; }
.annonce-thumb-empty { display: flex; align-items: center; justify-content: center; font-size: 1.6rem; }
.annonce-thumb-count { position: absolute; bottom: 2px; right: 4px; font-size: .68rem; background: rgba(0,0,0,.55); color: #fff; border-radius: 4px; padding: 0 4px; }
.annonce-body { flex: 1; min-width: 0; }
.annonce-header { display: flex; gap: .3rem; flex-wrap: wrap; margin-bottom: .25rem; }
.annonce-titre { font-size: .95rem; font-weight: 600; display: block; margin-bottom: .15rem; }
.annonce-prix { font-size: .95rem; font-weight: 700; color: var(--color-primary); margin-top: .2rem; display: flex; align-items: center; gap: .3rem; }
.annonce-toggle-col { display: flex; align-items: flex-start; padding-top: .1rem; }
.annonce-details { border-top: 1px solid var(--color-border); margin-top: .75rem; padding-top: .75rem; }
.annonce-photos-row { display: flex; gap: .5rem; flex-wrap: wrap; margin-bottom: .75rem; }
.annonce-photo-thumb { position: relative; width: 72px; height: 72px; border-radius: var(--radius); overflow: hidden; border: 1px solid var(--color-border); }
.annonce-photo-thumb img { width: 100%; height: 100%; object-fit: cover; }
.btn-photo-del { position: absolute; top: 2px; right: 2px; background: rgba(0,0,0,.6); color: #fff; border: none; border-radius: 50%; width: 18px; height: 18px; font-size: .75rem; cursor: pointer; line-height: 1; display: flex; align-items: center; justify-content: center; }
.annonce-contact { margin-bottom: .6rem; }
.annonce-contact a { color: var(--color-primary); }
.annonce-actions { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
.annonce-actions select { padding: .35rem .5rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: .8rem; background: var(--color-bg); }
.filter-select { padding: .35rem .5rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: .85rem; background: var(--color-bg); }
</style>