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

	let smtpConfig = {
		enabled: false,
		server: '',
		port: 587,
		from: '',
		from_name: '',
		username: '',
		password: '',
		starttls: true,
		ssl_tls: false,
	};
	let smtpSaving = false;
	let smtpPasswordSet = false;
	let smtpEditingPassword = true;
	let smtpTestEmail = '';
	let smtpTesting = false;

	//  ── Réception des réponses (IMAP) — #703 ────────────────────────────────
	//
	//  🔴 CET ÉCRAN MANQUAIT, et son absence rendait la fonction inexistante :
	//  la v3.73.0 a livré la relève, les clés `imap_*` et la tâche planifiée,
	//  mais AUCUN endroit pour les renseigner. Un réglage qu'on ne peut pas
	//  atteindre n'est pas un réglage — signalé à l'écran le 03/09/2026 :
	//  *« IMAP : je ne vois pas quoi faire »*.
	//
	//  Il vit dans l'onglet SMTP parce que c'est la MÊME boîte, chez le même
	//  hébergeur, avec les mêmes identifiants : les séparer aurait obligé à
	//  saisir deux fois ce qui ne fait qu'un.
	let imapConfig = {
		enabled: false,
		server: '',
		port: 993,
		username: '',
		password: '',
		dossier: 'INBOX',
		plancher: '2026-09-02',
	};
	let imapSaving = false;
	let imapPasswordSet = false;
	let imapEditingPassword = true;
	let imapTesting = false;
	let imapResultat = '';

	//  🔴 HYDRATER UNE SEULE FOIS, PUIS RELIRE — correctif du 03/09/2026.
	//
	//  Les valeurs arrivent APRÈS le montage : ce `$:` les reprend dès qu'elles
	//  changent, là où une affectation au montage figerait des champs vides.
	//
	//  Mais il RÉÉCRIVAIT le formulaire à chaque ré-exécution, avec le `valeurs`
	//  du montage. Signalé à l'écran : *« quand je fais enregistrer ça efface les
	//  champs Nom et password »* — la saisie partait bien vers le serveur, puis
	//  l'écran la remplaçait par ce qu'il avait lu au chargement, c'est-à-dire
	//  rien. On voyait un formulaire vidé, et on en concluait un échec.
	//
	//  Deux gestes, et il faut les deux :
	//    • cette garde — un formulaire ne s'hydrate qu'une fois, à l'arrivée des
	//      données, jamais par-dessus une saisie en cours ;
	//    • `relire()` après chaque enregistrement — sinon la garde figerait
	//      l'écran sur l'état du montage, et le prochain aller-retour entre
	//      onglets réafficherait des champs vides sur une base renseignée.
	let hydrate = false;
	$: if (!hydrate && valeurs && Object.keys(valeurs).length) {
		hydrate = true;
		hydrater(valeurs);
	}

	function hydrater(lues: Record<string, string>) {
		smtpConfig.enabled = lues['smtp_enabled'] === '1';
		smtpConfig.server = lues['smtp_server'] ?? '';
		smtpConfig.port = parseInt(lues['smtp_port'] ?? '587') || 587;
		smtpConfig.from = lues['smtp_from'] ?? '';
		smtpConfig.from_name = lues['smtp_from_name'] ?? '';
		smtpConfig.username = lues['smtp_username'] ?? '';
		smtpConfig.starttls = lues['smtp_starttls'] !== '0';
		smtpConfig.ssl_tls = lues['smtp_ssl_tls'] === '1';
		smtpPasswordSet = !!lues['smtp_password'];
		smtpEditingPassword = !smtpPasswordSet;

		imapConfig.enabled = lues['imap_enabled'] === '1';
		imapConfig.server = lues['imap_server'] ?? '';
		imapConfig.port = parseInt(lues['imap_port'] ?? '993') || 993;
		imapConfig.username = lues['imap_username'] ?? '';
		imapConfig.dossier = lues['imap_dossier'] || 'INBOX';
		imapConfig.plancher = lues['imap_plancher'] || '2026-09-02';
		imapPasswordSet = !!lues['imap_password'];
		imapEditingPassword = !imapPasswordSet;
	}

	/** Relit ce que le serveur a RETENU, et remet le formulaire dessus.
	 *
	 * 🔴 Relire plutôt que recopier ce qu'on vient d'envoyer : c'est la seule
	 * façon de montrer l'état réel. Une clé refusée, tronquée ou normalisée
	 * côté serveur se verrait ici — alors qu'un `{ ...valeurs, ...payload }`
	 * afficherait la saisie en la faisant passer pour un enregistrement.
	 *
	 * ⚠️ Et c'est ce qui rend l'aller-retour entre onglets juste : le composant
	 * est détruit puis recréé, donc réhydraté depuis `valeurs` — qui date du
	 * montage de la PAGE. Sans cette relecture, les champs reparaîtraient vides
	 * après un changement d'onglet, alors que la base est renseignée.
	 */
	async function relire() {
		try {
			valeurs = await api.get<Record<string, string>>('/config/admin');
			hydrater(valeurs);
		} catch {
			//  Muet à dessein : l'enregistrement a réussi, seul l'affichage est en
			//  retard. Un second message d'erreur ferait douter d'un succès réel.
		}
	}

	/** Reprend les paramètres d'envoi : même compte, même hébergeur. */
	function reprendreDuSmtp() {
		imapConfig.server = smtpConfig.server.replace(/^smtp\./, 'ssl0.').trim();
		imapConfig.username = smtpConfig.username || smtpConfig.from;
		//  🔴 « Copié » et non « repris — le mot de passe reste à saisir » : la
		//  première rédaction annonçait ce qui MANQUAIT, sur un ton indiscernable
		//  d'une erreur. Elle est apparue à quelqu'un qui venait justement de
		//  saisir son mot de passe, et a été lue comme un échec (03/09/2026).
		//  Un message de confirmation dit ce qui a été FAIT ; ce qui reste à faire
		//  est déjà écrit sous les champs concernés.
		toast('success', 'Serveur et identifiant copiés depuis la configuration d’envoi.');
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
			smtpConfig.password = '';
			await relire();
			toast('success', 'Configuration SMTP enregistrée.');
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			smtpSaving = false;
		}
	}

	async function saveImapConfig() {
		imapSaving = true;
		try {
			const payload: Record<string, string> = {
				imap_enabled: imapConfig.enabled ? '1' : '0',
				imap_server: imapConfig.server.trim(),
				imap_port: String(imapConfig.port),
				imap_username: imapConfig.username.trim(),
				imap_dossier: imapConfig.dossier.trim() || 'INBOX',
				imap_plancher: imapConfig.plancher,
			};
			//  Le mot de passe n'est envoyé QUE s'il a été saisi : l'API renvoie un
			//  marqueur à sa place, et le réexpédier l'écraserait par des points.
			if (imapConfig.password) payload['imap_password'] = imapConfig.password;
			await configApi.save(payload);
			imapConfig.password = '';
			await relire();
			toast('success', 'Réception des réponses enregistrée.');
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			imapSaving = false;
		}
	}

	async function testerImap() {
		imapTesting = true;
		imapResultat = '';
		try {
			const r: any = await api.post('/config/imap-test', {});
			imapResultat = r.message;
			toast('success', 'Connexion à la boîte réussie.');
		} catch (e: any) {
			imapResultat = e.message ?? 'Échec';
			toast('error', imapResultat);
		} finally {
			imapTesting = false;
		}
	}

	async function sendSmtpTest() {
		if (!smtpTestEmail) return;
		smtpTesting = true;
		try {
			await api.post('/config/smtp-test', { email: smtpTestEmail });
			toast('success', `E-mail de test envoyé à ${smtpTestEmail}`);
		} catch (e: any) {
			toast('error', e.message ?? "Échec de l'envoi");
		} finally {
			smtpTesting = false;
		}
	}
</script>

<section class="card config-section">
	<h2 class="config-section-title">
		<Icon name="message-square-text" size={17} />Configuration SMTP (notifications e-mail)
	</h2>
	<SectionFormulaire premiere icone="settings" titre="Serveur d’envoi">
		<div class="form-grid largeur-saisie">
			<label class="field" style="grid-column:span 2">
				<span class="case">
					<input type="checkbox" bind:checked={smtpConfig.enabled} />
					Activer l'envoi d'e-mails
				</span>
				<span class="field-hint"
					>Si activé, les notifications (réinitialisation de mot de passe, etc.) seront envoyées par
					e-mail.</span
				>
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
				<span class="field-hint"
					>Laisser vide si le serveur ne requiert pas d'authentification.</span
				>
			</label>
			<label class="field">
				Mot de passe SMTP
				<div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
					<input
						type="password"
						bind:value={smtpConfig.password}
						autocomplete="new-password"
						disabled={smtpPasswordSet && !smtpEditingPassword}
						placeholder={smtpPasswordSet && !smtpEditingPassword
							? 'Mot de passe masqué'
							: 'Nouveau mot de passe SMTP'}
						style="flex:1;min-width:220px"
					/>
					{#if smtpPasswordSet && !smtpEditingPassword}
						<button
							class="btn btn-outline btn-sm"
							type="button"
							on:click={() => {
								smtpEditingPassword = true;
								smtpConfig.password = '';
							}}
						>
							Changer
						</button>
					{/if}
				</div>
				<span class="field-hint"
					>{smtpPasswordSet
						? smtpEditingPassword
							? 'Saisissez le nouveau mot de passe puis cliquez sur Enregistrer.'
							: 'Mot de passe déjà enregistré. Cliquez sur « Changer » pour le remplacer.'
						: 'Requis si le serveur exige une authentification.'}</span
				>
			</label>
			<label class="field" style="grid-column:span 2">
				<span style="display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap">
					<span style="display:flex;align-items:center;gap:.4rem">
						<input
							type="checkbox"
							bind:checked={smtpConfig.starttls}
							style="width:1rem;height:1rem"
						/>
						STARTTLS (port 587)
					</span>
					<span style="display:flex;align-items:center;gap:.4rem">
						<input
							type="checkbox"
							bind:checked={smtpConfig.ssl_tls}
							style="width:1rem;height:1rem"
						/>
						SSL/TLS (port 465)
					</span>
				</span>
				<span class="field-hint"
					>STARTTLS et SSL/TLS sont mutuellement exclusifs. Décocher les deux pour connexion non
					chiffrée.</span
				>
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
					<input type="email" bind:value={smtpTestEmail} placeholder="destinataire@example.com" />
				</div>
				<button
					class="btn btn-outline"
					on:click={sendSmtpTest}
					disabled={smtpTesting || !smtpTestEmail}
				>
					{smtpTesting ? 'Envoi...' : '📨 Envoyer un e-mail de test'}
				</button>
			</div>
			<p style="font-size:.8rem;color:var(--color-text-muted);margin-top:.3rem">
				Envoie un e-mail de test avec la configuration SMTP actuellement enregistrée en base.
			</p>
		</div>
	</SectionFormulaire>

	<!--  🔴 RÉCEPTION DES RÉPONSES (#703). Placée APRÈS l'envoi et son test, parce
	      qu'elle en dépend : sans envoi, aucune réponse à recevoir. -->
	<SectionFormulaire icone="message-square-text" titre="Réception des réponses aux tickets">
		<div class="largeur-saisie">
			<p class="field-hint" style="margin-bottom:.75rem">
				Quand le syndic répond à un e-mail de ticket, sa réponse arrive dans la boîte d'envoi et
				personne ne la voit. Activée, cette relève la dépose dans le fil du ticket concerné, toutes
				les 10 minutes.
			</p>
		</div>
		<div class="form-grid largeur-saisie">
			<label class="field" style="grid-column:span 2">
				<span class="case">
					<input type="checkbox" bind:checked={imapConfig.enabled} />
					Relever les réponses
				</span>
				<span class="field-hint">
					Tant que cette case est décochée, rien n'est relevé — vous pouvez régler et tester sans
					conséquence.
				</span>
			</label>
			<label class="field">
				Serveur IMAP
				<input type="text" bind:value={imapConfig.server} placeholder="ssl0.ovh.net" />
			</label>
			<label class="field champ-court">
				Port
				<input type="number" bind:value={imapConfig.port} min="1" max="65535" placeholder="993" />
			</label>
			<label class="field">
				Nom d'utilisateur
				<input type="text" bind:value={imapConfig.username} placeholder="noreply@exemple.fr" />
				<span class="field-hint">Le même compte que l'envoi, chez le même hébergeur.</span>
			</label>
			<label class="field">
				Mot de passe
				<div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
					<input
						type="password"
						bind:value={imapConfig.password}
						autocomplete="new-password"
						disabled={imapPasswordSet && !imapEditingPassword}
						placeholder={imapPasswordSet && !imapEditingPassword
							? 'Mot de passe masqué'
							: 'Mot de passe de la boîte'}
						style="flex:1;min-width:220px"
					/>
					{#if imapPasswordSet && !imapEditingPassword}
						<button
							class="btn btn-outline btn-sm"
							type="button"
							on:click={() => {
								imapEditingPassword = true;
								imapConfig.password = '';
							}}
						>
							Changer
						</button>
					{/if}
				</div>
			</label>
			<label class="field champ-court">
				Dossier
				<input type="text" bind:value={imapConfig.dossier} placeholder="INBOX" />
			</label>
			<label class="field champ-court">
				Ne rien relever avant le
				<input type="date" bind:value={imapConfig.plancher} />
				<span class="field-hint"> Évite de rejouer d'anciens messages à la première relève. </span>
			</label>
		</div>
		<div class="largeur-saisie form-actions">
			<button class="btn btn-outline btn-sm" type="button" on:click={reprendreDuSmtp}>
				Reprendre les paramètres d'envoi
			</button>
			<button class="btn btn-primary" on:click={saveImapConfig} disabled={imapSaving}>
				{imapSaving ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
		<div class="largeur-saisie" style="margin-top:.75rem">
			<button class="btn btn-outline" on:click={testerImap} disabled={imapTesting}>
				{imapTesting ? 'Connexion…' : '📥 Tester la connexion'}
			</button>
			{#if imapResultat}
				<p class="imap-resultat">{imapResultat}</p>
			{/if}
			<p class="field-hint" style="margin-top:.3rem">
				Se connecte avec ce qui est <strong>enregistré</strong>, compte les messages non lus, et ne
				traite rien. Enregistrez d'abord.
			</p>
		</div>
	</SectionFormulaire>

	<SectionFormulaire icone="message-square-text" titre="Signature des e-mails">
		<div class="largeur-saisie">
			<label class="field">
				<textarea
					bind:value={emailFooter}
					rows="2"
					placeholder="— Envoyé depuis 5hostachy.fr"
					style="width:100%;resize:vertical;font-size:.85rem;font-family:monospace"></textarea>
				<span class="field-hint"
					>Texte ajouté automatiquement en bas de chaque e-mail envoyé par la plateforme.</span
				>
			</label>
		</div>
	</SectionFormulaire>

	<SectionFormulaire icone="building-2" titre="Référence copropriété (syndic)">
		<div class="largeur-saisie">
			<label class="field champ-moyen">
				<input type="text" bind:value={referenceCopro} placeholder="00213" />
				<span class="field-hint"
					>Référence de la copropriété auprès du syndic. Utilisée en préfixe dans les sujets
					d'e-mails envoyés au syndic.</span
				>
			</label>
		</div>
	</SectionFormulaire>

	<div class="largeur-saisie form-actions">
		<button class="btn btn-primary" on:click={saveSmtpConfig} disabled={smtpSaving}>
			{smtpSaving ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</section>

<style>
	/*  Le résultat du test : un encadré, pas un `toast`. Un toast disparaît, et
	    c'est précisément ce message qu'on relit en corrigeant un paramètre. */
	.imap-resultat {
		margin: 0.6rem 0 0;
		padding: 0.55rem 0.7rem;
		background: var(--color-bg);
		border-left: 3px solid var(--color-primary);
		border-radius: 0 var(--radius) var(--radius) 0;
		font-size: 0.85rem;
		white-space: pre-wrap;
	}
</style>
