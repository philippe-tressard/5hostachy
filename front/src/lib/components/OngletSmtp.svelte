<!--
  L'onglet **SMTP** de l'administration : serveur d'envoi, test, signature des
  e-mails, référence copropriété.

  POURQUOI CE COMPOSANT (19/08/2026). `admin/+page.svelte` dépassait 1 950 lignes,
  et le garde-fou de modularité (rang 1) a refusé les huit lignes qu'ajoutait la
  mise au motif `SectionFormulaire` de ses sous-sections. La règle est « on
  découpe QUAND on y touche » — et #453 dit ce qui se passe quand on y répond en
  tassant des attributs au lieu de découper : le garde-fou devient une formalité.

  Même geste et même forme qu'`OngletWhatsApp.svelte`, extrait avant lui : l'état
  et les appels réseau vivent ici, la page ne garde que le choix de l'onglet.

  ⚠️ `email_footer` et `reference_copro` appartiennent à `siteConfig`, pas à la
  configuration SMTP — ils sont pourtant enregistrés par le même bouton, parce
  qu'ils ne concernent que les e-mails. Ils sont donc passés en `bind:`, et c'est
  la page qui reste propriétaire de `siteConfig`.
-->
<script lang="ts">
  import Icon from '$lib/components/Icon.svelte';
  import { api, config as configApi } from '$lib/api';
  import { toast } from '$lib/components/Toast.svelte';
  import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';

  /** Signature ajoutée en bas de chaque e-mail — appartient à `siteConfig`. */
  export let emailFooter = '';
  /** Référence de la copropriété auprès du syndic — appartient à `siteConfig`. */
  export let referenceCopro = '';
  /** Valeurs lues au chargement par la page (`adminCfg`). */
  export let valeurs: Record<string, string> = {};

  let smtpConfig = { enabled: false, server: '', port: 587, from: '', from_name: '', username: '', password: '', starttls: true, ssl_tls: false };
  let smtpSaving = false;
  let smtpPasswordSet = false;
  let smtpEditingPassword = true;
  let smtpTestEmail = '';
  let smtpTesting = false;

  //  Les valeurs arrivent APRÈS le montage (la page les charge) : un `$:` les
  //  reprend dès qu'elles changent, là où une affectation au montage figerait
  //  le formulaire sur des champs vides.
  $: if (valeurs && Object.keys(valeurs).length) {
    smtpConfig.enabled = valeurs['smtp_enabled'] === '1';
    smtpConfig.server = valeurs['smtp_server'] ?? '';
    smtpConfig.port = parseInt(valeurs['smtp_port'] ?? '587') || 587;
    smtpConfig.from = valeurs['smtp_from'] ?? '';
    smtpConfig.from_name = valeurs['smtp_from_name'] ?? '';
    smtpConfig.username = valeurs['smtp_username'] ?? '';
    smtpConfig.starttls = valeurs['smtp_starttls'] !== '0';
    smtpConfig.ssl_tls = valeurs['smtp_ssl_tls'] === '1';
    smtpPasswordSet = !!valeurs['smtp_password'];
    smtpEditingPassword = !smtpPasswordSet;
  }

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
        email_footer: emailFooter,
        reference_copro: referenceCopro,
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
</script>

<section class="card config-section">
  <h2 class="config-section-title"><Icon name="message-square-text" size={17} />Configuration SMTP (notifications e-mail)</h2>
  <SectionFormulaire premiere icone="settings" titre="Serveur d’envoi">
  <div class="form-grid largeur-saisie">
    <label class="field" style="grid-column:span 2">
      <span class="case">
        <input type="checkbox" bind:checked={smtpConfig.enabled} />
        Activer l'envoi d'e-mails
      </span>
      <span class="field-hint">Si activé, les notifications (réinitialisation de mot de passe, etc.) seront envoyées par e-mail.</span>
    </label>
    <label class="field">
      Serveur SMTP
      <input type="text" bind:value={smtpConfig.server} placeholder="smtp.example.com" />
    </label>
    <label class="field champ-court">
      Port
      <input type="number" bind:value={smtpConfig.port} min="1" max="65535" placeholder="587" />
    </label>
    <label class="field">
      Adresse expéditeur (From)
      <input type="email" bind:value={smtpConfig.from} placeholder="noreply@example.com" />
    </label>
    <label class="field">
      Nom expéditeur
      <input type="text" bind:value={smtpConfig.from_name} placeholder="Résidence du Parc" />
    </label>
    <label class="field">
      Nom d'utilisateur SMTP
      <input type="text" bind:value={smtpConfig.username} placeholder="user@example.com" />
      <span class="field-hint">Laisser vide si le serveur ne requiert pas d'authentification.</span>
    </label>
    <label class="field">
      Mot de passe SMTP
      <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
        <input
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
    <label class="field" style="grid-column:span 2">
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
  <div class="largeur-saisie form-actions">
    <button class="btn btn-primary" on:click={saveSmtpConfig} disabled={smtpSaving}>
      {smtpSaving ? 'Enregistrement…' : 'Enregistrer'}
    </button>
  </div>
  </SectionFormulaire>

  <SectionFormulaire icone="activity" titre="Tester la configuration">
  <div class="largeur-saisie">
    <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
      <div class="field champ-en-ligne" style="flex:1;min-width:220px">
        <input
          type="email"
          bind:value={smtpTestEmail}
          placeholder="destinataire@example.com"
        />
      </div>
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
  </SectionFormulaire>

  <SectionFormulaire icone="message-square-text" titre="Signature des e-mails">
  <div class="largeur-saisie">
    <label class="field">
      <textarea
        bind:value={emailFooter}
        rows="2"
        placeholder="— Envoyé depuis 5hostachy.fr"
        style="width:100%;resize:vertical;font-size:.85rem;font-family:monospace"
      ></textarea>
      <span class="field-hint">Texte ajouté automatiquement en bas de chaque e-mail envoyé par la plateforme.</span>
    </label>
  </div>
  </SectionFormulaire>

  <SectionFormulaire icone="building-2" titre="Référence copropriété (syndic)">
  <div class="largeur-saisie">
    <label class="field champ-moyen">
      <input
        type="text"
        bind:value={referenceCopro}
        placeholder="00213"
      />
      <span class="field-hint">Référence de la copropriété auprès du syndic. Utilisée en préfixe dans les sujets d'e-mails envoyés au syndic.</span>
    </label>
  </div>
  </SectionFormulaire>

  <div class="largeur-saisie form-actions">
    <button class="btn btn-primary" on:click={saveSmtpConfig} disabled={smtpSaving}>
      {smtpSaving ? 'Enregistrement…' : 'Enregistrer'}
    </button>
  </div>
</section>
