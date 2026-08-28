<!--
  L'onglet **Modèles e-mail** de l'administration : la liste des gabarits, leur
  édition, la réinitialisation des designs, et l'historique des envois.

  ## Il en existait DEUX jusqu'au 19/08/2026

  `admin/templates-email` — « Designs des modèles d'e-mail » — montrait la même
  donnée sous un autre angle. Le doublon était connu depuis #299, déclaré en
  tolérance dans `lint:routes`, et son arbitrage attendait dans #307 : *« les
  fusionner est une décision fonctionnelle »*. Elle a été prise à l'écran.

  🔴 **La fusion est une UNION, pas un remplacement.** Chacun savait faire ce que
  l'autre ignorait :

  | Capacité | Venait de |
  |---|---|
  | table Code · Nom · Sujet · Actif, historique des envois | l'onglet |
  | corps texte (repli) | l'onglet |
  | **intention** (le bandeau attendu du destinataire) | Designs |
  | **aperçu** du corps rendu | Designs |
  | **variables disponibles** du gabarit | Designs |
  | **réinitialiser tous les designs** | Designs |

  ⚠️ Une seule chose n'a pas été reprise : le **regroupement par domaine**.
  `ModeleEmail` n'a ni `domaine` ni `categorie` — l'écran rangeait donc tout dans
  un unique groupe « général ». Ce n'était pas une capacité, c'était une promesse
  vide.

  ⚠️ Et une capacité a été **réparée en la reprenant** : « variables disponibles »
  découpait sur les virgules un champ qui est un **tableau JSON**, et affichait
  `{{ ["civilite" }}`. Recopier le geste aurait recopié le défaut.
-->
<script lang="ts">
  import Modale from '$lib/components/Modale.svelte';
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import { toast } from '$lib/components/Toast.svelte';
  import { safeHtml } from '$lib/sanitize';
  import { fmtDatetimeShort as fmt } from '$lib/date';

  let emailTemplates: any[] = [];
  let emailsLoading = true;
  let emailEdit: any | null = null;
  let emailSujet = '';
  let emailCorpsHtml = '';
  let emailCorpsTexte = '';
  let emailActif = true;
  let emailIntention = '';
  let emailApercu = false;

  //  L’INTENTION — ce que le message attend de son destinataire, rendu en
  //  bandeau au-dessus du corps par le gabarit commun. Les valeurs sont celles
  //  d’`app/utils/email.INTENTIONS`, que le serveur vérifie en liste blanche et
  //  refuse en 422 si elles divergent : c’est lui qui fait foi, pas cette liste.
  const INTENTIONS = [
    { valeur: '', label: 'Aucun bandeau' },
    { valeur: 'information', label: 'Pour information' },
    { valeur: 'action_requise', label: 'Action requise' },
    { valeur: 'reponse_attendue', label: 'Réponse attendue' },
    { valeur: 'archive', label: 'À conserver' },
  ];
  //  `variables_disponibles` est un tableau JSON en base — `'["civilite", "nom"]'`.
  //  L’écran « Designs » le découpait sur les VIRGULES et affichait donc
  //  `{{ ["civilite" }}`, crochets et guillemets compris. Le défaut est corrigé
  //  en le fusionnant ici (19/08/2026) plutôt que recopié : on analyse le JSON, et
  //  on ne retombe sur la virgule que pour une valeur ancienne écrite à plat.
  function variablesDeModele(brut: string | null | undefined): string[] {
    const texte = (brut ?? '').trim();
    if (!texte) return [];
    try {
      const lu = JSON.parse(texte);
      if (Array.isArray(lu)) return lu.map((v) => String(v).trim()).filter(Boolean);
    } catch { /* valeur héritée, écrite à plat */ }
    return texte.split(',').map((v) => v.trim()).filter(Boolean);
  }

  const labelIntention = (v: string | null | undefined) =>
    INTENTIONS.find((i) => i.valeur === (v ?? ''))?.label ?? '';
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
  //  `?? ''` et non `?? undefined` : `undefined` ne correspondrait à aucune
  //  option du sélecteur, qui s’afficherait vide au lieu d’« Aucun bandeau ».
  emailIntention = tpl.intention ?? '';
  emailApercu = false;
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
  intention: emailIntention,
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

  //  Remettre TOUS les modèles à leur design par défaut. Venait de l’écran
  //  « Designs des modèles d’e-mail », fusionné ici le 19/08/2026 : il montrait
  //  la même donnée sous un autre angle, et cette action était la seule qu’il
  //  portait seul (#307).
  let emailResetting = false;
  async function resetEmailTemplates() {
    if (!confirm('Remettre TOUS les modèles à leur design par défaut ? Les textes personnalisés seront perdus.')) return;
    emailResetting = true;
    try {
      const res = await api.post<{ message: string }>('/admin/modeles-email/reinitialiser', {});
      toast('success', res?.message ?? 'Designs réinitialisés.');
      await loadEmails();
    } catch (e: any) {
      toast('error', e.message ?? 'Erreur');
    } finally {
      emailResetting = false;
    }
  }

  onMount(loadEmails);
</script>

<p class="muted" style="margin-bottom:1rem">Modeles utilises pour les notifications automatiques.</p>
{#if emailsLoading}
<p class="muted">Chargement...</p>
{:else if emailTemplates.length === 0}
<div class="empty-state"><h3>Aucun modele trouve</h3></div>
{:else}
<div class="card" style="overflow:hidden">
<div class="action-row" style="margin-bottom:.75rem">
<button class="btn btn-outline btn-sm" on:click={resetEmailTemplates} disabled={emailResetting}
  title="Remet tous les modèles au design par défaut">
  {emailResetting ? 'Réinitialisation…' : '🔄 Réinitialiser les designs'}
</button>
</div>
<table class="table">
<thead>
<tr><th>Code</th><th>Nom</th><th>Sujet</th><th>Intention</th><th>Actif</th><th>Action</th></tr>
</thead>
<tbody>
{#each emailTemplates as tpl}
<tr>
<td><code style="font-size:.78rem">{tpl.code}</code></td>
<td style="font-size:.875rem">{tpl.libelle ?? tpl.nom ?? '—'}</td>
<td style="font-size:.8rem;color:var(--color-text-muted)">{tpl.sujet}</td>
<td>
{#if tpl.intention}<span class="badge badge-blue">{labelIntention(tpl.intention)}</span>
{:else}<span class="muted" style="font-size:.8rem">—</span>{/if}
</td>
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
<Modale titre="Modifier le modèle d'e-mail" classeBoite="modal-box card" styleBoite="max-width:680px"
  on:fermer={() => (emailEdit = null)}>
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:1rem">
      Modifier le modèle — <code style="font-size:.85rem">{emailEdit.code}</code>
    </h2>
    <div style="display:flex;flex-direction:column;gap:.6rem">
      <div class="field">
        <label for="email-sujet">Sujet</label>
        <input id="email-sujet" type="text" bind:value={emailSujet} style="font-family:monospace" />
      </div>
      <div class="field">
        <label for="email-intention">Intention — ce que le message attend du destinataire</label>
        <select id="email-intention" bind:value={emailIntention}>
          {#each INTENTIONS as i}<option value={i.valeur}>{i.label}</option>{/each}
        </select>
        <span class="field-hint">Affichée en bandeau au-dessus du corps, pour que le lecteur sache d'emblée s'il doit agir. « Aucun bandeau » n'affiche rien.</span>
      </div>
      <div class="field">
        <div style="display:flex;align-items:center;justify-content:space-between">
          <label for="email-corps-html">Corps HTML</label>
          <button class="btn btn-outline btn-sm" type="button" on:click={() => (emailApercu = !emailApercu)}>
            {emailApercu ? '✏️ Code' : '👁️ Aperçu'}
          </button>
        </div>
        {#if emailApercu}
          <div class="apercu-email">{@html safeHtml(emailCorpsHtml)}</div>
        {:else}
          <textarea id="email-corps-html" rows="10" bind:value={emailCorpsHtml} style="font-family:monospace;resize:vertical"></textarea>
        {/if}
      </div>
      <div class="field">
        <label for="email-corps-texte">Corps texte (fallback)</label>
        <textarea id="email-corps-texte" rows="4" bind:value={emailCorpsTexte} style="font-family:monospace;resize:vertical"></textarea>
      </div>
      <label class="case">
        <input type="checkbox" bind:checked={emailActif} />
        Actif
      </label>
      {#if emailEdit.variables_disponibles}
        <p class="variables-modele">
          <strong>Variables disponibles :</strong>
          {#each variablesDeModele(emailEdit.variables_disponibles) as v}
            <code>{`{{ ${v} }}`}</code>
          {/each}
        </p>
      {/if}
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" on:click={() => (emailEdit = null)} disabled={emailSaving}>Annuler</button>
      <button class="btn btn-primary" on:click={saveEmailEdit} disabled={emailSaving}>
        {emailSaving ? 'Enregistrement…' : 'Enregistrer'}
      </button>
    </div>
</Modale>
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
<thead class="sticky-head"><tr><th>Date</th><th>Template</th><th>Destinataire</th><th>Sujet</th><th>Statut</th></tr></thead>
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
<style>
	/*  Même cause que la télémétrie : ces règles étaient restées dans la page à
	    l'extraction. Le style part AVEC le balisage — `lint:classes-nues`. */
.apercu-email {
border: 1px solid var(--color-border); border-radius: var(--radius);
padding: .75rem; background: #fff; max-height: 340px; overflow: auto;
}
.variables-modele { font-size: .8rem; color: var(--color-text-muted); margin: .25rem 0 0; line-height: 1.8; }
.variables-modele code { margin-left: .25rem; }
</style>
