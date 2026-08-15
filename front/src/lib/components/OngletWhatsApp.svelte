<script lang="ts">
  //  Onglet « WhatsApp » de l'administration — extrait de `admin/+page.svelte`
  //  le 14/08/2026 : la page dépassait 2 200 lignes et la règle de modularité
  //  impose de découper le fichier quand on y touche. L'onglet est autonome
  //  (son état, ses appels, son rendu) ; seul le pied de message reste au
  //  parent, parce qu'il vit dans la configuration du site partagée avec
  //  l'onglet « Paramétrage site ».
  import { onMount } from 'svelte';
  import { api, config as configApi } from '$lib/api';
  import { configStore } from '$lib/stores/pageConfig';
  import { toast } from '$lib/components/Toast.svelte';
  import { fmtDatetimeShort } from '$lib/date';
  import Icon from '$lib/components/Icon.svelte';

  /** Configuration publique déjà chargée par la page (préremplit le formulaire). */
  export let cfgPublique: Record<string, string> = {};
  /** Une clé d'API est-elle déjà enregistrée côté serveur ? */
  export let apiKeySet = false;
  /** Pied de message — appartient à `siteConfig`, d'où le `bind:`. */
  export let footer = '';
  export let footerSaving = false;
  /** Enregistrement du pied de message, porté par la page. */
  export let onSaveFooter: () => unknown = () => {};

  let waConfig = { enabled: false, group_name: '', api_url: '', api_key: '', group_jid: '' };
  let waSaving = false;
  let waTestMessage = '\u{1F9EA} Test WhatsApp — si vous recevez ce message, la configuration est correcte ✅';
  let waTesting = false;
  let waStatus: { state: string; hasQR: boolean } | null = null;
  let waStatusLoading = false;
  let waQrTimestamp = Date.now();
  let waScheduled: { id: number; label: string; message: string; cron_rule: string; enabled: boolean; mis_a_jour_le: string | null }[] = [];
  let waScheduledSaving: Record<number, boolean> = {};
  let waLogs: { id: number; label: string; message: string; statut: string; erreur: string | null; envoye_le: string | null }[] = [];

  //  La page charge sa configuration en asynchrone : l'onglet peut être monté
  //  avant qu'elle arrive. On recopie dès qu'elle est là, une seule fois, pour
  //  ne pas écraser une saisie en cours.
  let prerempli = false;
  $: if (!prerempli && Object.keys(cfgPublique).length) {
    waConfig.enabled = cfgPublique['whatsapp_enabled'] === '1';
    waConfig.group_name = cfgPublique['whatsapp_group_name'] ?? '';
    waConfig.api_url = cfgPublique['whatsapp_api_url'] ?? '';
    waConfig.group_jid = cfgPublique['whatsapp_group_jid'] ?? '';
    prerempli = true;
  }

  onMount(() => {
    loadWaScheduled();
    loadWaLogs();
  });

  async function loadWaScheduled() {
    try { waScheduled = await api.get('/config/whatsapp-scheduled'); } catch { /**/ }
  }
  async function loadWaLogs() {
    try { waLogs = await api.get('/config/whatsapp-logs'); } catch { /**/ }
  }

  //  Un envoi a trois issues, pas deux : réussi, échoué, ou sans réponse du
  //  bridge. Ce dernier cas s'affichait « ❌ échec » alors que le message était
  //  le plus souvent bien arrivé dans le groupe — c'est cette lecture qui a
  //  fait renvoyer trois fois le message des encombrants le 14/08/2026.
  function waStatutIcone(statut: string): string {
    if (statut === 'envoyé') return '✅';
    if (statut === 'incertain') return '⚠️';
    if (statut === 'en cours') return '⏳';
    return '❌';
  }
  function waStatutStyle(statut: string): string {
    if (statut === 'envoyé') return 'background:#d1fae5;color:#065f46';
    if (statut === 'incertain' || statut === 'en cours') return 'background:#fef3c7;color:#92400e';
    return 'background:#fee2e2;color:#991b1b';
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
    } catch (e: any) {
      //  Le serveur répond 502 quand le bridge n'a pas acquitté : ce n'est pas
      //  un échec, et surtout ce n'est pas une invitation à recliquer.
      toast('error', e.message ?? 'Échec de l\'envoi');
    } finally {
      waTesting = false;
      loadWaLogs();
    }
  }

  async function checkWaStatus() {
    waStatusLoading = true;
    try {
      waStatus = await api.get('/config/whatsapp-status');
      if (waStatus?.state === 'waiting_qr') waQrTimestamp = Date.now();
    } catch (e: any) {
      waStatus = null;
      toast('error', e.message ?? 'Impossible de joindre le bridge');
    } finally {
      waStatusLoading = false;
    }
  }

  function refreshWaQr() {
    waQrTimestamp = Date.now();
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
      if (waConfig.api_key) apiKeySet = true;
      waConfig.api_key = '';
      toast('success', 'Configuration WhatsApp enregistrée.');
    } catch (e: any) {
      toast('error', e.message ?? 'Erreur');
    } finally {
      waSaving = false;
    }
  }
</script>

<section class="config-section">
  <h2 class="config-section-title">
    <Icon name="whatsapp" size={18} />
    Configuration WhatsApp
  </h2>
  <div class="form-grid largeur-saisie">
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
        placeholder={apiKeySet ? '••••••  (clé déjà configurée — laisser vide pour conserver)' : 'Entrez la clé API du bridge WhatsApp'} />
      <span class="field-hint">{apiKeySet ? 'Une clé est déjà configurée. Laissez ce champ vide pour la conserver.' : 'Requis pour l\'authentification au bridge WhatsApp.'}</span>
    </label>
  </div>
  <div class="largeur-saisie" style="display:flex;justify-content:flex-end;margin-top:.75rem">
    <button class="btn btn-primary" on:click={saveWaConfig} disabled={waSaving}>
      {waSaving ? 'Enregistrement...' : 'Enregistrer'}
    </button>
  </div>
  <hr class="largeur-saisie" style="border:none;border-top:1px solid var(--color-border);margin:.75rem 0">
  <div class="largeur-saisie">
    <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.5rem">
      <p style="font-size:.85rem;font-weight:600;color:var(--color-text-muted);margin:0">&#x1F9EA; Tester la configuration</p>
      <button class="btn btn-outline" style="font-size:.75rem;padding:.15rem .5rem" on:click={checkWaStatus} disabled={waStatusLoading}>
        {waStatusLoading ? '...' : '\u{1F504} Statut'}
      </button>
      {#if waStatus}
        <span style="font-size:.8rem;padding:.1rem .5rem;border-radius:4px;{waStatus.state === 'open' ? 'background:#d1fae5;color:#065f46' : 'background:#fee2e2;color:#991b1b'}">
          {waStatus.state === 'open' ? '✅ Connecté' : waStatus.state === 'waiting_qr' ? '\u{1F4F1} En attente du QR' : '❌ ' + waStatus.state}
        </span>
      {/if}
    </div>
    {#if waStatus?.state === 'waiting_qr'}
      <div style="margin-top:.75rem;padding:.75rem;border:2px solid #f59e0b;border-radius:8px;background:#fffbeb;max-width:360px">
        <p style="margin:0 0 .5rem;font-size:.85rem;font-weight:600;color:#92400e">
          &#x26A0;&#xFE0F; Bridge déconnecté — scannez ce QR code avec WhatsApp
        </p>
        <p style="margin:0 0 .75rem;font-size:.78rem;color:#92400e">
          WhatsApp → Appareils connectés → Connecter un appareil
        </p>
        <img
          src="/api/config/whatsapp-qr?t={waQrTimestamp}"
          alt="QR code WhatsApp"
          style="display:block;width:220px;height:220px;border-radius:4px;border:1px solid #f59e0b"
        />
        <div style="display:flex;gap:.5rem;margin-top:.5rem;align-items:center">
          <button class="btn btn-outline" style="font-size:.75rem;padding:.15rem .5rem" type="button" on:click={refreshWaQr}>
            &#x1F504; Rafraîchir le QR
          </button>
          <button class="btn btn-outline" style="font-size:.75rem;padding:.15rem .5rem" type="button" on:click={checkWaStatus}>
            &#x2705; Vérifier la connexion
          </button>
        </div>
      </div>
    {/if}
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
        {waTesting ? 'Envoi...' : '\u{1F4E8} Envoyer le test'}
      </button>
    </div>
    <p style="font-size:.8rem;color:var(--color-text-muted);margin-top:.3rem">Envoie le message ci-dessus sur le groupe WhatsApp configuré.</p>
  </div>

  <hr class="largeur-saisie" style="border:none;border-top:1px solid var(--color-border);margin:1rem 0">

  <!-- Messages planifiés -->
  <div class="largeur-saisie">
    <p style="font-size:.85rem;font-weight:600;margin-bottom:.5rem;color:var(--color-text-muted)">&#x1F4C5; Messages planifiés (envoi automatique)</p>
    <p style="font-size:.78rem;color:var(--color-text-muted);margin-bottom:1rem;line-height:1.5">
      &#x1F4A1; Markdown WhatsApp : <strong>*gras*</strong> | <em>_italique_</em> | <s>~barré~</s> | Sauts de ligne (Enter)
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
            {waScheduledSaving[item.id] ? '...' : '\u{1F4BE} Enregistrer'}
          </button>
        </div>
      </div>
    {/each}
  </div>

  <hr class="largeur-saisie" style="border:none;border-top:1px solid var(--color-border);margin:1rem 0">

  <!-- Footer des messages -->
  <div class="largeur-saisie">
    <p style="font-size:.85rem;font-weight:600;margin-bottom:.5rem;color:var(--color-text-muted)">&#x1F4DD; Footer des messages (markdown WhatsApp)</p>
    <label class="field-label">
      <textarea
        class="input input-sm"
        bind:value={footer}
        rows="2"
        placeholder="— Le Conseil Syndical"
        style="width:100%;resize:vertical;font-size:.85rem;font-family:monospace"
      ></textarea>
      <span class="field-hint">Texte qui finalise chaque message (markdown WhatsApp autorisé : *gras*, _italique_, ~barré~).</span>
    </label>
  </div>

  <div class="largeur-saisie" style="display:flex;justify-content:flex-end;margin-top:.5rem">
    <button class="btn btn-primary" style="font-size:.8rem;padding:.2rem .6rem" on:click={onSaveFooter} disabled={footerSaving}>
      {footerSaving ? '...' : '\u{1F4BE} Enregistrer'}
    </button>
  </div>

  <hr class="largeur-saisie" style="border:none;border-top:1px solid var(--color-border);margin:1rem 0">

  <!-- Historique des envois -->
  <div class="largeur-saisie">
    <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.5rem">
      <p style="font-size:.85rem;font-weight:600;color:var(--color-text-muted);margin:0">&#x1F4CB; Historique des envois (6 derniers)</p>
      <button class="btn btn-outline" style="font-size:.7rem;padding:.1rem .4rem" on:click={loadWaLogs} aria-label="Rafraîchir l'historique">&#x1F504;</button>
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
                <span style="padding:.1rem .3rem;border-radius:4px;font-size:.7rem;{waStatutStyle(log.statut)}">
                  {waStatutIcone(log.statut)} {log.statut}
                </span>
                <span style="color:var(--color-text-muted);font-size:.75rem">{log.envoye_le ? fmtDatetimeShort(log.envoye_le) : ''}</span>
              </div>
            </div>
            <p style="margin:0;white-space:pre-wrap;color:var(--color-text-muted);font-size:.78rem">{log.message.length > 120 ? log.message.slice(0, 120) + '…' : log.message}</p>
            {#if log.erreur}
              <p style="margin:.2rem 0 0;color:#991b1b;font-size:.75rem">&#x26A0;&#xFE0F; {log.erreur}</p>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</section>
