<script lang="ts">
	import EnteteCarte from '$lib/components/EnteteCarte.svelte';
import EntetePage from '$lib/components/EntetePage.svelte';
import FormulaireIdee from '$lib/components/FormulaireIdee.svelte';
import WorkflowPastilles from '$lib/components/WorkflowPastilles.svelte';
import { STATUTS_IDEE, STATUTS_IDEE_FILTRE, IDEE_BADGE, STATUT_IDEE_LABELS } from '$lib/idees';
import FormulaireSondage from '$lib/components/FormulaireSondage.svelte';
import OngletAnnonces from '$lib/components/OngletAnnonces.svelte';
import Reponses from '$lib/components/Reponses.svelte';
import FichiersUpload from '$lib/components/FichiersUpload.svelte';
import { onMount } from 'svelte';
import { goto } from '$app/navigation';
import { api, sondages as sondagesApi, idees as ideesApi, annonces as annoncesApi, signalements as signalementsApi, ApiError } from '$lib/api';
import { isCS, isAdmin, currentUser } from '$lib/stores/auth';
import RichEditor from '$lib/components/RichEditor.svelte';
import CanauxNotification from '$lib/components/CanauxNotification.svelte';
import { toast } from '$lib/components/Toast.svelte';
import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
import { safeHtml } from '$lib/sanitize';
import { fmtDateShort, isNouveau } from '$lib/date';
import { trackTabView } from '$lib/telemetry';
import { cibleDuHash, ongletDeLUrl, revelerCible } from '$lib/deepLink';
import { estPerimetreParDefaut, perimetreLabel } from '$lib/perimetres';
import { concerneTousLesResidents, destinatairesLabel } from '$lib/destinataires';

$: _pc = getPageConfig($configStore, 'communaute', defautsDePage('communaute'));
$: _siteNom = $siteNomStore;

// Liste explicite : elle sert aussi à valider le `?onglet=` d'un lien profond
// (fil d'activité, notification) — cf. $lib/deepLink.ts.
const ONGLETS = ['sondages', 'idees', 'annonces'] as const;
type Tab = (typeof ONGLETS)[number];
let activeTab: Tab = 'sondages';
$: trackTabView(activeTab);

// Ban communauté
let banMessage = '';

// Sondages — l'état de SAISIE vit dans `FormulaireSondage.svelte` : le ciblage
// (périmètre, destinataires), les options et les canaux y sont désormais, avec
// le reste des formulaires du site. Ne restent ici que la LISTE et ses actions.
let sondages: any[] = [];
let sondagesLoading = true;
let showFormSondage = false;

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
let filtreStatut = '';

//  Les annonces : la page les CHARGE (un seul `Promise.all` pour les trois
//  rubriques) et les lie à `OngletAnnonces`, qui porte tout le reste — filtres,
//  formulaires, gestes. `expandedAnnonce` reste ici parce qu'un lien profond
//  (`#annonce-12`) la désigne avant que l'onglet ne soit monté.
let annonces: any[] = [];
let annoncesLoading = true;
let showFormAnnonce = false;
let expandedAnnonce: number | null = null;

const statuts = STATUTS_IDEE_FILTRE;
const statutClass = (s: string) => IDEE_BADGE[s] ?? 'badge-gray';

$: filteredIdees = filtreStatut ? idees.filter(i => i.statut === filtreStatut) : idees;
$: sortedIdees = [...filteredIdees].sort((a, b) => b.nb_votes - a.nb_votes);

function ideeCreee() {
	//  La liste est rechargée plutôt que complétée localement : le compteur de
	//  votes et le statut sont calculés par le serveur.
	ideesApi.list().then((l) => (idees = l));
	showFormIdee = false;
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
//  La liste des bâtiments n'est plus chargée ici : le sélecteur de périmètre
//  lit l'arbre complet depuis son store, comme sur tous les autres écrans — un
//  bâtiment n'est qu'un nœud parmi le parking, l'AFUL et les espaces.
[sondages, idees, annonces] = await Promise.all([
	sondagesApi.list().catch(() => []),
	ideesApi.list().catch(() => []),
	annoncesApi.list().catch(() => []),
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

<!--  L'en-tête n'OUVRE plus : l'annulation vit à côté d'« Enregistrer » (norme du
      18/08/2026). Deux commandes pour un formulaire, c'est #367. -->
<EntetePage titre={_pc.titre} icone={_pc.icone || 'users-round'}>
	{#if activeTab === 'sondages' && $isCS && !showFormSondage}
		<button class="btn btn-primary page-header-btn" on:click={() => (showFormSondage = true)}>
			+ Nouveau sondage
		</button>
	{:else if activeTab === 'idees' && !showFormIdee}
		<button class="btn btn-primary page-header-btn" on:click={() => (showFormIdee = true)}>
			+ Nouvelle idée
		</button>
	{:else if activeTab === 'annonces' && !showFormAnnonce}
		<button class="btn btn-primary page-header-btn" on:click={() => (showFormAnnonce = true)}>
			+ Déposer une annonce
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
<FormulaireSondage on:cree={async () => { sondages = await sondagesApi.list(); showFormSondage = false; }}
	on:annule={() => (showFormSondage = false)} />
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
<!--  Ciblage affiché comme PARTOUT ailleurs : 🔹 pour le périmètre logique
      (jamais 📍, qui est réservé au lieu physique), et rien du tout quand le
      ciblage est le défaut — le redire n'apprend rien. Les badges rendaient
      jusqu'ici les valeurs BRUTES de la base (« copropriétaire_résident »,
      « Bât. 3 » reconstitué à la main), faute de traduction disponible. -->
{#if !estPerimetreParDefaut(s.perimetre_cible) || !concerneTousLesResidents(s.public_cible)}
<div class="sondage-ciblage">
	{#if !estPerimetreParDefaut(s.perimetre_cible)}
		<span class="badge badge-blue sondage-badge">&#x1F539; {perimetreLabel(s.perimetre_cible)}</span>
	{/if}
	{#if !concerneTousLesResidents(s.public_cible)}
		<span class="badge badge-orange sondage-badge">{destinatairesLabel(s.public_cible)}</span>
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
<FormulaireIdee on:cree={ideeCreee} on:annule={() => (showFormIdee = false)} />
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
<!--  🔴 L'EN-TÊTE DU SITE (18/08/2026, signalé à l'écran : « l'état sur une
      2nde ligne après le titre »). Le titre et le badge d'état partageaient une
      ligne en `space-between`, seule carte du produit dans ce cas — les quatre
      autres passent par `EnteteCarte` : titre sur sa propre ligne, puis les tags.

      ⚠️ L'en-tête vit DANS `.idee-body`, pas au-dessus : le bouton de vote reste
      à gauche de l'ensemble, il n'est pas un tag. `basculable` reste faux — une
      idée ne se déplie pas, elle montre tout. -->
<EnteteCarte titre={idee.titre} date={fmtDateShort(idee.cree_le)}>
<svelte:fragment slot="titre-suffixe">
{#if isNouveau(idee.cree_le, idee.mis_a_jour_le)}<span class="badge badge-gray idee-neuf">New</span>{/if}
</svelte:fragment>
<svelte:fragment slot="tags">
<span class="badge {statutClass(idee.statut)}">{STATUT_IDEE_LABELS[idee.statut] ?? idee.statut}</span>
{#if !estPerimetreParDefaut(idee.perimetre_cible)}<span class="badge badge-gray">&#x1F539; {perimetreLabel(idee.perimetre_cible)}</span>{/if}
</svelte:fragment>
</EnteteCarte>
<div class="idee-desc rich-content clamp-5">{@html safeHtml(idee.description)}</div>
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
<!--  Workflow en PASTILLES, jamais un `<select>` nu (R3, #423). -->
<WorkflowPastilles options={STATUTS_IDEE} valeur={idee.statut}
on:choisir={(e) => changeStatut(idee.id, e.detail)} />
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
<OngletAnnonces
	bind:annonces
	chargement={annoncesLoading}
	bind:showForm={showFormAnnonce}
	bind:expandedAnnonce
	estCS={$isCS}
	estAdmin={$isAdmin}
	currentUserId={$currentUser?.id}
	onSignaler={signaler}
/>
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
.sondage-card { display: flex; justify-content: space-between; align-items: flex-start; padding: 1rem 1.25rem; margin-bottom: .5rem; text-decoration: none; color: var(--color-text); transition: border-color .12s; }
.sondage-card:hover { border-color: var(--color-primary); }
.sondage-actions { display: flex; flex-direction: column; align-items: flex-end; gap: .35rem; flex-shrink: 0; }
.sondage-question { font-size: .95rem; font-weight: 600; display: block; margin-bottom: .2rem; }
.sondage-desc { font-size: .85rem; color: var(--color-text-muted); margin: .2rem 0 .3rem; }
.sondage-votants { font-weight: 600; }
.sondage-ciblage { display: flex; flex-wrap: wrap; gap: .25rem; margin-top: .35rem; }
.sondage-badge { font-size: .7rem; }
.idee-card { display: flex; gap: 1rem; align-items: flex-start; padding: 1rem 1.25rem; margin-bottom: .5rem; }
.vote-btn { display: flex; flex-direction: column; align-items: center; gap: .2rem; background: none; border: 1px solid var(--color-border); border-radius: var(--radius); padding: .5rem .6rem; cursor: pointer; transition: border-color .12s; min-width: 3.5rem; }
.vote-btn:hover { border-color: var(--color-primary); }
.vote-btn.voted { border-color: var(--color-primary); background: var(--color-primary-light); }
.vote-icon { font-size: 1.1rem; }
.vote-count { font-size: .85rem; font-weight: 700; color: var(--color-primary); }
.idee-body { flex: 1; }
.idee-neuf { margin-left: .5em; font-size: .82em; font-weight: 500; vertical-align: middle; }
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
/* Annonces */
</style>