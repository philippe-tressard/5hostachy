<script lang="ts">
import { onMount } from 'svelte';
import { get } from 'svelte/store';
import { api, config as configApi } from '$lib/api';
import { toast } from '$lib/components/Toast.svelte';
import Icon from '$lib/components/Icon.svelte';
import LegalEditor from '$lib/components/LegalEditor.svelte';
import RichEditor from '$lib/components/RichEditor.svelte';
import { safeHtml } from '$lib/sanitize';
import { fmtDatetimeShort as fmt } from '$lib/date';
import { trackTabView } from '$lib/telemetry';

//  Onglets 
let onglet: 'comptes' | 'acces' | 'sauvegardes' | 'emails' | 'utilisateurs' | 'demandes_profil' | 'site' | 'pages' | 'legal' | 'referentiels' | 'whatsapp' | 'smtp' | 'telemetry' = 'comptes';
$: trackTabView(onglet);

//  Bâtiments (pour affichage) 
let batimentsMap: Record<number, string> = {};
async function loadBatiments() {
try {
const list = await api.get<{ id: number; numero: string }[]>('/auth/batiments');
batimentsMap = Object.fromEntries(list.map((b: { id: number; numero: string }) => [b.id, `Bât. ${b.numero}`]));

batimentsList = list;
} catch { /* non bloquant */ }
}

//  Comptes en attente 
let comptes: any[] = [];
let comptesLoading = true;
let refusMotif: Record<number, string> = {};
let refusOpen: Record<number, boolean> = {};

async function loadComptes() {
comptesLoading = true;
try {
comptes = await api.get<any[]>('/admin/comptes-en-attente/enrichis');
} finally {
comptesLoading = false;
}
}

async function validerCompte(id: number) {
try {
const res = await api.post<any>(`/admin/comptes/${id}/traiter`, { action: 'valider' });
const lots = res?.auto_match?.lots_resolus ?? 0;
const lotsMatches = res?.auto_match?.lots ?? 0;
if (lots > 0) {
toast('success', `Compte activé — ${lots} lot(s) résolu(s) automatiquement.`);
} else if (lotsMatches > 0) {
toast('success', `Compte activé — ${lotsMatches} lot(s) trouvé(s) dans l'import (en attente de résolution).`);
} else {
const statut = comptes.find(c => c.user?.id === id)?.user?.statut ?? '';
if (statut.startsWith('copropriétaire')) {
toast('warning', `Compte activé — ⚠️ Aucun lot trouvé dans l'import pour ce copropriétaire.`);
} else {
toast('success', 'Compte activé.');
}
}
comptes = comptes.filter((c) => (c.user?.id ?? c.id) !== id);
} catch (e: any) {
toast('error', e.message ?? 'Erreur');
}
}

async function refuserCompte(id: number) {
try {
await api.post(`/admin/comptes/${id}/traiter`, { action: 'refuser', motif: refusMotif[id] });
toast('info', 'Compte refusé.');
comptes = comptes.filter((c) => (c.user?.id ?? c.id) !== id);
} catch (e: any) {
toast('error', e.message ?? 'Erreur');
}
}

async function relancerAutoMatch(userId: number, userNom: string) {
  try {
    const res = await api.post<any>(`/admin/utilisateurs/${userId}/auto-match`, {});
    const lots = res?.auto_match?.lots_resolus ?? 0;
    const lotsM = res?.auto_match?.lots ?? 0;
    if (lots > 0) toast('success', `${userNom} — ${lots} lot(s) résolu(s) automatiquement.`);
    else if (lotsM > 0) toast('success', `${userNom} — ${lotsM} lot(s) matché(s) (en attente de résolution).`);
    else toast('info', `${userNom} — Aucun import trouvé pour ce nom.`);
    await loadUtilisateurs();
  } catch (e: any) {
    toast('error', e.message ?? 'Erreur auto-match');
  }
}

//  Commandes d'acces 
let commandes: any[] = [];
let commandesLoading = true;
let cmdMotif: Record<number, string> = {};
let cmdRefusOpen: Record<number, boolean> = {};

async function loadCommandes() {
commandesLoading = true;
try {
commandes = await api.get<any[]>('/admin/commandes-acces');
} finally {
commandesLoading = false;
}
}

async function accepterCommande(id: number) {
try {
await api.post(`/admin/commandes-acces/${id}/traiter`, { action: 'accepter' });
toast('success', 'Commande acceptee.');
commandes = commandes.filter((c) => c.id !== id);
} catch (e: any) {
toast('error', e.message ?? 'Erreur');
}
}

async function refuserCommande(id: number) {
try {
await api.post(`/admin/commandes-acces/${id}/traiter`, {
action: 'refuser',
motif_refus: cmdMotif[id],
});
toast('info', 'Commande refusee.');
commandes = commandes.filter((c) => c.id !== id);
} catch (e: any) {
toast('error', e.message ?? 'Erreur');
}
}

//  Sauvegardes 
let historique: any[] = [];
let historiqueLoading = true;
let backupEnCours = false;

async function loadHistorique() {
historiqueLoading = true;
try {
historique = await api.get<any[]>('/admin/sauvegardes/historique');
} finally {
historiqueLoading = false;
}
}

async function declencherSauvegarde() {
backupEnCours = true;
try {
await api.post('/admin/sauvegardes/maintenant');
toast('success', 'Sauvegarde lancee en arriere-plan.');
setTimeout(loadHistorique, 3000);
} catch (e: any) {
toast('error', e.message ?? 'Erreur');
} finally {
backupEnCours = false;
}
}

//  Maintenance cron 
let historiqueMaintenance: any[] = [];
let maintenanceLoading = true;
let maintenanceEnCours = false;

async function loadHistoriqueMaintenance() {
maintenanceLoading = true;
try {
historiqueMaintenance = await api.get<any[]>('/admin/maintenance/historique');
} catch { historiqueMaintenance = []; }
finally { maintenanceLoading = false; }
}

async function declencherMaintenance() {
maintenanceEnCours = true;
try {
await api.post('/admin/maintenance/lancer');
toast('success', 'Maintenance lancée en arrière-plan.');
setTimeout(loadHistoriqueMaintenance, 4000);
} catch (e: any) {
toast('error', e.message ?? 'Erreur');
} finally {
maintenanceEnCours = false;
}
}

//  Télémétrie 
let telemetryData: any = null;
let telemetryLoading = true;
let telemetryAggEnCours = false;
let historiqueTelemetrie: any[] = [];
let telemetryHistLoading = true;
let tlScope: 'jour' | 'mois' | 'annee' = 'jour';

async function loadTelemetry() {
telemetryLoading = true;
try {
telemetryData = await api.get<any>(`/telemetry/dashboard?scope=${tlScope}`);
} catch { telemetryData = null; }
finally { telemetryLoading = false; }
}

function switchTlScope(s: 'jour' | 'mois' | 'annee') {
tlScope = s;
loadTelemetry();
}

async function loadHistoriqueTelemetrie() {
telemetryHistLoading = true;
try {
historiqueTelemetrie = await api.get<any[]>('/admin/telemetry/historique');
} catch { historiqueTelemetrie = []; }
finally { telemetryHistLoading = false; }
}

async function declencherAggregation() {
telemetryAggEnCours = true;
try {
await api.post('/admin/telemetry/agreger');
toast('success', 'Agrégation lancée en arrière-plan.');
setTimeout(() => { loadTelemetry(); loadHistoriqueTelemetrie(); }, 4000);
} catch (e: any) {
toast('error', e.message ?? 'Erreur');
} finally {
telemetryAggEnCours = false;
}
}

//  Modeles e-mail 
let emailTemplates: any[] = [];
let emailsLoading = true;
let emailEdit: any | null = null;
let emailSujet = '';
let emailCorpsHtml = '';
let emailCorpsTexte = '';
let emailActif = true;
let emailSaving = false;
let emailHistory: any[] = [];
let emailHistoryLoading = true;

async function loadEmails() {
emailsLoading = true;
emailHistoryLoading = true;
try {
[emailTemplates, emailHistory] = await Promise.all([
api.get<any[]>('/admin/modeles-email'),
api.get<any[]>('/admin/emails/historique'),
]);
} finally {
emailsLoading = false;
emailHistoryLoading = false;
}
}

function openEmailEdit(tpl: any) {
emailEdit = tpl;
emailSujet = tpl.sujet ?? '';
emailCorpsHtml = tpl.corps_html ?? '';
emailCorpsTexte = tpl.corps_texte ?? '';
emailActif = tpl.actif ?? true;
}

async function saveEmailEdit() {
if (!emailEdit) return;
emailSaving = true;
try {
const updated = await api.patch<any>(`/admin/modeles-email/${emailEdit.id}`, {
sujet: emailSujet,
corps_html: emailCorpsHtml,
corps_texte: emailCorpsTexte,
actif: emailActif,
});
emailTemplates = emailTemplates.map((t) => (t.id === emailEdit.id ? updated : t));
toast('success', 'Modèle mis à jour.');
emailEdit = null;
} catch (e: any) {
toast('error', e.message ?? 'Erreur');
} finally {
emailSaving = false;
}
}

//  Utilisateurs & rôles 
let utilisateurs: any[] = [];
let utilisateursLoading = true;
let userSearch = '';
let userStatutFilter = '';
let userCompteFilter = '';
let roleEnCours: { user: any; role: string; action: 'ajouter' | 'retirer' } | null = null;
let editUser: any | null = null;
let editForm = { nom: '', prenom: '', email: '', telephone: '', societe: '', statut: '', batiment_id: null as number | null, actif: true };
let deleteConfirm: any | null = null;
let batimentsList: { id: number; numero: string }[] = [];

// Validation modal (comptes en attente + Nouvel Arrivant)
let cvModal: { user: any; lotsPrevus: number } | null = null;
let cvNewArrivant = false;
let cvBatiment = '';
let cvAncienResident = '';
let cvSubmitting = false;

function openCompteValidation(item: any) {
  const u = item.user ?? item;
  cvModal = { user: u, lotsPrevus: item.lots_prevus ?? 0 };
  cvNewArrivant = false;
  cvBatiment = u.batiment_id ? (batimentsMap[u.batiment_id] ?? '') : '';
  cvAncienResident = '';
}

async function confirmerCompteValidation() {
  if (!cvModal) return;
  const u = cvModal.user;
  cvSubmitting = true;
  try {
    const res = await api.post<any>(`/admin/comptes/${u.id}/traiter`, { action: 'valider' });
    const lots = res?.auto_match?.lots_resolus ?? 0;
    const lotsMatches = res?.auto_match?.lots ?? 0;
    const aideMatch = res?.auto_match?.aide_match;
    if (aideMatch?.aide_trouve) {
      const parts = [`Compte activé — aidé(e) : ${aideMatch.aide_nom}`];
      if (aideMatch.lots > 0) parts.push(`${aideMatch.lots} lot(s)`);
      if (aideMatch.tc > 0) parts.push(`${aideMatch.tc} TC`);
      if (aideMatch.vigik > 0) parts.push(`${aideMatch.vigik} vigik`);
      if (aideMatch.delegation) parts.push('délégation créée');
      toast('success', parts.join(' — '));
    } else if (aideMatch && !aideMatch.aide_trouve) {
      toast('warning', `Compte activé — ⚠️ Copropriétaire aidé(e) « ${u.prenom_aide ?? ''} ${u.nom_aide ?? ''} » non trouvé(e). Affectation manuelle requise.`);
    } else if (lots > 0) toast('success', `Compte activé — ${lots} lot(s) résolu(s) automatiquement.`);
    else if (lotsMatches > 0) toast('success', `Compte activé — ${lotsMatches} lot(s) trouvé(s) dans l'import.`);
    else if (u.statut?.startsWith('copropriétaire')) toast('warning', 'Compte activé — ⚠️ Aucun lot trouvé dans l\'import.');
    else toast('success', 'Compte activé.');
    comptes = comptes.filter(c => (c.user?.id ?? c.id) !== u.id);
    if (cvNewArrivant) {
      await api.post(`/admin/utilisateurs/${u.id}/accueil-arrivant`, {
        batiment: cvBatiment || null,
        ancien_resident: cvAncienResident || null,
      });
      toast('success', 'Actions d\'accueil envoyées (bienvenue, consignes, demandes syndic/CS).');
    }
    cvModal = null;
  } catch (e: any) {
    toast('error', e.message ?? 'Erreur');
  } finally {
    cvSubmitting = false;
  }
}

// Accueil arrivant (utilisateur existant)
let accueilModal: { user: any } | null = null;
let accueilBatiment = '';
let accueilAncienResident = '';
let accueilSubmitting = false;

function openAccueilModal(u: any) {
  accueilModal = { user: u };
  accueilBatiment = u.batiment_id ? (batimentsMap[u.batiment_id] ?? '') : '';
  accueilAncienResident = '';
}

async function confirmerAccueil() {
  if (!accueilModal) return;
  const u = accueilModal.user;
  accueilSubmitting = true;
  try {
    await api.post(`/admin/utilisateurs/${u.id}/accueil-arrivant`, {
      batiment: accueilBatiment || null,
      ancien_resident: accueilAncienResident || null,
    });
    toast('success', `Actions d'accueil envoyées pour ${u.prenom} ${u.nom}.`);
    accueilModal = null;
  } catch (e: any) {
    toast('error', e.message ?? 'Erreur');
  } finally {
    accueilSubmitting = false;
  }
}

async function loadUtilisateurs() {
utilisateursLoading = true;
try {
utilisateurs = await api.get<any[]>('/admin/utilisateurs');
} finally {
utilisateursLoading = false;
}
}

function demanderRole(u: any, role: string, action: 'ajouter' | 'retirer') {
roleEnCours = { user: u, role, action };
}

async function confirmerRole() {
if (!roleEnCours) return;
const { user, role, action } = roleEnCours;
try {
const endpoint = action === 'ajouter'
? `/admin/utilisateurs/${user.id}/ajouter-role`
: `/admin/utilisateurs/${user.id}/retirer-role`;
const updated = await api.post<any>(endpoint, { role });
toast('success', `Rôle ${roleLabels[role] ?? role} ${action === 'ajouter' ? 'ajouté à' : 'retiré de'} ${user.prenom} ${user.nom}.`);
utilisateurs = utilisateurs.map((u) => u.id === user.id ? { ...u, ...updated } : u);
} catch (e: any) {
toast('error', e.message ?? 'Erreur');
} finally {
roleEnCours = null;
}
}

function openEdit(u: any) {
editForm = { nom: u.nom, prenom: u.prenom, email: u.email, telephone: u.telephone ?? '', societe: u.societe ?? '', statut: u.statut, batiment_id: u.batiment_id ?? null, actif: u.actif };
editUser = u;
}

async function saveEdit() {
if (!editUser) return;
try {
const updated = await api.patch<any>(`/admin/utilisateurs/${editUser.id}`, editForm);
utilisateurs = utilisateurs.map((u) => u.id === editUser!.id ? { ...u, ...updated } : u);
toast('success', 'Utilisateur mis à jour.');
editUser = null;
} catch (e: any) {
toast('error', e.message ?? 'Erreur');
}
}

async function confirmerDelete() {
if (!deleteConfirm) return;
const target = deleteConfirm;
deleteConfirm = null;
try {
await api.delete(`/admin/utilisateurs/${target.id}`);
utilisateurs = utilisateurs.filter((u) => u.id !== target.id);
toast('success', `${target.prenom} ${target.nom} supprimé.`);
} catch (e: any) {
toast('error', e.message ?? 'Erreur');
}
}

async function toggleBanCommunaute(u: any) {
const isBanned = u.communaute_interdit || (u.communaute_ban_jusqu_au && new Date(u.communaute_ban_jusqu_au) > new Date());
const interdit = !isBanned;
try {
const updated = await api.patch<any>(`/admin/utilisateurs/${u.id}/ban-communaute`, { interdit });
utilisateurs = utilisateurs.map(x => x.id === u.id ? { ...x, ...updated } : x);
if (interdit) {
  const msg = updated.communaute_interdit
    ? `${u.prenom} ${u.nom} banni définitivement de la communauté.`
    : `${u.prenom} ${u.nom} banni de la communauté pour 1 mois (probatoire).`;
  toast('success', msg);
} else {
  toast('success', `${u.prenom} ${u.nom} réautorisé à la communauté.`);
}
} catch (e: any) {
toast('error', e.message ?? 'Erreur');
}
}

$: nbCS = utilisateurs.filter((u) => (u.roles ?? [u.role]).includes('conseil_syndical')).length;

$: filteredUsers = utilisateurs
  .filter((u) => {
    if (userStatutFilter && u.statut !== userStatutFilter) return false;
    if (userCompteFilter === 'actif' && !u.actif) return false;
    if (userCompteFilter === 'inactif' && u.actif) return false;
    if (!userSearch.trim()) return true;
    const q = userSearch.toLowerCase();
    return (
      (u.prenom + ' ' + u.nom).toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q)
    );
  })
  .sort((a, b) => {
    const nomCmp = (a.nom ?? '').localeCompare(b.nom ?? '', 'fr', { sensitivity: 'base' });
    if (nomCmp !== 0) return nomCmp;
    return (a.prenom ?? '').localeCompare(b.prenom ?? '', 'fr', { sensitivity: 'base' });
  });

const roleLabels: Record<string, string> = {
  propriétaire: 'Propriétaire',
  résident: 'Résident',
  externe: 'Externe',
  conseil_syndical: 'Conseil syndical',
  admin: 'Admin',
  // legacy / compat
  locataire: 'Locataire',
  'copropriétaire_résident': 'Copropriétaire Résident',
  'copropriétaire_bailleur': 'Copropriétaire Bailleur',
  bailleur: 'Copropriétaire Bailleur',
  syndic: 'Syndic',
  mandataire: 'Mandataire',
};

const roleBadgeClass: Record<string, string> = {
  propriétaire: 'badge-teal',
  résident: 'badge-gray',
  externe: 'badge-yellow',
  conseil_syndical: 'badge-blue',
  admin: 'badge-orange',
  // legacy
  locataire: 'badge-gray',
  'copropriétaire_résident': 'badge-teal',
  'copropriétaire_bailleur': 'badge-purple',
  bailleur: 'badge-purple',
  syndic: 'badge-orange',
  mandataire: 'badge-yellow',
};

const statutLabels: Record<string, string> = {
  'copropriétaire_résident': 'Copro. résident',
  'copropriétaire_bailleur': 'Copro. bailleur',
  locataire: 'Locataire',
  syndic: 'Syndic',
  mandataire: 'Mandataire',
  aidant: 'Aidant (proche)',
  admin_technique: 'Admin technique',
};

const statutBadgeClass: Record<string, string> = {
  'copropriétaire_résident': 'badge-green',
  'copropriétaire_bailleur': 'badge-blue',
  locataire: 'badge-purple',
  syndic: 'badge-orange',
  mandataire: 'badge-gray',
  aidant: 'badge-yellow',
  admin_technique: 'badge-orange',
};

function userRoles(u: any): string[] {
return u.roles?.length ? u.roles : [u.role];
}

// Rôles actifs : affiche les rôles réels (P·R·E·CS·A) depuis u.roles
function displayRoles(u: any): { label: string; cls: string }[] {
  const roles: string[] = u.roles?.length ? u.roles : [u.role];
  return roles.map((r: string) => ({
    label: roleLabels[r] ?? r,
    cls: roleBadgeClass[r] ?? 'badge-gray',
  }));
}

function userBatimentLabel(u: any): string {
  if (u.batiment_id && batimentsMap[u.batiment_id]) return batimentsMap[u.batiment_id];
  if (u.batiment_nom) return u.batiment_nom;
  if (u.batiment_id) return `Bât. ${u.batiment_id}`;
  return '—';
}

//  Demandes de modification de profil 
let demandesProfil: any[] = [];
let demandesProfilLoading = true;
let refusDemande: Record<number, string> = {};
let refusDemandeOpen: Record<number, boolean> = {};

const statutDemandeLabel: Record<string, string> = {
	en_attente: 'En attente',
	approuvee: 'Approvée',
	rejetee: 'Rejetée',
};

const statutLabelsAdmin: Record<string, string> = {
	'copropriétaire_résident': 'Copro. résident',
	'copropriétaire_bailleur': 'Copro. bailleur',
	locataire: 'Locataire',
	syndic: 'Syndic',
	mandataire: 'Mandataire',
	aidant: 'Aidant (proche)',
};

async function loadDemandesProfil() {
	demandesProfilLoading = true;
	try {
		demandesProfil = await api.get<any[]>('/admin/demandes-profil');
	} catch { /* ignore */ } finally {
		demandesProfilLoading = false;
	}
}

async function approuverDemande(id: number) {
	try {
		await api.post(`/admin/demandes-profil/${id}/traiter`, { action: 'approuver' });
		toast('success', 'Demande approuvée.');
		demandesProfil = demandesProfil.filter((d) => d.id !== id);
	} catch (e: any) {
		toast('error', e.message ?? 'Erreur');
	}
}

async function rejeterDemande(id: number) {
	try {
		await api.post(`/admin/demandes-profil/${id}/traiter`, {
			action: 'rejeter',
			motif_refus: refusDemande[id] || null,
		});
		toast('info', 'Demande rejetée.');
		demandesProfil = demandesProfil.filter((d) => d.id !== id);
	} catch (e: any) {
		toast('error', e.message ?? 'Erreur');
	} finally {
		refusDemandeOpen[id] = false;
	}
}

//  Montage 
onMount(async () => {
await loadSiteConfig();
// Paramétrage site — lu depuis le store (chargé par layout ou par fetch client)
const cfg = get(configStore) as Record<string, string>;
// Les clés légales sont exclues de /api/config (perf) — fetch dédié
let sMentions = '';
let sPolitique = '';
try {
  const r = await fetch('/api/config/legal');
  if (r.ok) { const legal = await r.json(); sMentions = legal['mentions_legales'] ?? ''; sPolitique = legal['politique_confidentialite'] ?? ''; }
} catch { /**/ }
siteConfig = {
  nom: cfg['site_nom'] ?? '5Hostachy',
  url: cfg['site_url'] ?? '',
  email_admin: cfg['site_email'] ?? '',
  login_sous_titre: cfg['login_sous_titre'] ?? 'Votre espace numérique de résidence',
  mentions_legales: sMentions,
  politique_confidentialite: sPolitique,
  archivage_delai_heures: parseInt(cfg['archivage_delai_heures'] ?? '48') || 48,
  notify_ticket_bug_email: cfg['notify_ticket_bug_email'] === '1',
  notify_new_user_created_email: cfg['notify_new_user_created_email'] === '1',
  site_manager_user_id: cfg['site_manager_user_id'] ?? '',
  whatsapp_footer: cfg['whatsapp_footer'] ?? '— Le Conseil Syndical',
  email_footer: cfg['email_footer'] ?? '— Envoyé depuis 5hostachy.fr',
  reference_copro: cfg['reference_copro'] ?? '',
};
// Config des pages
pagesConfig = pagesDefaults.map(pg => {
  const s = cfg[`page_config_${pg.id}`];
  if (s) { try {
    const saved = normalizeSavedPageDef(JSON.parse(s), pg);
    const mergedOnglets = pg.onglets?.map(o => { const so = saved.onglets?.[o.id]; if (typeof so === 'string') return { ...o, label: so }; return { id: o.id, label: so?.label ?? o.label, descriptif: so?.descriptif ?? o.descriptif }; });
    return { ...pg, ...saved, onglets: mergedOnglets ?? pg.onglets };
  } catch { /**/ } }
  return { ...pg };
});
// Restaurer l'ordre personnalisé depuis le backend
const savedOrder = cfg['pages_order'];
if (savedOrder) { try {
  const ids: string[] = JSON.parse(savedOrder);
  const map = Object.fromEntries(pagesConfig.map(p => [p.id, p]));
  pagesConfig = [...ids.map(id => map[id]).filter(Boolean), ...pagesConfig.filter(p => !ids.includes(p.id))];
} catch { /**/ } }
// Référentiels
referentiels = referentielsDefaults.map(ref => {
  const s = localStorage.getItem(`ref_${ref.id}`);
  if (s) { try { return { ...ref, items: JSON.parse(s) }; } catch { /**/ } }
  return { ...ref, items: [...ref.items] };
});
// WhatsApp config
waConfig.enabled = cfg['whatsapp_enabled'] === '1';
waConfig.group_name = cfg['whatsapp_group_name'] ?? '';
waConfig.api_url = cfg['whatsapp_api_url'] ?? '';
waConfig.group_jid = cfg['whatsapp_group_jid'] ?? '';
try {
  const adminCfg = await api.get<Record<string, string>>('/config/admin');
  waApiKeySet = !!(adminCfg['whatsapp_api_key']);
  // SMTP config
  smtpConfig.enabled = adminCfg['smtp_enabled'] === '1';
  smtpConfig.server = adminCfg['smtp_server'] ?? '';
  smtpConfig.port = parseInt(adminCfg['smtp_port'] ?? '587') || 587;
  smtpConfig.from = adminCfg['smtp_from'] ?? '';
  smtpConfig.from_name = adminCfg['smtp_from_name'] ?? '';
  smtpConfig.username = adminCfg['smtp_username'] ?? '';
  smtpConfig.starttls = adminCfg['smtp_starttls'] !== '0';
  smtpConfig.ssl_tls = adminCfg['smtp_ssl_tls'] === '1';
  smtpPasswordSet = !!(adminCfg['smtp_password']);
  smtpEditingPassword = !smtpPasswordSet;
} catch { /**/ }
loadBatiments();
loadComptes();
loadCommandes();
loadHistorique();
loadHistoriqueMaintenance();
loadEmails();
loadDemandesProfil();
loadWaScheduled();
loadWaLogs();
loadTelemetry();
loadHistoriqueTelemetrie();
});

function statutBadge(s: string) {
const map: Record<string, string> = {
succes: 'badge-green', erreur: 'badge-red', echec: 'badge-red', en_cours: 'badge-orange',
};
return map[s] ?? 'badge-gray';
}

// ── Paramétrage site ──────────────────────────────────────────
let siteConfig = { nom: '5Hostachy', url: '', email_admin: '', login_sous_titre: 'Votre espace numérique de résidence', mentions_legales: '', politique_confidentialite: '', archivage_delai_heures: 48, notify_ticket_bug_email: false, notify_new_user_created_email: false, site_manager_user_id: '', whatsapp_footer: '— Le Conseil Syndical', email_footer: '— Envoyé depuis 5hostachy.fr', reference_copro: '' };
let siteSaving = false;
$: siteManagerUsers = utilisateurs.filter((u) => !!u.email);
function openSiteTab() {
  onglet = 'site';
  if (utilisateurs.length === 0) loadUtilisateurs();
}
async function saveSiteConfig() {
  siteSaving = true;
  try {
    await configApi.save({ site_nom: siteConfig.nom, site_url: siteConfig.url, site_email: siteConfig.email_admin, login_sous_titre: siteConfig.login_sous_titre, mentions_legales: siteConfig.mentions_legales, politique_confidentialite: siteConfig.politique_confidentialite, archivage_delai_heures: String(siteConfig.archivage_delai_heures), notify_ticket_bug_email: siteConfig.notify_ticket_bug_email ? '1' : '0', notify_new_user_created_email: siteConfig.notify_new_user_created_email ? '1' : '0', site_manager_user_id: siteConfig.site_manager_user_id || '', whatsapp_footer: siteConfig.whatsapp_footer, email_footer: siteConfig.email_footer, reference_copro: siteConfig.reference_copro });
    configStore.update((c: Record<string, string>) => ({ ...c, site_nom: siteConfig.nom, site_url: siteConfig.url, site_email: siteConfig.email_admin, login_sous_titre: siteConfig.login_sous_titre, mentions_legales: siteConfig.mentions_legales, politique_confidentialite: siteConfig.politique_confidentialite, archivage_delai_heures: String(siteConfig.archivage_delai_heures), notify_ticket_bug_email: siteConfig.notify_ticket_bug_email ? '1' : '0', notify_new_user_created_email: siteConfig.notify_new_user_created_email ? '1' : '0', site_manager_user_id: siteConfig.site_manager_user_id || '' }));
    toast('success', 'Paramètres sauvegardés.');
  } catch (e: any) {
    toast('error', e.message ?? 'Erreur lors de la sauvegarde.');
  } finally {
    siteSaving = false;
  }
}

// ── WhatsApp ──────────────────────────────────────────────────
let waConfig = { enabled: false, group_name: '', api_url: '', api_key: '', group_jid: '' };
let waSaving = false;
let waApiKeySet = false;
let waTestMessage = '🧪 Test WhatsApp — si vous recevez ce message, la configuration est correcte ✅';
let waTesting = false;
let waStatus: { state: string; hasQR: boolean } | null = null;
let waStatusLoading = false;
// Messages planifiés
let waScheduled: { id: number; label: string; message: string; cron_rule: string; enabled: boolean; mis_a_jour_le: string | null }[] = [];
let waScheduledSaving: Record<number, boolean> = {};
let waLogs: { id: number; label: string; message: string; statut: string; erreur: string | null; envoye_le: string | null }[] = [];
async function loadWaScheduled() {
  try { waScheduled = await api.get('/config/whatsapp-scheduled'); } catch { /**/ }
}
async function loadWaLogs() {
  try { waLogs = await api.get('/config/whatsapp-logs'); } catch { /**/ }
}
async function saveWaScheduledItem(item: typeof waScheduled[0]) {
  waScheduledSaving = { ...waScheduledSaving, [item.id]: true };
  try {
    await api.put(`/config/whatsapp-scheduled/${item.id}`, { label: item.label, message: item.message, cron_rule: item.cron_rule, enabled: item.enabled });
    toast('success', `Message « ${item.label} » enregistré.`);
  } catch (e: any) { toast('error', e.message ?? 'Erreur'); }
  finally { waScheduledSaving = { ...waScheduledSaving, [item.id]: false }; }
}
async function sendWaTest() {
  if (!waTestMessage.trim()) return;
  waTesting = true;
  try {
    await api.post('/config/whatsapp-test', { message: waTestMessage });
    toast('success', 'Message de test envoyé sur le groupe WhatsApp.');
    loadWaLogs();
  } catch (e: any) {
    toast('error', e.message ?? 'Échec de l\'envoi');
  } finally {
    waTesting = false;
  }
}
async function checkWaStatus() {
  waStatusLoading = true;
  try {
    waStatus = await api.get('/config/whatsapp-status');
  } catch (e: any) {
    waStatus = null;
    toast('error', e.message ?? 'Impossible de joindre le bridge');
  } finally {
    waStatusLoading = false;
  }
}
async function saveWaConfig() {
  waSaving = true;
  try {
    const payload: Record<string, string> = {
      whatsapp_enabled: waConfig.enabled ? '1' : '0',
      whatsapp_group_name: waConfig.group_name,
      whatsapp_api_url: waConfig.api_url,
      whatsapp_group_jid: waConfig.group_jid,
    };
    if (waConfig.api_key) payload['whatsapp_api_key'] = waConfig.api_key;
    await configApi.save(payload);
    configStore.update((c: Record<string, string>) => ({ ...c, whatsapp_enabled: waConfig.enabled ? '1' : '0', whatsapp_group_name: waConfig.group_name, whatsapp_api_url: waConfig.api_url, whatsapp_group_jid: waConfig.group_jid }));
    if (waConfig.api_key) waApiKeySet = true;
    waConfig.api_key = '';
    toast('success', 'Configuration WhatsApp enregistrée.');
  } catch (e: any) {
    toast('error', e.message ?? 'Erreur');
  } finally {
    waSaving = false;
  }
}

// ── SMTP ────────────────────────────────────────────────────
let smtpConfig = { enabled: false, server: '', port: 587, from: '', from_name: '', username: '', password: '', starttls: true, ssl_tls: false };
let smtpSaving = false;
let smtpPasswordSet = false;
let smtpEditingPassword = true;
let smtpTestEmail = '';
let smtpTesting = false;
async function saveSmtpConfig() {
  smtpSaving = true;
  try {
    const payload: Record<string, string> = {
      smtp_enabled: smtpConfig.enabled ? '1' : '0',
      smtp_server: smtpConfig.server,
      smtp_port: String(smtpConfig.port),
      smtp_from: smtpConfig.from,
      smtp_from_name: smtpConfig.from_name,
      smtp_username: smtpConfig.username,
      smtp_starttls: smtpConfig.starttls ? '1' : '0',
      smtp_ssl_tls: smtpConfig.ssl_tls ? '1' : '0',
      email_footer: siteConfig.email_footer,
      reference_copro: siteConfig.reference_copro,
    };
    if (smtpConfig.password) payload['smtp_password'] = smtpConfig.password;
    await configApi.save(payload);
    if (smtpConfig.password) {
      smtpPasswordSet = true;
      smtpEditingPassword = false;
    }
    smtpConfig.password = '';
    toast('success', 'Configuration SMTP enregistrée.');
  } catch (e: any) {
    toast('error', e.message ?? 'Erreur');
  } finally {
    smtpSaving = false;
  }
}
async function sendSmtpTest() {
  if (!smtpTestEmail) return;
  smtpTesting = true;
  try {
    await api.post('/config/smtp-test', { email: smtpTestEmail });
    toast('success', `E-mail de test envoyé à ${smtpTestEmail}`);
  } catch (e: any) {
    toast('error', e.message ?? 'Échec de l\'envoi');
  } finally {
    smtpTesting = false;
  }
}

// ── Descriptif des pages ──────────────────────────────────────
type PageDef = { id: string; nom: string; titre: string; descriptif: string; navLabel: string; icone: string; onglets?: { id: string; label: string; descriptif: string }[] };
function stripHtmlPreview(html: string) {
  return (html ?? '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}
function normalizeSavedPageDef(saved: any, defaults: PageDef) {
  const normalized = { ...saved, onglets: saved?.onglets ? { ...saved.onglets } : undefined };
  if (normalized.onglets) {
    for (const [k, v] of Object.entries(normalized.onglets)) {
      if (typeof v === 'string') {
        (normalized.onglets as any)[k] = { label: v, descriptif: defaults.onglets?.find(o => o.id === k)?.descriptif ?? '' };
      }
    }
  }
  if (defaults.id === 'prestataires') {
    if (normalized.onglets?.consommation && !normalized.onglets?.consommations) {
      normalized.onglets.consommations = normalized.onglets.consommation;
      delete normalized.onglets.consommation;
    }
  }
  if (defaults.id === 'espace-cs') {
    if (normalized.onglets?.validations?.label === '✅ Validations') {
      normalized.onglets.validations.label = defaults.onglets?.find(o => o.id === 'validations')?.label ?? normalized.onglets.validations.label;
    }
    if (normalized.onglets?.validations?.descriptif === 'Comptes en attente de validation et demandes d\'accès à traiter.') {
      normalized.onglets.validations.descriptif = defaults.onglets?.find(o => o.id === 'validations')?.descriptif ?? normalized.onglets.validations.descriptif;
    }
  }
  return normalized;
}
const pagesDefaults: PageDef[] = [
  { id: 'tableau-de-bord', nom: 'Tableau de bord',      titre: 'Tableau de bord',           navLabel: 'Accueil',        icone: 'layout-dashboard',    descriptif: "Votre espace numérique de résidence : actualités, demandes, accès et gouvernance de votre copropriété en un seul endroit." },
  { id: 'actualites',      nom: 'Actualités',           titre: 'Actualités',                navLabel: 'Actualités',     icone: 'newspaper',           descriptif: "Publications officielles du conseil syndical : informations importantes, travaux et actualités de la résidence." },
  { id: 'calendrier',      nom: 'Calendrier',           titre: 'Calendrier',                navLabel: 'Calendrier',     icone: 'calendar-days',       descriptif: "Agenda des événements et interventions de la résidence.",
    onglets: [{ id: 'liste', label: '\u{1F4CB} Liste', descriptif: 'Vue chronologique des événements à venir.' }, { id: 'kanban', label: '\u{1F5C3}️ Kanban', descriptif: 'Organisation visuelle des événements par statut.' }, { id: 'archives', label: '\u{1F4C1} Archives', descriptif: 'Événements passés classés par année.' }] },
  { id: 'mes-demandes',    nom: 'Tickets',              titre: 'Mes Tickets',               navLabel: 'Tickets',        icone: 'message-square-text', descriptif: "Signalez un problème, une nuisance ou posez une question au conseil syndical. Suivez l'avancement de vos tickets." },
  { id: 'annuaire',        nom: 'Annuaire',             titre: 'Annuaire',                  navLabel: 'Annuaire',       icone: 'users',               descriptif: "Coordonnées des membres du Conseil Syndical et du Syndic. En cas d'urgence, contactez le syndic directement par téléphone. Sinon, faites une demande depuis la plateforme." },
  { id: 'residence',       nom: 'Ma résidence',         titre: 'Ma résidence',              navLabel: 'Résidence',      icone: 'building-2',          descriptif: "Documents et informations de la copropriété." },
  { id: 'mon-lot',         nom: 'Mes lots',             titre: 'Mes lots',                  navLabel: 'Mes lots',       icone: 'door-closed',         descriptif: "Informations sur votre bien : situation de vos lots (appartement, cave & parkings) dans la résidence et gestion locative pour les copropriétaires mandataires.",
    onglets: [{ id: 'lots', label: '\u{1F3E0} Mes lots', descriptif: 'Situation de vos lots dans la résidence : appartements, caves et parkings.' }, { id: 'location', label: '\u{1F4CB} Gestion locative', descriptif: 'Suivi de vos baux, locataires et documents de gestion locative.' }] },
  { id: 'acces-badges',    nom: 'Accès & badges',       titre: 'Accès & badges',            navLabel: 'Accès & badges', icone: 'key-round',           descriptif: "Gestion de vos télécommandes parkings & Vigiks." },
  { id: 'prestataires',    nom: 'Prestataires',         titre: 'Prestataires',              navLabel: 'Prestataires',   icone: 'hard-hat',            descriptif: "Intervenants de la résidence et leurs contrats de maintenance (avec synthèse IA du contrat) et documents contractuels.",
    onglets: [{ id: 'prestataires', label: '\u{1F527} Prestataires', descriptif: 'Intervenants et contrats d\'entretien de la résidence.' }, { id: 'consommations', label: '\u{1F4A7} Consommations', descriptif: 'Suivi des relevés de compteurs et abonnements de la résidence.' }, { id: 'devis', label: '\u{1F4CB} Prestations', descriptif: 'Demandes de devis, prestations ponctuelles et suivi des interventions.' }] },
  { id: 'communaute',      nom: 'Communauté',           titre: 'Communauté',                navLabel: 'Communauté',     icone: 'users-round',         descriptif: "Sondages et boîte à idées pour contribuer à la vie de la résidence.",
    onglets: [{ id: 'sondages', label: '\u{1F4CA} Sondages', descriptif: 'Participez aux votes et consultations de la copropriété.' }, { id: 'idees', label: '\u{1F4A1} Boîte à idées', descriptif: 'Proposez et soutenez des idées pour améliorer la vie en résidence.' }] },
  { id: 'faq',             nom: 'FAQ',                  titre: 'FAQ',                       navLabel: 'FAQ',            icone: 'help-circle',         descriptif: "Réponses aux questions fréquentes sur la vie en résidence, les services et la réglementation de la copropriété." },
  { id: 'espace-cs',       nom: 'Espace CS',            titre: 'Espace Conseil Syndical (CS)', navLabel: 'Espace CS',      icone: 'shield-half',         descriptif: "Tableau de bord des membres du Conseil Syndical (CS) : suivi des comptes, tickets résidence et demandes d'accès — réservé au Conseil Syndical.",
    onglets: [{ id: 'validations', label: '✅ Comptes & accès', descriptif: 'Comptes en attente, demandes d\'accès et validations à traiter.' }, { id: 'tickets', label: '\u{1F3AB} Tickets résidence', descriptif: 'Tous les tickets de la résidence, avec le demandeur, son bâtiment et le suivi de traitement.' }, { id: 'annuaire', label: '\u{1F4D2} Annuaire CS & Syndic', descriptif: 'Coordonnées des membres du CS et du syndic.' }] },
  { id: 'admin',           nom: 'Paramétrage',          titre: 'Paramétrage',               navLabel: 'Admin',          icone: 'sliders-horizontal',  descriptif: "Administration de la plateforme : comptes, utilisateurs, rôles, modèles e-mail, paramétrage et référentiels — réservés aux admins." },
  { id: 'profil',          nom: 'Mon profil',           titre: 'Mon profil',                navLabel: 'Profil',         icone: 'user',                descriptif: "Vos informations personnelles (mot de passe, lots...), sécurité du compte et préférences de notifications." },
  { id: 'notifications',   nom: 'Notifications',        titre: 'Notifications',             navLabel: 'Notifications',  icone: 'bell',                descriptif: "Vos alertes et messages." },
];
let pagesConfig: PageDef[] = pagesDefaults.map(pg => ({ ...pg }));
let expandedPages = new Set<string>();
function togglePage(id: string) {
  expandedPages = expandedPages.has(id) ? new Set() : new Set([id]);
}
async function savePageConfig(pg: PageDef) {
  const ongletsRecord = pg.onglets ? Object.fromEntries(pg.onglets.map(o => [o.id, { label: o.label, descriptif: o.descriptif }])) : undefined;
  const val = JSON.stringify({ titre: pg.titre, descriptif: pg.descriptif, navLabel: pg.navLabel, icone: pg.icone, ...(ongletsRecord ? { onglets: ongletsRecord } : {}) });
  try {
    await configApi.save({ [`page_config_${pg.id}`]: val });
    configStore.update((c: Record<string, string>) => ({ ...c, [`page_config_${pg.id}`]: val }));
    toast('success', 'Configuration enregistrée.');
  } catch (e: any) {
    toast('error', e.message ?? 'Erreur lors de la sauvegarde.');
  }
}
async function movePage(i: number, dir: number) {
  const arr = [...pagesConfig];
  const j = i + dir;
  if (j < 0 || j >= arr.length) return;
  [arr[i], arr[j]] = [arr[j], arr[i]];
  pagesConfig = arr;
  const ordered = JSON.stringify(pagesConfig.map(p => p.id));
  configStore.update((c: Record<string, string>) => ({ ...c, pages_order: ordered }));
  try {
    await configApi.save({ pages_order: ordered });
  } catch (e: any) {
    toast('error', e.message ?? "Erreur lors de la sauvegarde de l'ordre.");
  }
}

// ── Référentiels ──────────────────────────────────────────────
type RefItem = { id: string; label: string };
type Referentiel = { id: string; nom: string; items: RefItem[] };
const referentielsDefaults: Referentiel[] = [
  { id: 'prestataire_specialites', nom: 'Spécialités prestataires', items: [
    { id: 'ascenseur', label: 'Ascenseur' }, { id: 'eau', label: 'Eau' },
    { id: 'espaces_verts', label: 'Espaces verts' }, { id: 'electricite', label: 'Électricité' },
    { id: 'toits', label: 'Toits' }, { id: 'vmc', label: 'VMC' },
    { id: 'chauffage', label: 'Chauffage' }, { id: 'securite', label: 'Sécurité' },
    { id: 'autre', label: 'Autre' },
  ]},
  { id: 'calendrier_categories', nom: 'Catégories du calendrier', items: [
    { id: 'reunion', label: 'Réunion' }, { id: 'travaux', label: 'Travaux' },
    { id: 'evenement', label: 'Événement' }, { id: 'permanence', label: 'Permanence' },
  ]},
  { id: 'ticket_statuts', nom: 'Statuts des demandes (tickets)', items: [
    { id: 'ouvert', label: 'Ouvert' }, { id: 'en_cours', label: 'En cours' },
    { id: 'resolu', label: 'Résolu' }, { id: 'ferme', label: 'Fermé' },
  ]},
  { id: 'ticket_categories', nom: 'Catégories des demandes (tickets)', items: [
    { id: 'panne', label: 'Panne' }, { id: 'nuisance', label: 'Nuisance' },
    { id: 'question', label: 'Question' }, { id: 'urgence', label: 'Urgence' },
  ]},
];
let referentiels: Referentiel[] = referentielsDefaults.map(ref => ({ ...ref, items: [...ref.items] }));
let expandedRefs = new Set<string>();
function toggleRef(id: string) {
  expandedRefs = expandedRefs.has(id) ? new Set() : new Set([id]);
}
let refNewItem: Record<string, string> = Object.fromEntries(referentielsDefaults.map(r => [r.id, '']));
function addRefItem(refId: string) {
  const label = (refNewItem[refId] ?? '').trim();
  if (!label) return;
  const ref = referentiels.find(r => r.id === refId);
  if (!ref) return;
  const newId = label.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '_');
  ref.items = [...ref.items, { id: newId, label }];
  referentiels = referentiels;
  refNewItem = { ...refNewItem, [refId]: '' };
  localStorage.setItem(`ref_${refId}`, JSON.stringify(ref.items));
}
function removeRefItem(refId: string, itemId: string) {
  const ref = referentiels.find(r => r.id === refId);
  if (!ref) return;
  ref.items = ref.items.filter(i => i.id !== itemId);
  referentiels = referentiels;
  localStorage.setItem(`ref_${refId}`, JSON.stringify(ref.items));
}
import { getPageConfig, configStore, siteNomStore, loadSiteConfig } from '$lib/stores/pageConfig';
$: _pc = getPageConfig($configStore, 'admin', { titre: 'Paramétrage', navLabel: 'Admin', descriptif: 'Administration de la plateforme : comptes, utilisateurs, rôles, modèles e-mail, paramétrage et référentiels — réservés aux admins.' });
$: _siteNom = $siteNomStore;
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<div class="page-header">
<h1 style="display:flex;align-items:center;gap:.4rem"><Icon name={_pc.icone || 'sliders-horizontal'} size={20} />{_pc.titre}</h1>
</div>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

<div class="tabs-group">
  <div class="tabs-group-label">&#x1F465; Gestion utilisateurs</div>
  <div class="tabs">
    <button class="tab-btn" class:active={onglet === 'comptes'} on:click={() => (onglet = 'comptes')}>
      Comptes en attente
      {#if comptes.length > 0}<span class="badge-count">{comptes.length}</span>{/if}
    </button>
    <button class="tab-btn" class:active={onglet === 'acces'} on:click={() => (onglet = 'acces')}>
      Commandes d'accès
      {#if commandes.length > 0}<span class="badge-count">{commandes.length}</span>{/if}
    </button>
    <button class="tab-btn" class:active={onglet === 'utilisateurs'} on:click={() => { onglet = 'utilisateurs'; loadUtilisateurs(); }}>
      Utilisateurs
    </button>
    <button class="tab-btn" class:active={onglet === 'demandes_profil'} on:click={() => (onglet = 'demandes_profil')}>
      Demandes profil
      {#if demandesProfil.length > 0}<span class="badge-count">{demandesProfil.length}</span>{/if}
    </button>
    <button class="tab-btn" class:active={onglet === 'emails'} on:click={() => (onglet = 'emails')}>
      Modèles e-mail
    </button>
    <a href="/admin/lots-import" class="tab-btn" style="text-decoration:none">Import Lots</a>
    <a href="/admin/telecommandes-import" class="tab-btn" style="text-decoration:none">Import TC</a>
    <a href="/admin/vigiks-import" class="tab-btn" style="text-decoration:none">Import Vigik</a>
    <a href="/admin/audit-lots" class="tab-btn" style="text-decoration:none">Audit lots</a>
  </div>
</div>

<div class="tabs-group" style="margin-top:.5rem;margin-bottom:1.5rem">
  <div class="tabs-group-label">⚙️ Configuration</div>
  <div class="tabs" style="margin-bottom:0">
    <button class="tab-btn" class:active={onglet === 'site'} on:click={openSiteTab}>
      Paramétrage site
    </button>
    <button class="tab-btn" class:active={onglet === 'pages'} on:click={() => (onglet = 'pages')}>
      Descriptif pages
    </button>
    <button class="tab-btn" class:active={onglet === 'legal'} on:click={() => (onglet = 'legal')}>
      Pages légales
    </button>
    <button class="tab-btn" class:active={onglet === 'referentiels'} on:click={() => (onglet = 'referentiels')}>
      Référentiels
    </button>
    <button class="tab-btn" class:active={onglet === 'whatsapp'} on:click={() => (onglet = 'whatsapp')}>
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="#25D366" style="flex-shrink:0"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.570-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
      WhatsApp
    </button>
    <button class="tab-btn" class:active={onglet === 'smtp'} on:click={() => (onglet = 'smtp')}>
      ✉️ SMTP
    </button>
    <button class="tab-btn" class:active={onglet === 'telemetry'} on:click={() => { onglet = 'telemetry'; loadTelemetry(); loadHistoriqueTelemetrie(); }}>
      📊 Télémétrie
    </button>
  </div>
</div>

{#if onglet === 'comptes'}
{#if comptesLoading}
<p class="muted">Chargement...</p>
{:else if comptes.length === 0}
<div class="empty-state">
<h3>Aucun compte en attente</h3>
<p>Tous les comptes ont ete traites.</p>
</div>
{:else}
<div class="card" style="overflow:hidden">
<table class="table">
<thead>
<tr>
<th>Nom</th><th>Statut</th><th>Rôle(s)</th><th>Bât.</th><th>Lots import</th><th>Inscription</th><th>Actions</th>
</tr>
</thead>
<tbody>
{#each comptes as item}
{@const u = item.user ?? item}
<tr>
<td style="font-weight:500">{u.prenom} {u.nom}
{#if u.statut === 'locataire' && u.nom_proprietaire}
  <div style="font-size:.75rem;color:var(--color-text-muted);margin-top:.15rem">&#x1F464; Prop. : {u.nom_proprietaire}</div>
{/if}
{#if (u.statut === 'aidant' || u.statut === 'mandataire') && u.nom_aide}
  <div style="font-size:.75rem;color:var(--color-text-muted);margin-top:.15rem">&#x1F464; Aidé : {u.prenom_aide} {u.nom_aide}</div>
{/if}
</td>
<td><span class="badge {statutBadgeClass[u.statut] ?? 'badge-gray'}" style="font-size:.75rem">{statutLabels[u.statut] ?? u.statut}</span></td>
<td>
  <div style="display:flex;gap:.25rem;flex-wrap:wrap">
    {#each (u.roles?.length ? u.roles : [u.role]) as r}
      <span class="badge {roleBadgeClass[r] ?? 'badge-gray'}" style="font-size:.75rem">{roleLabels[r] ?? r}</span>
    {/each}
  </div>
</td>
<td style="color:var(--color-text-muted)">{u.batiment_id ? (batimentsMap[u.batiment_id] ?? `#${u.batiment_id}`) : '—'}</td>
<td>
{#if item.lots_prevus > 0}
<span class="badge badge-success" title="{item.lots_prevus} lot(s) trouvé(s) dans l'import">✓ {item.lots_prevus}</span>
{:else if u.statut?.startsWith('copropriétaire')}
<span class="badge badge-warning" title="Pas trouvé dans l'import Lots">⚠ 0</span>
{:else}
<span style="color:var(--color-text-muted)">—</span>
{/if}
</td>
<td style="color:var(--color-text-muted);font-size:.8rem">{fmt(u.cree_le)}</td>
<td>
<div class="action-row">
<button class="btn btn-primary btn-sm" on:click={() => openCompteValidation(item)}>Valider →</button>
{#if !refusOpen[u.id]}
<button class="btn btn-danger btn-sm" on:click={() => (refusOpen[u.id] = true)}>Refuser</button>
{:else}
<div class="refus-inline">
<input type="text" placeholder="Motif (optionnel)" bind:value={refusMotif[u.id]} class="input-sm" />
<button class="btn btn-outline btn-sm" on:click={() => (refusOpen[u.id] = false)}>Annuler</button>
<button class="btn btn-danger btn-sm" on:click={() => refuserCompte(u.id)}>Confirmer</button>
</div>
{/if}
</div>
</td>
</tr>
{/each}
</tbody>
</table>
</div>
{/if}

{:else if onglet === 'acces'}
{#if commandesLoading}
<p class="muted">Chargement...</p>
{:else if commandes.length === 0}
<div class="empty-state">
<h3>Aucune commande en attente</h3>
<p>Toutes les demandes d'acces ont ete traitees.</p>
</div>
{:else}
<div class="card" style="overflow:hidden">
<table class="table">
<thead>
<tr><th>Utilisateur</th><th>Type</th><th>Lot</th><th>Date</th><th>Actions</th></tr>
</thead>
<tbody>
{#each commandes as cmd}
<tr>
<td style="font-weight:500">#{cmd.user_id}</td>
<td><span class="badge badge-blue">{cmd.type}</span></td>
<td style="color:var(--color-text-muted)">{cmd.lot_id ?? ''}</td>
<td style="color:var(--color-text-muted);font-size:.8rem">{fmt(cmd.cree_le)}</td>
<td>
<div class="action-row">
<button class="btn btn-primary btn-sm" on:click={() => accepterCommande(cmd.id)}>Accepter</button>
{#if !cmdRefusOpen[cmd.id]}
<button class="btn btn-danger btn-sm" on:click={() => (cmdRefusOpen[cmd.id] = true)}>Refuser</button>
{:else}
<div class="refus-inline">
<input type="text" placeholder="Motif du refus" bind:value={cmdMotif[cmd.id]} class="input-sm" />
<button class="btn btn-outline btn-sm" on:click={() => (cmdRefusOpen[cmd.id] = false)}>Annuler</button>
<button class="btn btn-danger btn-sm" on:click={() => refuserCommande(cmd.id)}>Confirmer</button>
</div>
{/if}
</div>
</td>
</tr>
{/each}
</tbody>
</table>
</div>
{/if}

{:else if onglet === 'utilisateurs'}
{#if utilisateursLoading}
<p class="muted">Chargement...</p>
{:else}

<!-- Barre de recherche + filtres + compteurs -->
<div class="users-toolbar">
  <input
    type="search"
    class="input-sm user-search"
    placeholder="Rechercher par nom ou e-mail…"
    bind:value={userSearch}
  />
  <select class="input-sm role-select" bind:value={userStatutFilter} style="min-width:160px">
    <option value="">— Tous les types —</option>
    {#each Object.entries(statutLabels) as [val, label]}
      <option value={val}>{label}</option>
    {/each}
  </select>
  <select class="input-sm role-select" bind:value={userCompteFilter} style="min-width:130px">
    <option value="">— Tous comptes —</option>
    <option value="actif">Actifs</option>
    <option value="inactif">En attente</option>
  </select>
  <span class="muted" style="font-size:.8rem">
    {filteredUsers.length} / {utilisateurs.length} utilisateur{utilisateurs.length > 1 ? 's' : ''}
    &nbsp;·&nbsp;
    {nbCS} membre{nbCS > 1 ? 's' : ''} CS
  </span>
</div>

{#if filteredUsers.length === 0}
<div class="empty-state"><h3>Aucun résultat</h3></div>
{:else}
<div class="card" style="overflow:hidden">
<table class="table">
<thead>
<tr><th>Nom</th><th>E-mail</th><th>Type</th><th>Bâtiment</th><th>Compte</th><th>Rôles actifs</th><th>Ajouter / Retirer un rôle</th><th>Actions</th></tr>
</thead>
<tbody>
{#each filteredUsers as u (u.id)}
<tr class:row-cs={userRoles(u).includes('conseil_syndical')} class:row-inactive={!u.actif}>
  <td style="font-weight:500">
    {u.prenom} {u.nom}
    <div class="user-tags">
      {#if u.has_lots}<span class="utag utag-ok">Loti</span>{:else}<span class="utag utag-ko">Loti</span>{/if}
      {#if u.has_tc}<span class="utag utag-ok">TC</span>{:else}<span class="utag utag-ko">TC</span>{/if}
      {#if u.has_vigik}<span class="utag utag-ok">Vigik</span>{:else}<span class="utag utag-ko">Vigik</span>{/if}
      {#if u.has_bail}<span class="utag utag-ok">Lié</span>{:else}<span class="utag utag-ko">Lié</span>{/if}
    </div>
  </td>
  <td style="color:var(--color-text-muted);font-size:.85rem">{u.email}</td>
  <td>
    <span class="badge {statutBadgeClass[u.statut] ?? 'badge-gray'}" style="font-size:.75rem">
      {statutLabels[u.statut] ?? u.statut ?? '—'}
    </span>
  </td>
  <td>
    <span class="badge badge-gray">{userBatimentLabel(u)}</span>
  </td>
  <td>
    {#if u.actif}
      <span class="badge badge-green">Actif</span>
    {:else if u.email_verifie === false}
      <span class="badge badge-orange" title="Email non vérifié">Email non vérifié</span>
    {:else}
      <span class="badge badge-gray">En attente</span>
    {/if}
  </td>
  <td>
    <div style="display:flex;gap:.3rem;flex-wrap:wrap">
      {#each displayRoles(u) as d (d.label)}
        <span class="badge {d.cls}">{d.label}</span>
      {/each}
    </div>
  </td>
  <td>
    {#if !u.actif}
      <span class="muted" style="font-size:.8rem">Compte inactif</span>
    {:else}
      <div class="action-row">
        <!-- Ajouter CS si pas déjà — réservé aux propriétaires -->
        {#if !userRoles(u).includes('conseil_syndical')}
          {#if u.statut?.startsWith('copropriétaire')}
          <button class="btn btn-outline btn-sm" style="color:#1d4ed8;border-color:#1d4ed8"
            on:click={() => demanderRole(u, 'conseil_syndical', 'ajouter')}>
            + CS
          </button>
          {/if}
        {:else}
          <button class="btn btn-outline btn-sm" style="color:#dc2626;border-color:#dc2626"
            on:click={() => demanderRole(u, 'conseil_syndical', 'retirer')}>
            – CS
          </button>
        {/if}
        <!-- Ajouter Admin si pas déjà — réservé aux propriétaires -->
        {#if !userRoles(u).includes('admin')}
          {#if u.statut?.startsWith('copropriétaire')}
          <button class="btn btn-outline btn-sm" style="color:#c2410c;border-color:#c2410c"
            on:click={() => demanderRole(u, 'admin', 'ajouter')}>
            + Admin
          </button>
          {/if}
        {:else}
          <button class="btn btn-outline btn-sm" style="color:#dc2626;border-color:#dc2626"
            on:click={() => demanderRole(u, 'admin', 'retirer')}>
            – Admin
          </button>
        {/if}
      </div>
    {/if}
  </td>
  <td>
    <div class="action-row">
      <button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={() => openEdit(u)}>✏️</button>
      <button class="btn-icon" aria-label="Accueil nouvel arrivant" title="Accueil nouvel arrivant" on:click={() => openAccueilModal(u)}>&#x1F3E0;</button>
      {#if u.actif && !u.has_lots}
        <button class="btn-icon" aria-label="Rejouer auto-match lots" title="Rejouer auto-match lots" on:click={() => relancerAutoMatch(u.id, `${u.prenom} ${u.nom}`)}>🔄</button>
      {/if}
      <button
        class={(u.communaute_interdit || (u.communaute_ban_jusqu_au && new Date(u.communaute_ban_jusqu_au) > new Date())) ? 'btn-icon-success' : 'btn-icon-warn'}
        aria-label={(u.communaute_interdit || (u.communaute_ban_jusqu_au && new Date(u.communaute_ban_jusqu_au) > new Date())) ? 'Autoriser la communauté' : 'Interdire la communauté'}
        title={u.communaute_interdit ? 'Banni définitivement — cliquer pour débannir' : (u.communaute_ban_jusqu_au && new Date(u.communaute_ban_jusqu_au) > new Date()) ? 'Banni 1 mois (probatoire) — cliquer pour débannir' : 'Interdire la communauté'}
        on:click={() => toggleBanCommunaute(u)}>
        {u.communaute_interdit ? '⛔' : (u.communaute_ban_jusqu_au && new Date(u.communaute_ban_jusqu_au) > new Date()) ? '🔓' : '🔒'}
      </button>
      <button class="btn-icon-danger" aria-label="Supprimer" title="Supprimer" on:click={() => (deleteConfirm = u)}>&#x1F5D1;️</button>
    </div>
  </td>
</tr>
{/each}
</tbody>
</table>
</div>
{/if}
{/if}

<!-- Modal de confirmation rôle -->
{#if roleEnCours}
<div class="modal-overlay" on:click|self={() => (roleEnCours = null)} role="dialog" aria-modal="true" tabindex="-1">
  <div class="modal-box card">
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:.75rem">Confirmer</h2>
    <p style="font-size:.875rem;margin-bottom:1rem">
      {roleEnCours.action === 'ajouter' ? 'Ajouter' : 'Retirer'} le rôle
      <strong>{roleLabels[roleEnCours.role] ?? roleEnCours.role}</strong>
      {roleEnCours.action === 'ajouter' ? 'à' : 'de'}
      <strong>{roleEnCours.user.prenom} {roleEnCours.user.nom}</strong> ?
      <br />
      <span style="font-size:.8rem;color:var(--color-text-muted)">
        Cette personne recevra une notification.
      </span>
    </p>
    <div style="display:flex;gap:.5rem;justify-content:flex-end">
      <button class="btn btn-outline" on:click={() => (roleEnCours = null)}>Annuler</button>
      <button class="btn btn-primary" on:click={confirmerRole}>Confirmer</button>
    </div>
  </div>
</div>
{/if}

<!-- Modal édition utilisateur -->
{#if editUser}
<div class="modal-overlay" on:click|self={() => (editUser = null)} role="dialog" aria-modal="true" tabindex="-1">
  <div class="modal-box card" style="max-width:520px">
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:1rem">Modifier l'utilisateur</h2>
    <div class="form-grid">
      <label>Prénom<input class="input input-sm" type="text" bind:value={editForm.prenom} /></label>
      <label>Nom<input class="input input-sm" type="text" bind:value={editForm.nom} /></label>
      <label>E-mail<input class="input input-sm" type="email" bind:value={editForm.email} /></label>
      <label>Téléphone<input class="input input-sm" type="text" bind:value={editForm.telephone} /></label>
      <label>Société<input class="input input-sm" type="text" bind:value={editForm.societe} /></label>
      <label>Statut
        <select class="input input-sm" bind:value={editForm.statut}>
          {#each Object.entries(statutLabels) as [val, lbl]}
            <option value={val}>{lbl}</option>
          {/each}
        </select>
      </label>
      <label>Bâtiment
        <select class="input input-sm" bind:value={editForm.batiment_id}>
          <option value={null}>— Aucun —</option>
          {#each batimentsList as b}
            <option value={b.id}>Bât. {b.numero}</option>
          {/each}
        </select>
      </label>
      <label style="display:flex;align-items:center;gap:.5rem;padding-top:1.2rem">
        <input type="checkbox" bind:checked={editForm.actif} />
        Compte actif
      </label>
    </div>
    <div style="display:flex;gap:.5rem;justify-content:flex-end;margin-top:1rem">
      <button class="btn btn-outline" on:click={() => (editUser = null)}>Annuler</button>
      <button class="btn btn-primary" on:click={saveEdit}>Enregistrer</button>
    </div>
  </div>
</div>
{/if}

{#if accueilModal}
<div class="modal-overlay" on:click|self={() => (accueilModal = null)} role="dialog" aria-modal="true" tabindex="-1">
  <div class="modal-box card" style="max-width:480px">
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:.75rem">&#x1F3E0; Accueil nouvel arrivant</h2>
    <p style="font-size:.85rem;margin-bottom:.1rem"><strong>{accueilModal.user.prenom} {accueilModal.user.nom}</strong></p>
    <p style="font-size:.78rem;color:var(--color-text-muted);margin-bottom:.75rem">
      Déclenche : bienvenue, consignes de copropriété, demande d'étiquette BAL (syndic), demande d'interphone (CS),
      avec copie des démarches au résident.
    </p>
    <div class="form-grid" style="margin-bottom:.75rem">
      <label>Bâtiment / logement
        <input bind:value={accueilBatiment} placeholder="Ex: Bât. A, Apt. 12…" />
      </label>
      <label>Ancien résident (optionnel)
        <input bind:value={accueilAncienResident} placeholder="Nom de l'ancien occupant…" />
      </label>
    </div>
    <div class="modal-actions">
      <button class="btn btn-outline" on:click={() => (accueilModal = null)}>Annuler</button>
      <button class="btn btn-primary" disabled={accueilSubmitting} on:click={confirmerAccueil}>
        {accueilSubmitting ? 'En cours…' : 'Lancer les actions d\'accueil'}
      </button>
    </div>
  </div>
</div>
{/if}

{#if deleteConfirm}
<div class="modal-overlay" on:click|self={() => (deleteConfirm = null)} role="dialog" aria-modal="true" tabindex="-1">
  <div class="modal-box card">
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:.75rem">Supprimer l'utilisateur ?</h2>
    <p style="font-size:.875rem;margin-bottom:1rem">
      Vous êtes sur le point de supprimer définitivement le compte de
      <strong>{deleteConfirm.prenom} {deleteConfirm.nom}</strong> ({deleteConfirm.email}).
      <br /><span style="color:var(--color-danger);font-size:.8rem">Cette action est irréversible.</span>
    </p>
    <div style="display:flex;gap:.5rem;justify-content:flex-end">
      <button class="btn btn-outline" on:click={() => (deleteConfirm = null)}>Annuler</button>
      <button class="btn btn-danger" on:click={confirmerDelete}>Supprimer définitivement</button>
    </div>
  </div>
</div>
{/if}

{:else if onglet === 'demandes_profil'}
{#if demandesProfilLoading}
<p class="muted">Chargement...</p>
{:else if demandesProfil.length === 0}
<div class="empty-state">
<h3>Aucune demande en attente</h3>
<p>Toutes les demandes de modification de profil ont été traitées.</p>
</div>
{:else}
<div class="card" style="overflow:hidden">
<table class="table">
<thead>
<tr><th>Résident</th><th>Statut actuel</th><th>Bâtiment actuel</th><th>Changement souhaité</th><th>Motif</th><th>Date</th><th>Actions</th></tr>
</thead>
<tbody>
{#each demandesProfil as d}
<tr>
  <td>
    <div style="font-weight:600">{d.utilisateur_nom}</div>
    <div style="font-size:.8rem;color:var(--color-text-muted)">{d.utilisateur_email}</div>
  </td>
  <td><span style="font-size:.82rem">{statutLabelsAdmin[d.statut_actuel] ?? d.statut_actuel ?? '—'}</span></td>
  <td><span style="font-size:.82rem">{d.batiment_actuel ?? '—'}</span></td>
  <td>
    {#if d.statut_souhaite}
      <div style="font-size:.82rem">Type : <strong>{statutLabelsAdmin[d.statut_souhaite] ?? d.statut_souhaite}</strong></div>
    {/if}
    {#if d.batiment_nom_souhaite}
      <div style="font-size:.82rem">Bât. : <strong>{d.batiment_nom_souhaite}</strong></div>
    {/if}
  </td>
  <td style="font-size:.82rem;color:var(--color-text-muted);max-width:140px;white-space:pre-wrap">{d.motif ?? '—'}</td>
  <td style="font-size:.82rem;color:var(--color-text-muted)">{fmt(d.cree_le)}</td>
  <td>
    <div class="action-row">
      <button class="btn btn-sm" style="background:#16a34a;color:#fff;border-color:#16a34a"
        on:click={() => approuverDemande(d.id)}>✓ Approuver</button>
      {#if refusDemandeOpen[d.id]}
        <div style="display:flex;gap:.35rem;align-items:center">
          <input type="text" bind:value={refusDemande[d.id]} placeholder="Motif refus" style="font-size:.78rem;padding:.25rem .5rem;width:120px;border:1px solid var(--color-border);border-radius:4px" />
          <button class="btn btn-sm btn-danger" on:click={() => rejeterDemande(d.id)}>Confirmer</button>
          <button class="btn btn-sm" on:click={() => (refusDemandeOpen[d.id] = false)}>✕</button>
        </div>
      {:else}
        <button class="btn btn-sm btn-danger btn-outline"
          on:click={() => (refusDemandeOpen[d.id] = true)}>✗ Rejeter</button>
      {/if}
    </div>
  </td>
</tr>
{/each}
</tbody>
</table>
</div>
{/if}

{:else if onglet === 'sauvegardes'}
<div class="backup-header">
<p class="muted">Stockage : <code>/data/5hostachy/backups/</code></p>
<button class="btn btn-primary" on:click={declencherSauvegarde} disabled={backupEnCours}>
{#if backupEnCours}En cours...{:else}Declencher maintenant{/if}
</button>
</div>
{#if historiqueLoading}
<p class="muted">Chargement...</p>
{:else if historique.length === 0}
<div class="empty-state">
<h3>Aucune sauvegarde</h3>
<p>Cliquez sur Declencher maintenant pour lancer la premiere sauvegarde.</p>
</div>
{:else}
<div class="card" style="overflow:hidden;margin-top:1rem">
<table class="table">
<thead>
<tr><th>Date</th><th>Declenchement</th><th>Statut</th><th>Taille</th><th>Duree</th></tr>
</thead>
<tbody>
{#each historique as h}
<tr>
<td style="font-size:.85rem">{fmt(h.cree_le)}</td>
<td style="color:var(--color-text-muted)">{h.declenchee_par}</td>
<td><span class="badge {statutBadge(h.statut)}">{h.statut}</span></td>
<td style="color:var(--color-text-muted);font-size:.85rem">
{h.taille_octets ? (h.taille_octets / 1024 / 1024).toFixed(1) + ' Mo' : ''}
</td>
<td style="color:var(--color-text-muted);font-size:.85rem">
{h.duree_secondes != null ? h.duree_secondes + ' s' : ''}
</td>
</tr>
{/each}
</tbody>
</table>
</div>
{/if}

{:else if onglet === 'emails'}
<p class="muted" style="margin-bottom:1rem">Modeles utilises pour les notifications automatiques.</p>
{#if emailsLoading}
<p class="muted">Chargement...</p>
{:else if emailTemplates.length === 0}
<div class="empty-state"><h3>Aucun modele trouve</h3></div>
{:else}
<div class="card" style="overflow:hidden">
<table class="table">
<thead>
<tr><th>Code</th><th>Nom</th><th>Sujet</th><th>Actif</th><th>Action</th></tr>
</thead>
<tbody>
{#each emailTemplates as tpl}
<tr>
<td><code style="font-size:.78rem">{tpl.code}</code></td>
<td style="font-size:.875rem">{tpl.libelle ?? tpl.nom ?? '—'}</td>
<td style="font-size:.8rem;color:var(--color-text-muted)">{tpl.sujet}</td>
<td>
{#if tpl.actif}<span class="badge badge-green">Oui</span>
{:else}<span class="badge badge-gray">Non</span>{/if}
</td>
<td>
<button class="btn-icon-edit" aria-label="Modifier ce modèle" title="Modifier" on:click={() => openEmailEdit(tpl)}>✏️</button>
</td>
</tr>
{/each}
</tbody>
</table>
</div>
{/if}

<!-- Modal édition modèle e-mail -->
{#if emailEdit}
<div class="modal-overlay" on:click|self={() => (emailEdit = null)} role="dialog" aria-modal="true">
  <div class="modal-box card" style="max-width:680px">
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:1rem">
      Modifier le modèle — <code style="font-size:.85rem">{emailEdit.code}</code>
    </h2>
    <div style="display:flex;flex-direction:column;gap:.6rem">
      <div>
        <label class="email-label" for="email-sujet">Sujet</label>
        <input id="email-sujet" class="email-input" type="text" bind:value={emailSujet} />
      </div>
      <div>
        <label class="email-label" for="email-corps-html">Corps HTML</label>
        <textarea id="email-corps-html" class="email-input" rows="10" bind:value={emailCorpsHtml}></textarea>
      </div>
      <div>
        <label class="email-label" for="email-corps-texte">Corps texte (fallback)</label>
        <textarea id="email-corps-texte" class="email-input" rows="4" bind:value={emailCorpsTexte}></textarea>
      </div>
      <label style="display:flex;align-items:center;gap:.5rem;font-size:.875rem;cursor:pointer">
        <input type="checkbox" bind:checked={emailActif} />
        Actif
      </label>
    </div>
    <div style="display:flex;gap:.5rem;justify-content:flex-end;margin-top:1rem">
      <button class="btn btn-outline" on:click={() => (emailEdit = null)} disabled={emailSaving}>Annuler</button>
      <button class="btn btn-primary" on:click={saveEmailEdit} disabled={emailSaving}>
        {emailSaving ? 'Enregistrement...' : 'Enregistrer'}
      </button>
    </div>
  </div>
</div>
{/if}

<!-- Historique des emails envoyés -->
<hr style="border:none;border-top:1px solid var(--color-border);margin:1.5rem 0" />
<h3 style="font-size:1rem;font-weight:700;margin-bottom:.75rem">📬 Historique des envois</h3>
<p class="muted" style="font-size:.85rem;margin-bottom:.75rem">10 derniers emails envoyés (ou tentatives). Purgé automatiquement après 90 jours.</p>
{#if emailHistoryLoading}
<p class="muted">Chargement...</p>
{:else if emailHistory.length === 0}
<div class="empty-state"><h3>Aucun email envoyé</h3><p>L'historique est vide.</p></div>
{:else}
<div class="card" style="overflow:auto;max-height:420px">
<table class="table" style="font-size:.82rem">
<thead style="position:sticky;top:0;background:var(--color-surface)"><tr><th>Date</th><th>Template</th><th>Destinataire</th><th>Sujet</th><th>Statut</th></tr></thead>
<tbody>
{#each emailHistory as h}
<tr>
<td style="white-space:nowrap">{fmt(h.cree_le)}</td>
<td><code style="font-size:.75rem">{h.code}</code></td>
<td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title={h.destinataire}>{h.destinataire}</td>
<td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title={h.sujet}>{h.sujet || '—'}</td>
<td>
{#if h.statut === 'succes'}<span class="badge badge-green">✓</span>
{:else if h.statut === 'erreur'}<span class="badge badge-red" title={h.erreur ?? ''}>✗</span>
{:else}<span class="badge badge-gray" title={h.erreur ?? ''}>ignoré</span>{/if}
</td>
</tr>
{/each}
</tbody>
</table>
</div>
{/if}

{:else if onglet === 'site'}
<section class="config-section">
  <h2 class="config-section-title">⚙️ Paramètres généraux</h2>
  <div class="form-grid" style="max-width:600px">
    <label class="field-label">
      Nom de la plateforme
      <input class="input input-sm" type="text" bind:value={siteConfig.nom} placeholder="5Hostachy" />
      <span class="field-hint">Affiché sur la page de connexion et dans le menu.</span>
    </label>
    <label class="field-label">
      URL publique
      <input class="input input-sm" type="url" bind:value={siteConfig.url} placeholder="https://..." />
    </label>
    <label class="field-label" style="grid-column:span 2">
      E-mail administrateur
      <input class="input input-sm" type="email" bind:value={siteConfig.email_admin} placeholder="admin@example.com" />
      <span class="field-hint">Adresse de secours utilisée si aucun utilisateur gestionnaire du site n'est sélectionné.</span>
    </label>
    <label class="field-label" style="grid-column:span 2">
      Gestionnaire du site (utilisateur)
      <select class="input input-sm" bind:value={siteConfig.site_manager_user_id}>
        <option value="">Aucun (utiliser l'e-mail administrateur)</option>
        {#each siteManagerUsers as u}
          <option value={String(u.id)}>{u.prenom} {u.nom} — {u.email}</option>
        {/each}
      </select>
      <span class="field-hint">Cet utilisateur est considéré comme gestionnaire du site dans l'administration et reçoit les notifications e-mail « Bug » si l'option est activée.</span>
    </label>
    <label class="field-label" style="grid-column:span 2">
      Sous-titre de la page de connexion
      <input class="input input-sm" type="text" bind:value={siteConfig.login_sous_titre} placeholder="Votre espace numérique de résidence" />
      <span class="field-hint">Affiché sous le nom du site sur la page de connexion.</span>
    </label>
    <label class="field-label" style="grid-column:span 2">
      Délai d'archivage automatique (heures)
      <input class="input input-sm" type="number" bind:value={siteConfig.archivage_delai_heures} min="1" max="8760" placeholder="48" style="width:120px" />
      <span class="field-hint">Délai après lequel une actualité « Résolue » est automatiquement archivée (défaut : 48h). Le bouton 📦 permet d'archiver immédiatement sans attendre ce délai.</span>
    </label>
    <label class="field-label" style="grid-column:span 2">
      <span style="display:flex;align-items:center;gap:.5rem">
        <input type="checkbox" bind:checked={siteConfig.notify_ticket_bug_email} style="width:1rem;height:1rem" />
        Notifier si un bug (Tickets)
      </span>
      <span class="field-hint">Envoie un e-mail au gestionnaire du site sélectionné (ou à l'adresse administrateur de secours) uniquement pour les tickets de catégorie « Bug ». Les tickets « Urgence » ne déclenchent pas cette notification.</span>
    </label>
    <label class="field-label" style="grid-column:span 2">
      <span style="display:flex;align-items:center;gap:.5rem">
        <input type="checkbox" bind:checked={siteConfig.notify_new_user_created_email} style="width:1rem;height:1rem" />
        Notifier si un nouvel utilisateur est créé
      </span>
      <span class="field-hint">Envoie un e-mail au gestionnaire du site sélectionné (ou à l'adresse administrateur de secours) lorsqu'un nouveau compte est créé et mis en attente de validation.</span>
    </label>
  </div>
  <div style="display:flex;justify-content:flex-end;margin-top:.75rem;max-width:600px">
    <button class="btn btn-primary" on:click={saveSiteConfig} disabled={siteSaving}>
      {siteSaving ? 'Enregistrement...' : 'Enregistrer'}
    </button>
  </div>

</section>
<hr style="border:none;border-top:1px solid var(--color-border);margin:1.5rem 0" />
<section class="config-section">
  <h2 class="config-section-title">&#x1F5A5;️ Système — Sauvegardes</h2>
  <div class="backup-header">
    <p class="muted">Stockage : <code>/data/5hostachy/backups/</code></p>
    <button class="btn btn-primary" on:click={declencherSauvegarde} disabled={backupEnCours}>
      {#if backupEnCours}En cours...{:else}Déclencher maintenant{/if}
    </button>
  </div>
  {#if historiqueLoading}
    <p class="muted">Chargement...</p>
  {:else if historique.length === 0}
    <div class="empty-state">
      <h3>Aucune sauvegarde</h3>
      <p>Cliquez sur Déclencher maintenant pour lancer la première sauvegarde.</p>
    </div>
  {:else}
    <div class="card" style="overflow:auto;max-height:420px;margin-top:1rem">
      <table class="table" style="font-size:.82rem">
        <thead style="position:sticky;top:0;background:var(--color-surface)"><tr><th>Date</th><th>Déclenchement</th><th>Statut</th><th>Taille</th><th>Durée</th></tr></thead>
        <tbody>
          {#each historique as h}
            <tr>
              <td style="font-size:.85rem">{fmt(h.cree_le)}</td>
              <td style="color:var(--color-text-muted)">{h.declenchee_par}</td>
              <td><span class="badge {statutBadge(h.statut)}">{h.statut}</span></td>
              <td style="color:var(--color-text-muted);font-size:.85rem">{h.taille_octets ? (h.taille_octets / 1024 / 1024).toFixed(1) + ' Mo' : ''}</td>
              <td style="color:var(--color-text-muted);font-size:.85rem">{h.duree_secondes != null ? h.duree_secondes + ' s' : ''}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>
<hr style="border:none;border-top:1px solid var(--color-border);margin:1.5rem 0" />
<section class="config-section">
  <h2 class="config-section-title">&#x1F527; Système — Maintenance</h2>
  <div class="backup-header">
    <p class="muted" style="font-size:.85rem">Exécutions du script cron hebdomadaire (purge tokens, VACUUM, prune images). Le script enregistre automatiquement chaque passage si <code>MAINTENANCE_KEY</code> est configuré dans le <code>.env</code>.</p>
    <button class="btn btn-primary" on:click={declencherMaintenance} disabled={maintenanceEnCours}>
      {maintenanceEnCours ? 'En cours...' : 'Déclencher maintenant'}
    </button>
  </div>
  {#if maintenanceLoading}
    <p class="muted">Chargement...</p>
  {:else if historiqueMaintenance.length === 0}
    <div class="empty-state">
      <h3>Aucune exécution enregistrée</h3>
      <p>Le script <code>maintenance.sh</code> n'a pas encore été exécuté, ou <code>MAINTENANCE_KEY</code> n'est pas configuré.</p>
    </div>
  {:else}
    <div class="card" style="overflow:auto;max-height:420px;margin-top:1rem">
      <table class="table" style="font-size:.82rem">
        <thead style="position:sticky;top:0;background:var(--color-surface)"><tr><th>Date</th><th>Déclenchement</th><th>Statut</th><th>Taille DB</th><th>Durée</th></tr></thead>
        <tbody>
          {#each historiqueMaintenance as m}
            <tr>
              <td style="font-size:.85rem">{fmt(m.cree_le)}</td>
              <td style="color:var(--color-text-muted)">{m.declenchee_par}</td>
              <td>
                <span class="badge {m.statut === 'succes' ? 'badge-green' : 'badge-red'}">{m.statut}</span>
                {#if m.erreur}<span title={m.erreur} style="margin-left:.4rem;cursor:help">⚠️</span>{/if}
              </td>
              <td style="color:var(--color-text-muted);font-size:.85rem">{m.taille_db_octets ? (m.taille_db_octets / 1024 / 1024).toFixed(1) + ' Mo' : '—'}</td>
              <td style="color:var(--color-text-muted);font-size:.85rem">{m.duree_secondes != null ? m.duree_secondes + ' s' : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>

{:else if onglet === 'pages'}
<p class="muted" style="margin-bottom:1.25rem">Personnalisez l'icône, le label de navigation, le titre et la description de chaque page. Cliquer sur une entrée pour la modifier ; les autres se referment automatiquement.</p>
<div class="ref-list">
  {#each pagesConfig as pg, i (pg.id)}
    <div class="ref-item" class:expanded={expandedPages.has(pg.id)}>
      <div class="page-row">
        <div class="order-btns">
          <button type="button" class="btn-order" disabled={i === 0} on:click={() => movePage(i, -1)} aria-label="Monter">▲</button>
          <button type="button" class="btn-order" disabled={i === pagesConfig.length - 1} on:click={() => movePage(i, 1)} aria-label="Descendre">▼</button>
        </div>
        <button class="page-row-btn" on:click={() => togglePage(pg.id)} type="button">
          <span class="page-row-icon"><Icon name={pg.icone || 'help-circle'} size={16} /></span>
          <span class="page-nom">{pg.nom}</span>
          <span class="ref-desc muted">{stripHtmlPreview(pg.descriptif)}</span>
          <span class="chevron" class:open={expandedPages.has(pg.id)}>›</span>
        </button>
      </div>
      {#if expandedPages.has(pg.id)}
        <div class="ref-body">
          <div class="pages-form-grid">
            <div class="pages-form-section">
              <div class="pages-form-section-title">Navigation (barre de menu)</div>
              <label class="field-label">
                Icône Lucide
                <div style="display:flex;align-items:center;gap:.5rem">
                  <input class="input input-sm" style="flex:1" type="text" bind:value={pg.icone} placeholder="ex. : layout-dashboard" />
                  <span style="color:var(--color-text-muted);flex-shrink:0;display:flex;align-items:center"><Icon name={pg.icone || 'help-circle'} size={20} /></span>
                </div>
                <span class="field-hint">Cette icône s'affiche dans le menu <strong>et</strong> aussi avant le titre H1 en haut de la page (c'est la même icône, modifiable ici). <a href="https://lucide.dev/icons/" target="_blank" rel="noopener noreferrer">Parcourir lucide.dev →</a></span>
              </label>
              <label class="field-label">
                Label menu
                <input class="input input-sm" type="text" bind:value={pg.navLabel} />
                <span class="field-hint">Texte affiché dans la barre de navigation.</span>
              </label>
            </div>
            <div class="pages-form-section">
              <div class="pages-form-section-title">Page</div>
              <label class="field-label">
                Titre de la page
                <input class="input input-sm" type="text" bind:value={pg.titre} />
                <span class="field-hint">Titre de Page avec reprise de l'icône (de navigation du menu associé).</span>
              </label>
              <label class="field-label">
                Description
                <RichEditor bind:value={pg.descriptif} minHeight="80px" />
                <span class="field-hint">Sous-titre affiché sous le titre de page. Mise en forme riche supportée (gras, italique, listes, liens).</span>
              </label>
            </div>
            {#if pg.onglets && pg.onglets.length > 0}
            <div class="pages-form-section" style="grid-column:1/-1">
              <div class="pages-form-section-title">Onglets</div>
              <div class="onglets-cards">
                {#each pg.onglets as o}
                <div class="onglet-card">
                  <label class="field-label">
                    Label « {o.id} »
                    <input class="input input-sm" type="text" bind:value={o.label} />
                  </label>
                  <label class="field-label">
                    Descriptif
                    <RichEditor bind:value={o.descriptif} minHeight="56px" />
                  </label>
                </div>
                {/each}
              </div>
              <span class="field-hint">Labels et descriptifs de chaque onglet. Le descriptif apparaît sous les onglets quand l'onglet est actif.</span>
            </div>
            {/if}
          </div>
          <div style="display:flex;justify-content:flex-end;margin-top:.75rem">
            <button class="btn btn-primary btn-sm" on:click={() => savePageConfig(pg)}>Enregistrer</button>
          </div>
        </div>
      {/if}
    </div>
  {/each}
</div>
{:else if onglet === 'legal'}
<section class="config-section">
  <h2 class="config-section-title">&#x1F4C4; Mentions légales</h2>
  <p class="muted" style="margin-bottom:1rem">Contenu affiché sur <code>/mentions-legales</code>.</p>
  <LegalEditor bind:value={siteConfig.mentions_legales} minHeight="380px" />
</section>
<hr style="border:none;border-top:1px solid var(--color-border);margin:1.5rem 0" />
<section class="config-section">
  <h2 class="config-section-title">&#x1F512; Politique de confidentialité</h2>
  <p class="muted" style="margin-bottom:1rem">Contenu affiché sur <code>/politique-de-confidentialite</code>.</p>
  <LegalEditor bind:value={siteConfig.politique_confidentialite} minHeight="380px" />
</section>
<div style="display:flex;justify-content:flex-end;margin-top:1rem">
  <button class="btn btn-primary" on:click={saveSiteConfig} disabled={siteSaving}>
    {siteSaving ? 'Enregistrement...' : 'Enregistrer'}
  </button>
</div>

{:else if onglet === 'referentiels'}
<p class="muted" style="margin-bottom:1.25rem">Gérez les valeurs de référence utilisées dans les filtres et formulaires de l'application.</p>
<div class="ref-list">
  {#each referentiels as ref (ref.id)}
    <div class="ref-item" class:expanded={expandedRefs.has(ref.id)}>
      <button class="ref-row" on:click={() => toggleRef(ref.id)} type="button">
        <span class="ref-name">{ref.nom}</span>
        <span class="ref-meta muted">{ref.items.length} valeur{ref.items.length > 1 ? 's' : ''}</span>
        <span class="chevron" class:open={expandedRefs.has(ref.id)}>›</span>
      </button>
      {#if expandedRefs.has(ref.id)}
        <div class="ref-body">
          <div class="ref-chips">
            {#each ref.items as item (item.id)}
              <span class="ref-chip">
                {item.label}
                <button class="chip-del" type="button" aria-label="Supprimer {item.label}"
                  on:click={() => removeRefItem(ref.id, item.id)}>×</button>
              </span>
            {/each}
            {#if ref.items.length === 0}
              <span class="muted" style="font-size:.82rem">Aucune valeur.</span>
            {/if}
          </div>
          <div class="ref-add-row">
            <input
              class="input input-sm"
              type="text"
              placeholder="Nouvelle valeur..."
              bind:value={refNewItem[ref.id]}
              on:keydown={(e) => { if (e.key === 'Enter') addRefItem(ref.id); }}
            />
            <button class="btn btn-primary btn-sm" on:click={() => addRefItem(ref.id)} type="button">+ Ajouter</button>
          </div>
        </div>
      {/if}
    </div>
  {/each}
</div>

{:else if onglet === 'whatsapp'}
<section class="config-section">
  <h2 class="config-section-title">
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="#25D366" style="vertical-align:middle;margin-right:.4rem"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.570-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
    Configuration WhatsApp
  </h2>
  <div class="form-grid" style="max-width:640px">
    <label class="field-label" style="grid-column:span 2">
      <span style="display:flex;align-items:center;gap:.5rem">
        <input type="checkbox" bind:checked={waConfig.enabled} style="width:1rem;height:1rem" />
        Activer l'envoi WhatsApp
      </span>
      <span class="field-hint">Si activé, les actualités avec "Partager sur le groupe" seront envoyées au groupe WhatsApp.</span>
    </label>
    <label class="field-label">
      Nom du canal
      <input class="input input-sm" type="text" bind:value={waConfig.group_name} placeholder="Groupe WhatsApp" />
      <span class="field-hint">Nom affiché dans l'interface (informatif).</span>
    </label>
    <label class="field-label">
      URL du bridge WhatsApp
      <input class="input input-sm" type="url" bind:value={waConfig.api_url} placeholder="http://whatsapp-bridge:8090" />
    </label>
    <label class="field-label">
      Group JID
      <input class="input input-sm" type="text" bind:value={waConfig.group_jid} placeholder="1234567890@g.us" />
      <span class="field-hint">Identifiant du groupe WhatsApp (format : 123...@g.us).</span>
    </label>
    <label class="field-label" style="grid-column:span 2">
      Clé API
      <input class="input input-sm" type="password" bind:value={waConfig.api_key}
        placeholder={waApiKeySet ? '••••••  (clé déjà configurée — laisser vide pour conserver)' : 'Entrez la clé API du bridge WhatsApp'} />
      <span class="field-hint">{waApiKeySet ? 'Une clé est déjà configurée. Laissez ce champ vide pour la conserver.' : 'Requis pour l\'authentification au bridge WhatsApp.'}</span>
    </label>
  </div>
  <div style="display:flex;justify-content:flex-end;margin-top:.75rem;max-width:640px">
    <button class="btn btn-primary" on:click={saveWaConfig} disabled={waSaving}>
      {waSaving ? 'Enregistrement...' : 'Enregistrer'}
    </button>
  </div>
  <hr style="border:none;border-top:1px solid var(--color-border);margin:.75rem 0;max-width:640px" />
  <div style="max-width:640px">
    <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.5rem">
      <p style="font-size:.85rem;font-weight:600;color:var(--color-text-muted);margin:0">🧪 Tester la configuration</p>
      <button class="btn btn-outline" style="font-size:.75rem;padding:.15rem .5rem" on:click={checkWaStatus} disabled={waStatusLoading}>
        {waStatusLoading ? '...' : '🔄 Statut'}
      </button>
      {#if waStatus}
        <span style="font-size:.8rem;padding:.1rem .5rem;border-radius:4px;{waStatus.state === 'open' ? 'background:#d1fae5;color:#065f46' : 'background:#fee2e2;color:#991b1b'}">
          {waStatus.state === 'open' ? '✅ Connecté' : waStatus.state === 'waiting_qr' ? '📱 En attente du QR' : '❌ ' + waStatus.state}
        </span>
      {/if}
    </div>
    <div style="display:flex;gap:.5rem;align-items:start;flex-wrap:wrap">
      <textarea
        class="input input-sm"
        bind:value={waTestMessage}
        rows="2"
        placeholder="Message de test..."
        style="flex:1;min-width:220px;resize:vertical"
      ></textarea>
      <button
        class="btn btn-outline"
        on:click={sendWaTest}
        disabled={waTesting || !waTestMessage.trim()}
        style="white-space:nowrap"
      >
        {waTesting ? 'Envoi...' : '📨 Envoyer le test'}
      </button>
    </div>
    <p style="font-size:.8rem;color:var(--color-text-muted);margin-top:.3rem">Envoie le message ci-dessus sur le groupe WhatsApp configuré.</p>
  </div>

  <hr style="border:none;border-top:1px solid var(--color-border);margin:1rem 0;max-width:640px" />

  <!-- Messages planifiés -->
  <div style="max-width:640px">
    <p style="font-size:.85rem;font-weight:600;margin-bottom:.5rem;color:var(--color-text-muted)">📅 Messages planifiés (envoi automatique)</p>
    <p style="font-size:.78rem;color:var(--color-text-muted);margin-bottom:1rem;line-height:1.5">
      💡 Markdown WhatsApp : <strong>*gras*</strong> | <em>_italique_</em> | <s>~barré~</s> | Sauts de ligne (Enter)
    </p>
    {#if waScheduled.length === 0}
      <p style="font-size:.8rem;color:var(--color-text-muted)">Aucun message planifié.</p>
    {/if}
    {#each waScheduled as item (item.id)}
      <div style="border:1px solid var(--color-border);border-radius:8px;padding:.75rem;margin-bottom:.75rem;background:var(--color-surface)">
        <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.5rem">
          <input type="checkbox" bind:checked={item.enabled} style="width:1rem;height:1rem" />
          <input class="input input-sm" type="text" bind:value={item.label} style="flex:1;font-weight:600" placeholder="Titre du message" />
          <span style="font-size:.75rem;padding:.1rem .4rem;border-radius:4px;background:#dbeafe;color:#1e40af">
            {item.cron_rule === '3eme_samedi' ? 'Vendredi avant le 3ᵉ samedi' : item.cron_rule === '4eme_samedi' ? 'Vendredi avant le 4ᵉ samedi' : item.cron_rule}
          </span>
        </div>
        <textarea class="input input-sm" bind:value={item.message} rows="4" style="width:100%;resize:vertical;font-size:.85rem;font-family:monospace" placeholder="Contenu du message (markdown WhatsApp autorisé)"></textarea>
        <div style="margin-top:.4rem;padding:.5rem;background:var(--color-bg);border-left:3px solid var(--color-border);border-radius:4px;font-size:.78rem;color:var(--color-text-muted);line-height:1.6;white-space:pre-wrap;word-wrap:break-word">
          {item.message || '— Aperçu du message'}
        </div>
        <div style="display:flex;justify-content:flex-end;margin-top:.4rem">
          <button class="btn btn-primary" style="font-size:.8rem;padding:.2rem .6rem" on:click={() => saveWaScheduledItem(item)} disabled={waScheduledSaving[item.id]}>
            {waScheduledSaving[item.id] ? '...' : '💾 Enregistrer'}
          </button>
        </div>
      </div>
    {/each}
  </div>

  <hr style="border:none;border-top:1px solid var(--color-border);margin:1rem 0;max-width:640px" />

  <!-- Footer des messages -->
  <div style="max-width:640px">
    <p style="font-size:.85rem;font-weight:600;margin-bottom:.5rem;color:var(--color-text-muted)">📝 Footer des messages (markdown WhatsApp)</p>
    <label class="field-label">
      <textarea
        class="input input-sm"
        bind:value={siteConfig.whatsapp_footer}
        rows="2"
        placeholder="— Le Conseil Syndical"
        style="width:100%;resize:vertical;font-size:.85rem;font-family:monospace"
      ></textarea>
      <span class="field-hint">Texte qui finalise chaque message (markdown WhatsApp autorisé : *gras*, _italique_, ~barré~).</span>
    </label>
  </div>

  <div style="display:flex;justify-content:flex-end;margin-top:.5rem;max-width:640px">
    <button class="btn btn-primary" style="font-size:.8rem;padding:.2rem .6rem" on:click={saveSiteConfig} disabled={siteSaving}>
      {siteSaving ? '...' : '💾 Enregistrer'}
    </button>
  </div>

  <hr style="border:none;border-top:1px solid var(--color-border);margin:1rem 0;max-width:640px" />

  <!-- Historique des envois -->
  <div style="max-width:640px">
    <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.5rem">
      <p style="font-size:.85rem;font-weight:600;color:var(--color-text-muted);margin:0">📋 Historique des envois (6 derniers)</p>
      <button class="btn btn-outline" style="font-size:.7rem;padding:.1rem .4rem" on:click={loadWaLogs}>🔄</button>
    </div>
    {#if waLogs.length === 0}
      <p style="font-size:.8rem;color:var(--color-text-muted)">Aucun message envoyé.</p>
    {:else}
      <div style="display:flex;flex-direction:column;gap:.4rem">
        {#each waLogs as log (log.id)}
          <div style="border:1px solid var(--color-border);border-radius:6px;padding:.5rem .75rem;font-size:.8rem;background:var(--color-surface)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.25rem">
              <span style="font-weight:600">{log.label}</span>
              <div style="display:flex;align-items:center;gap:.4rem">
                <span style="padding:.1rem .3rem;border-radius:4px;font-size:.7rem;{log.statut === 'envoyé' ? 'background:#d1fae5;color:#065f46' : 'background:#fee2e2;color:#991b1b'}">
                  {log.statut === 'envoyé' ? '✅' : '❌'} {log.statut}
                </span>
                <span style="color:var(--color-text-muted);font-size:.75rem">{log.envoye_le ? fmt(log.envoye_le) : ''}</span>
              </div>
            </div>
            <p style="margin:0;white-space:pre-wrap;color:var(--color-text-muted);font-size:.78rem">{log.message.length > 120 ? log.message.slice(0, 120) + '…' : log.message}</p>
            {#if log.erreur}
              <p style="margin:.2rem 0 0;color:#991b1b;font-size:.75rem">⚠️ {log.erreur}</p>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</section>

{:else if onglet === 'smtp'}
<section class="config-section">
  <h2 class="config-section-title">✉️ Configuration SMTP (notifications e-mail)</h2>
  <div class="form-grid" style="max-width:640px">
    <label class="field-label" style="grid-column:span 2">
      <span style="display:flex;align-items:center;gap:.5rem">
        <input type="checkbox" bind:checked={smtpConfig.enabled} style="width:1rem;height:1rem" />
        Activer l'envoi d'e-mails
      </span>
      <span class="field-hint">Si activé, les notifications (réinitialisation de mot de passe, etc.) seront envoyées par e-mail.</span>
    </label>
    <label class="field-label">
      Serveur SMTP
      <input class="input input-sm" type="text" bind:value={smtpConfig.server} placeholder="smtp.example.com" />
    </label>
    <label class="field-label">
      Port
      <input class="input input-sm" type="number" bind:value={smtpConfig.port} min="1" max="65535" placeholder="587" style="width:100px" />
    </label>
    <label class="field-label">
      Adresse expéditeur (From)
      <input class="input input-sm" type="email" bind:value={smtpConfig.from} placeholder="noreply@example.com" />
    </label>
    <label class="field-label">
      Nom expéditeur
      <input class="input input-sm" type="text" bind:value={smtpConfig.from_name} placeholder="Résidence du Parc" />
    </label>
    <label class="field-label">
      Nom d'utilisateur SMTP
      <input class="input input-sm" type="text" bind:value={smtpConfig.username} placeholder="user@example.com" />
      <span class="field-hint">Laisser vide si le serveur ne requiert pas d'authentification.</span>
    </label>
    <label class="field-label">
      Mot de passe SMTP
      <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
        <input
          class="input input-sm"
          type="password"
          bind:value={smtpConfig.password}
          autocomplete="new-password"
          disabled={smtpPasswordSet && !smtpEditingPassword}
          placeholder={smtpPasswordSet && !smtpEditingPassword ? 'Mot de passe masqué' : 'Nouveau mot de passe SMTP'}
          style="flex:1;min-width:220px"
        />
        {#if smtpPasswordSet && !smtpEditingPassword}
          <button class="btn btn-outline btn-sm" type="button" on:click={() => { smtpEditingPassword = true; smtpConfig.password = ''; }}>
            Changer
          </button>
        {/if}
      </div>
      <span class="field-hint">{smtpPasswordSet ? (smtpEditingPassword ? 'Saisissez le nouveau mot de passe puis cliquez sur Enregistrer.' : 'Mot de passe déjà enregistré. Cliquez sur « Changer » pour le remplacer.') : 'Requis si le serveur exige une authentification.'}</span>
    </label>
    <label class="field-label" style="grid-column:span 2">
      <span style="display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap">
        <span style="display:flex;align-items:center;gap:.4rem">
          <input type="checkbox" bind:checked={smtpConfig.starttls} style="width:1rem;height:1rem" />
          STARTTLS (port 587)
        </span>
        <span style="display:flex;align-items:center;gap:.4rem">
          <input type="checkbox" bind:checked={smtpConfig.ssl_tls} style="width:1rem;height:1rem" />
          SSL/TLS (port 465)
        </span>
      </span>
      <span class="field-hint">STARTTLS et SSL/TLS sont mutuellement exclusifs. Décocher les deux pour connexion non chiffrée.</span>
    </label>
  </div>
  <div style="display:flex;justify-content:flex-end;margin-top:.75rem;max-width:640px">
    <button class="btn btn-primary" on:click={saveSmtpConfig} disabled={smtpSaving}>
      {smtpSaving ? 'Enregistrement...' : 'Enregistrer'}
    </button>
  </div>
  <hr style="border:none;border-top:1px solid var(--color-border);margin:.75rem 0;max-width:640px" />
  <div style="max-width:640px">
    <p style="font-size:.85rem;font-weight:600;margin-bottom:.5rem;color:var(--color-text-muted)">🧪 Tester la configuration</p>
    <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
      <input
        class="input input-sm"
        type="email"
        bind:value={smtpTestEmail}
        placeholder="destinataire@example.com"
        style="flex:1;min-width:220px"
      />
      <button
        class="btn btn-outline"
        on:click={sendSmtpTest}
        disabled={smtpTesting || !smtpTestEmail}
      >
        {smtpTesting ? 'Envoi...' : '📨 Envoyer un e-mail de test'}
      </button>
    </div>
    <p style="font-size:.8rem;color:var(--color-text-muted);margin-top:.3rem">Envoie un e-mail de test avec la configuration SMTP actuellement enregistrée en base.</p>
  </div>
  <hr style="border:none;border-top:1px solid var(--color-border);margin:.75rem 0;max-width:640px" />
  <div style="max-width:640px">
    <p style="font-size:.85rem;font-weight:600;margin-bottom:.5rem;color:var(--color-text-muted)">✉️ Signature des e-mails</p>
    <label class="field-label">
      <textarea
        class="input input-sm"
        bind:value={siteConfig.email_footer}
        rows="2"
        placeholder="— Envoyé depuis 5hostachy.fr"
        style="width:100%;resize:vertical;font-size:.85rem;font-family:monospace"
      ></textarea>
      <span class="field-hint">Texte ajouté automatiquement en bas de chaque e-mail envoyé par la plateforme.</span>
    </label>
  </div>
  <div style="max-width:640px;margin-top:.75rem">
    <p style="font-size:.85rem;font-weight:600;margin-bottom:.5rem;color:var(--color-text-muted)">🏢 Référence copropriété (syndic)</p>
    <label class="field-label">
      <input
        class="input input-sm"
        type="text"
        bind:value={siteConfig.reference_copro}
        placeholder="00213"
        style="max-width:200px"
      />
      <span class="field-hint">Référence de la copropriété auprès du syndic. Utilisée en préfixe dans les sujets d'e-mails envoyés au syndic.</span>
    </label>
  </div>
  <div style="display:flex;justify-content:flex-end;margin-top:.5rem;max-width:640px">
    <button class="btn btn-primary" on:click={saveSmtpConfig} disabled={smtpSaving}>
      {smtpSaving ? 'Enregistrement...' : 'Enregistrer'}
    </button>
  </div>
</section>

{:else if onglet === 'telemetry'}
<section class="config-section">
  <h2 class="config-section-title">📊 Télémétrie — Utilisation de l'application</h2>
  <p class="muted" style="font-size:.85rem">Statistiques d'utilisation : qui utilise quoi et quand.</p>

  <!-- Sélecteur Jour / Mois / Année -->
  <div class="tl-scope-switch" style="margin:.75rem 0 1rem">
    <button class="pill" class:pill-active={tlScope === 'jour'} on:click={() => switchTlScope('jour')}>📅 Jour</button>
    <button class="pill" class:pill-active={tlScope === 'mois'} on:click={() => switchTlScope('mois')}>📆 Mois (30j)</button>
    <button class="pill" class:pill-active={tlScope === 'annee'} on:click={() => switchTlScope('annee')}>📊 Année (10 ans)</button>
  </div>

  {#if telemetryLoading}
    <p class="muted">Chargement des statistiques...</p>
  {:else if !telemetryData}
    <div class="empty-state">
      <h3>Aucune donnée de télémétrie</h3>
      <p>Les données apparaîtront après les premières visites.</p>
    </div>
  {:else}
    <!-- KPI universels -->
    <div class="tl-kpi-row">
      <div class="tl-kpi">
        <div class="tl-kpi-value">{telemetryData.kpi.vues ?? 0}</div>
        <div class="tl-kpi-label">{tlScope === 'jour' ? 'Pages vues aujourd\'hui' : tlScope === 'mois' ? 'Pages vues (30j)' : 'Pages vues (total)'}</div>
      </div>
      {#if telemetryData.kpi.utilisateurs != null}
      <div class="tl-kpi">
        <div class="tl-kpi-value">{telemetryData.kpi.utilisateurs}</div>
        <div class="tl-kpi-label">{tlScope === 'jour' ? 'Utilisateurs actifs aujourd\'hui' : 'Utilisateurs uniques (pic)'}</div>
      </div>
      {/if}
      <div class="tl-kpi">
        <div class="tl-kpi-value">{telemetryData.kpi.pages ?? 0}</div>
        <div class="tl-kpi-label">Pages distinctes visitées</div>
      </div>
      {#if telemetryData.kpi.heure_pointe}
      <div class="tl-kpi">
        <div class="tl-kpi-value">{telemetryData.kpi.heure_pointe}</div>
        <div class="tl-kpi-label">🔺 Heure de pointe</div>
      </div>
      {/if}
      {#if telemetryData.kpi.moy_vues_utilisateur != null}
      <div class="tl-kpi">
        <div class="tl-kpi-value">{telemetryData.kpi.moy_vues_utilisateur}</div>
        <div class="tl-kpi-label">Moy. vues / utilisateur</div>
      </div>
      {/if}
      {#if telemetryData.kpi.moy_vues_jour != null}
      <div class="tl-kpi">
        <div class="tl-kpi-value">{telemetryData.kpi.moy_vues_jour}</div>
        <div class="tl-kpi-label">Moy. vues / jour</div>
      </div>
      {/if}
      {#if telemetryData.kpi.moy_utilisateurs_jour != null}
      <div class="tl-kpi">
        <div class="tl-kpi-value">{telemetryData.kpi.moy_utilisateurs_jour}</div>
        <div class="tl-kpi-label">Moy. utilisateurs / jour</div>
      </div>
      {/if}
      {#if telemetryData.kpi.mois_actifs != null}
      <div class="tl-kpi">
        <div class="tl-kpi-value">{telemetryData.kpi.mois_actifs}</div>
        <div class="tl-kpi-label">Mois avec activité</div>
      </div>
      {/if}
      {#if telemetryData.kpi.moy_vues_mois != null}
      <div class="tl-kpi">
        <div class="tl-kpi-value">{telemetryData.kpi.moy_vues_mois}</div>
        <div class="tl-kpi-label">Moy. vues / mois</div>
      </div>
      {/if}
    </div>

    <!-- Jour le plus actif (scope mois) -->
    {#if tlScope === 'mois' && telemetryData.kpi.jour_pointe}
    <div class="tl-kpi-row" style="margin-top:.75rem">
      <div class="tl-kpi">
        <div class="tl-kpi-value">{telemetryData.kpi.jour_pointe.uniques} <span style="font-size:.6em;font-weight:400">utilisateurs</span></div>
        <div class="tl-kpi-label">🏆 Jour le plus actif — {telemetryData.kpi.jour_pointe.jour}</div>
      </div>
    </div>
    {/if}

    <!-- Records (scope annee) -->
    {#if tlScope === 'annee' && (telemetryData.kpi.record_jour || telemetryData.kpi.record_mois)}
    <div class="tl-kpi-row" style="margin-top:.75rem">
      {#if telemetryData.kpi.record_jour}
      <div class="tl-kpi">
        <div class="tl-kpi-value">{telemetryData.kpi.record_jour.uniques} <span style="font-size:.6em;font-weight:400">utilisateurs</span></div>
        <div class="tl-kpi-label">🏆 Record jour — {telemetryData.kpi.record_jour.jour}</div>
      </div>
      {/if}
      {#if telemetryData.kpi.record_mois}
      <div class="tl-kpi">
        <div class="tl-kpi-value">{telemetryData.kpi.record_mois.uniques} <span style="font-size:.6em;font-weight:400">utilisateurs</span></div>
        <div class="tl-kpi-label">🏆 Record mois — {telemetryData.kpi.record_mois.mois}</div>
      </div>
      {/if}
    </div>
    {/if}

    <!-- Graphe (barres CSS) — adaptatif au scope -->
    {#if telemetryData.chart.length > 0}
    <div class="card" style="margin-top:1.25rem">
      <h3 class="tl-section-title">📈 {telemetryData.chart_label}</h3>
      <div class="tl-chart">
        {#each telemetryData.chart as d}
          {@const maxVal = Math.max(...telemetryData.chart.map((x) => x.total), 1)}
          <div class="tl-bar-col {tlScope === 'annee' ? 'tl-bar-col-month' : ''}" title="{d.label} — {d.total} vues{d.uniques != null ? `, ${d.uniques} uniques` : ''}">
            <div class="tl-bar {tlScope === 'annee' ? 'tl-bar-month' : ''}" style="height:{Math.max(4, (d.total / maxVal) * 100)}%"></div>
            <div class="tl-bar-label">{d.label}</div>
          </div>
        {/each}
      </div>
    </div>
    {/if}

    <!-- Top pages -->
    {#if telemetryData.top_pages.length > 0}
    <div class="card" style="margin-top:1.25rem">
      <h3 class="tl-section-title">🏆 Top pages</h3>
      <table class="table">
        <thead><tr><th>Page</th><th style="text-align:right">Vues</th><th style="text-align:right">Utilisateurs</th><th style="text-align:right">%</th></tr></thead>
        <tbody>
          {#each telemetryData.top_pages as p}
            {@const grandTotal = telemetryData.top_pages.reduce((s, x) => s + x.total, 0) || 1}
            <tr>
              <td><code style="font-size:.82rem">{p.page}</code></td>
              <td style="text-align:right;font-weight:600">{p.total}</td>
              <td style="text-align:right;color:var(--color-text-muted)">{p.uniques}</td>
              <td style="text-align:right;color:var(--color-text-muted)">{(p.total / grandTotal * 100).toFixed(1)}%</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {/if}

    <!-- Utilisateurs les plus actifs (scope jour et mois) -->
    {#if telemetryData.top_users && telemetryData.top_users.length > 0}
    <div class="card" style="margin-top:1.25rem">
      <h3 class="tl-section-title">👥 Utilisateurs les plus actifs</h3>
      <table class="table">
        <thead><tr><th>Utilisateur</th><th style="text-align:right">Vues</th><th style="text-align:right">Pages diff.</th><th style="text-align:right">Dernière connexion</th></tr></thead>
        <tbody>
          {#each telemetryData.top_users as u}
            <tr>
              <td style="font-size:.85rem">{u.nom}</td>
              <td style="text-align:right;font-weight:600">{u.total}</td>
              <td style="text-align:right;color:var(--color-text-muted)">{u.pages}</td>
              <td style="text-align:right;font-size:.82rem;color:var(--color-text-muted)">{u.derniere_connexion ? fmt(u.derniere_connexion) : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {/if}
  {/if}
</section>

<hr style="border:none;border-top:1px solid var(--color-border);margin:1.5rem 0" />
<section class="config-section">
  <h2 class="config-section-title">🕓 Historique des agrégations</h2>
  <div class="backup-header">
    <p class="muted" style="font-size:.85rem">Exécutions de l'agrégation de la télémétrie (automatique chaque nuit à 2h, ou manuelle). Agrège les événements bruts en données journalières puis mensuelles, et purge les données expirées.</p>
    <button class="btn btn-primary" on:click={declencherAggregation} disabled={telemetryAggEnCours}>
      {telemetryAggEnCours ? 'En cours...' : 'Déclencher maintenant'}
    </button>
  </div>
  {#if telemetryHistLoading}
    <p class="muted">Chargement...</p>
  {:else if historiqueTelemetrie.length === 0}
    <div class="empty-state">
      <h3>Aucune exécution enregistrée</h3>
      <p>L'agrégation n'a pas encore été exécutée.</p>
    </div>
  {:else}
    <div class="card" style="overflow:auto;max-height:420px;margin-top:1rem">
      <table class="table" style="font-size:.82rem">
        <thead style="position:sticky;top:0;background:var(--color-surface)"><tr><th>Date</th><th>Déclenchement</th><th>Statut</th><th>Événements agrégés</th><th>Purges</th><th>Durée</th></tr></thead>
        <tbody>
          {#each historiqueTelemetrie as h}
            <tr>
              <td style="font-size:.85rem">{fmt(h.cree_le)}</td>
              <td style="color:var(--color-text-muted)">{h.declenchee_par}</td>
              <td>
                <span class="badge {h.statut === 'succes' ? 'badge-green' : h.statut === 'en_cours' ? 'badge-yellow' : 'badge-red'}">{h.statut === 'en_cours' ? 'en cours' : h.statut}</span>
                {#if h.erreur}<span title={h.erreur} style="margin-left:.4rem;cursor:help">⚠️</span>{/if}
              </td>
              <td style="font-size:.85rem;color:var(--color-text-muted)">{h.jours_agreges} jour{h.jours_agreges > 1 ? 's' : ''} · {h.mois_agreges} mois</td>
              <td style="font-size:.85rem;color:var(--color-text-muted)">{h.events_purges + h.daily_purges + h.monthly_purges} lignes</td>
              <td style="font-size:.85rem;color:var(--color-text-muted)">{h.duree_secondes != null ? h.duree_secondes + ' s' : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>

{/if}
{#if cvModal}
<div class="modal-overlay" on:click|self={() => (cvModal = null)} role="dialog" aria-modal="true" tabindex="-1">
  <div class="modal-box card" style="max-width:480px">
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:.75rem">Valider le compte de {cvModal.user.prenom} {cvModal.user.nom}</h2>
    <p style="font-size:.85rem;color:var(--color-text-muted);margin-bottom:1rem">
      {cvModal.user.statut ? (statutLabels[cvModal.user.statut] ?? cvModal.user.statut) : ''}
      {cvModal.lotsPrevus > 0 ? ` — ${cvModal.lotsPrevus} lot(s) détecté(s) dans l'import` : ''}
    </p>
    <label style="display:flex;align-items:flex-start;gap:.6rem;cursor:pointer;border:1.5px solid var(--color-border);border-radius:var(--radius);padding:.75rem;margin-bottom:.75rem"
      class:nouvel-arrivant-checked={cvNewArrivant}>
      <input type="checkbox" bind:checked={cvNewArrivant} style="margin-top:.2rem;flex-shrink:0" />
      <div>
        <strong style="font-size:.9rem">&#x1F3E0; Nouvel Arrivant</strong>
        <p style="font-size:.78rem;color:var(--color-text-muted);margin:.25rem 0 0">
          À cocher uniquement pour un <strong>nouveau résident</strong> qui emménage dans la copropriété.
          Déclenche automatiquement : message de bienvenue, envoi des consignes de copropriété,
          demande d'étiquette de boîte aux lettres auprès du syndic, et demande d'ajout sur l'interphone auprès du Conseil Syndical.
          <em>Ne pas cocher pour un résident existant qui crée simplement son compte.</em>
        </p>
      </div>
    </label>
    {#if cvNewArrivant}
    <div class="form-grid" style="margin-bottom:.75rem">
      <label>Bâtiment / logement
        <input bind:value={cvBatiment} placeholder="Ex: Bât. A, Apt. 12…" />
      </label>
      <label>Ancien résident (optionnel)
        <input bind:value={cvAncienResident} placeholder="Nom de l'ancien occupant…" />
      </label>
    </div>
    {/if}
    <div class="modal-actions">
      <button class="btn btn-outline" on:click={() => (cvModal = null)}>Annuler</button>
      <button class="btn btn-primary" disabled={cvSubmitting} on:click={confirmerCompteValidation}>
        {cvSubmitting ? 'En cours…' : 'Valider le compte'}
      </button>
    </div>
  </div>
</div>
{/if}

<style>
.page-header { display: flex; align-items: center; margin-bottom: 1.5rem; padding-left: 1.25rem; }
.page-header h1 { font-size: 1.4rem; font-weight: 700; }
.tabs-group { margin-bottom: 0; }
.tabs-group-label {
  font-size: .72rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: .06em; color: var(--color-text-muted);
  padding: 0 .25rem .3rem;
}
.tabs { display: flex; flex-wrap: wrap; gap: .25rem; border-bottom: 2px solid var(--color-border); margin-bottom: 1.5rem; }
.tab-btn {
padding: .45rem .9rem; border: none; background: none; cursor: pointer;
font-size: .875rem; color: var(--color-text-muted); border-bottom: 2px solid transparent;
margin-bottom: -2px; font-weight: 500; display: flex; align-items: center; gap: .4rem;
transition: color .15s, border-color .15s; white-space: nowrap;
}
.tab-btn:hover { color: var(--color-text); }
.tab-btn.active { color: var(--color-primary); border-bottom-color: var(--color-primary); }
.badge-count {
background: var(--color-danger); color: #fff; border-radius: 999px;
font-size: .7rem; padding: .1rem .45rem; font-weight: 700;
}
.action-row { display: flex; gap: .4rem; flex-wrap: wrap; align-items: center; }
.btn-sm { padding: .3rem .7rem; font-size: .8rem; }
.refus-inline { display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; }
.input-sm {
padding: .3rem .5rem; border: 1px solid var(--color-border);
border-radius: var(--radius); font-size: .85rem; min-width: 160px;
}
.backup-header {
display: flex; justify-content: space-between; align-items: center;
margin-bottom: .5rem; flex-wrap: wrap; gap: .75rem;
}
.backup-header p {
margin: 0;
flex: 1 1 320px;
}
.backup-header .btn {
margin-left: auto;
}
.muted { color: var(--color-text-muted); }
code { background: var(--color-bg); padding: .1rem .35rem; border-radius: .25rem; font-size: .85em; }
.role-select {
padding: .25rem .4rem; border: 1px solid var(--color-border);
border-radius: var(--radius); font-size: .82rem; background: var(--color-surface);
color: var(--color-text); cursor: pointer;
}
.users-toolbar {
display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap;
}
.user-search {
flex: 1; min-width: 200px; max-width: 340px;
padding: .4rem .7rem; border: 1px solid var(--color-border);
border-radius: var(--radius); font-size: .875rem;
}
.row-cs td { background: #eff6ff; }
.row-inactive td { opacity: .6; }
.btn-outline {
background: none; border: 1px solid var(--color-border);
border-radius: var(--radius); cursor: pointer; font-size: .8rem;
padding: .3rem .7rem; color: var(--color-text);
}
.btn-outline:hover { border-color: var(--color-primary); color: var(--color-primary); }
.badge-orange { background: #fff7ed; color: #c2410c; }
.badge-purple { background: #f5f3ff; color: #7c3aed; }
.modal-overlay {
position: fixed; top: 0; right: 0; bottom: 0; left: 0; background: rgba(0,0,0,.45);
display: flex; align-items: center; justify-content: center; z-index: 200;
}
.modal-box { max-width: 420px; width: 90%; padding: 1.5rem; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; }
.form-grid label { display: flex; flex-direction: column; gap: .25rem; font-size: .825rem; font-weight: 500; }
.email-label { display: block; font-size: .78rem; font-weight: 500; color: var(--color-text-muted); margin-bottom: .25rem; }
.email-input { width: 100%; padding: .4rem .65rem; border: 1px solid var(--color-border); border-radius: 6px; font-size: .85rem; font-family: monospace; box-sizing: border-box; resize: vertical; }
.config-section { margin-bottom: 1.25rem; }
.config-section-title { font-size: .95rem; font-weight: 700; margin-bottom: .75rem; }
.field-label { display: flex; flex-direction: column; gap: .25rem; font-size: .825rem; font-weight: 500; }
.field-hint { font-size: .75rem; color: var(--color-text-muted); }
.ref-list { display: flex; flex-direction: column; gap: .4rem; }
.page-row { width: 100%; display: flex; align-items: center; gap: .4rem; padding: .4rem .5rem .4rem .75rem; }
.page-row:hover { background: var(--color-bg); }
.page-row-btn { flex: 1; display: flex; align-items: center; gap: .5rem; background: none; border: none; cursor: pointer; text-align: left; font-size: .875rem; padding: .25rem .25rem; min-width: 0; }
.page-row-icon { flex: 0 0 18px; display: flex; align-items: center; color: var(--color-text-muted); }
.page-nom { flex: 0 0 20%; min-width: 80px; max-width: 180px; font-weight: 600; font-size: .875rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pages-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
.pages-form-section { display: flex; flex-direction: column; gap: .5rem; }
.pages-form-section-title { font-size: .7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; color: var(--color-text-muted); padding-bottom: .3rem; border-bottom: 1px solid var(--color-border); margin-bottom: .1rem; }
.ref-desc { font-size: .78rem; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.order-btns { display: flex; flex-direction: column; gap: 1px; flex-shrink: 0; }
.btn-order { background: none; border: 1px solid var(--color-border); border-radius: 3px; cursor: pointer; font-size: .6rem; padding: 1px 4px; line-height: 1.5; color: var(--color-text-muted); }
.btn-order:hover:not(:disabled) { border-color: var(--color-primary); color: var(--color-primary); background: var(--color-bg); }
.btn-order:disabled { opacity: .3; cursor: default; }
.ref-item { border: 1px solid var(--color-border); border-radius: var(--radius); overflow: hidden; background: var(--color-surface); }
.ref-item.expanded { border-color: var(--color-primary); }
.ref-row { width: 100%; display: flex; align-items: center; gap: .75rem; padding: .65rem 1rem; background: none; border: none; cursor: pointer; text-align: left; font-size: .875rem; }
.ref-row:hover { background: var(--color-bg); }
.ref-name { font-weight: 600; flex: 1; }
.ref-meta { font-size: .8rem; white-space: nowrap; }
.ref-body { padding: .75rem 1rem; border-top: 1px solid var(--color-border); background: var(--color-bg); }
.ref-chips { display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: .75rem; }
.ref-chip { display: inline-flex; align-items: center; gap: .3rem; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 999px; padding: .2rem .65rem; font-size: .8rem; }
.chip-del { background: none; border: none; cursor: pointer; color: var(--color-text-muted); padding: 0 .1rem; font-size: 1rem; line-height: 1; margin-left: .1rem; }
.chip-del:hover { color: var(--color-danger); }
.ref-add-row { display: flex; gap: .5rem; align-items: center; }
.chevron { font-size: 1.1rem; color: var(--color-text-muted); transition: transform .2s; display: inline-block; }
.chevron.open { transform: rotate(90deg); }
.user-tags { display: flex; flex-wrap: wrap; gap: .2rem; margin-top: .15rem; }
.utag { font-size: .6rem; font-weight: 600; padding: .05rem .35rem; border-radius: 4px; line-height: 1.3; }
.utag-ok { background: #d4edda; color: #155724; }
.utag-ko { background: #f8d7da; color: #721c24; }
.onglets-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: .75rem; }
.onglet-card { background: var(--color-bg); border: 1px solid var(--color-border); border-radius: 8px; padding: .75rem; display: flex; flex-direction: column; gap: .5rem; }

/* Télémétrie */
.tl-scope-switch { display: flex; gap: .5rem; flex-wrap: wrap; }
.pill { padding: .3rem .85rem; border-radius: 999px; border: 1.5px solid var(--color-border); background: var(--color-bg); font-size: .85rem; cursor: pointer; transition: background .15s, border-color .15s, color .15s; white-space: nowrap; line-height: 1.6; }
.pill:hover { border-color: var(--color-primary); color: var(--color-primary); }
.pill-active { background: var(--color-primary); border-color: var(--color-primary); color: #fff; }
.tl-kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin-top: 1.25rem; }
.tl-kpi { background: var(--color-surface, #fff); border: 1px solid var(--color-border); border-radius: var(--radius, 8px); padding: 1.25rem 1rem; text-align: center; }
.tl-kpi-value { font-size: 2rem; font-weight: 700; color: var(--color-primary); line-height: 1.1; }
.tl-kpi-label { font-size: .82rem; color: var(--color-text-muted); margin-top: .3rem; }
.tl-section-title { font-size: .95rem; font-weight: 600; margin: 0 0 .75rem; padding: .75rem 1rem 0; }
.tl-chart { display: flex; align-items: flex-end; gap: 2px; height: 120px; padding: 0 1rem .5rem; overflow-x: auto; }
.tl-bar-col { display: flex; flex-direction: column; align-items: center; flex: 1; min-width: 16px; height: 100%; justify-content: flex-end; }
.tl-bar { background: var(--color-primary); border-radius: 3px 3px 0 0; width: 100%; min-height: 4px; transition: height .3s; }
.tl-bar-month { background: var(--color-primary-light, #93c5fd); }
.tl-bar-label { font-size: .6rem; color: var(--color-text-muted); margin-top: 2px; white-space: nowrap; }
.tl-bar-col-month { min-width: 32px; }
</style>
