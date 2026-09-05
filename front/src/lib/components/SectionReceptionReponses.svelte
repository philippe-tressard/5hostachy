<!--
  SectionReceptionReponses.svelte — la relève de la boîte, dans l'écran SMTP.

  Sortie d'`OngletSmtp.svelte` le 05/09/2026, sur refus du contrôle de
  modularité : ajouter la seconde adresse d'expédition (`contact@`) faisait
  passer l'écran de 500 à 521 lignes. Le découpage n'est pas qu'arithmétique —
  **envoyer** et **relever** sont deux sens de circulation, avec deux
  connexions, deux mots de passe et deux boutons de test.

  Ce qui les lie reste vrai, et c'est pourquoi les deux vivent dans le même
  onglet : c'est la MÊME boîte, chez le même hébergeur, avec les mêmes
  identifiants. D'où le bouton « Reprendre les paramètres d'envoi », qui reçoit
  ici en propriétés ce qu'il recopiait dans l'état voisin.

  🔴 CET ÉCRAN MANQUAIT AVANT LE 03/09/2026, et son absence rendait la fonction
  inexistante : la v3.73.0 a livré la relève, les clés `imap_*` et la tâche
  planifiée, mais AUCUN endroit pour les renseigner — *« IMAP : je ne vois pas
  quoi faire »*.
-->
<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import { api, config as configApi } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';

	/** Le serveur d'envoi, pour le bouton « Reprendre les paramètres d'envoi ». */
	export let serveurSmtp = '';
	/** L'identifiant d'envoi, même usage. */
	export let identifiantSmtp = '';

	//  L'écran parent relit la configuration après un enregistrement : les deux
	//  moitiés partagent la même table de clés, et une valeur enregistrée ici
	//  peut changer ce qu'il affiche.
	const dispatch = createEventDispatcher<{ enregistre: void }>();

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

	function reprendreDuSmtp() {
		imapConfig.server = serveurSmtp.replace(/^smtp\./, 'ssl0.').trim();
		imapConfig.username = identifiantSmtp;
		//  🔴 « Copié » et non « repris — le mot de passe reste à saisir » : la
		//  première rédaction annonçait ce qui MANQUAIT, sur un ton indiscernable
		//  d'une erreur. Elle est apparue à quelqu'un qui venait justement de
		//  saisir son mot de passe, et a été lue comme un échec (03/09/2026).
		//  Un message de confirmation dit ce qui a été FAIT ; ce qui reste à faire
		//  est déjà écrit sous les champs concernés.
		toast('success', 'Serveur et identifiant copiés depuis la configuration d’envoi.');
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
			dispatch('enregistre');
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

	async function relire() {
		const lues = await api.get<Record<string, string>>('/config/admin');
		imapConfig.enabled = lues['imap_enabled'] === '1';
		imapConfig.server = lues['imap_server'] ?? '';
		imapConfig.port = parseInt(lues['imap_port'] ?? '993') || 993;
		imapConfig.username = lues['imap_username'] ?? '';
		imapConfig.dossier = lues['imap_dossier'] || 'INBOX';
		imapConfig.plancher = lues['imap_plancher'] || '2026-09-02';
		imapPasswordSet = !!lues['imap_password'];
		imapEditingPassword = !imapPasswordSet;
	}

	onMount(relire);
</script>

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

<style>
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
