<script lang="ts">
	import EntetePage from '$lib/components/EntetePage.svelte';
	import ChangementMotDePasse from '$lib/components/ChangementMotDePasse.svelte';
	import { DEFAUTS_NOTIFS } from '$lib/preferences';
	import PreferencesAffichageNotifs from '$lib/components/PreferencesAffichageNotifs.svelte';
	import { onMount } from 'svelte';
	import { currentUser, setUser } from '$lib/stores/auth';
	import { auth as authApi, lots as lotsApi, uploads as uploadsApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import ImageUpload from '$lib/components/ImageUpload.svelte';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { setTelemetryOptOut } from '$lib/telemetry';
	import { fmtDateShort as fmtDate, fmtDatetimeShort as fmtDatetime } from '$lib/date';
	import ChargementPartiel from '$lib/components/ChargementPartiel.svelte';
	import HistoriqueDemandes from '$lib/components/HistoriqueDemandes.svelte';
	import { STATUT_DEMANDE_BADGE, STATUT_DEMANDE_LABEL } from '$lib/demandes';
	import { essayer, messagePartiel } from '$lib/chargement';

	$: _pc = getPageConfig($configStore, 'profil', defautsDePage('profil'));
	$: _siteNom = $siteNomStore;

	// ── Infos personnelles ─────────────────────────────────────────────────────
	let prenom = '';
	let nom = '';
	let telephone = '';
	let societe = '';
	let fonction = '';
	let email = '';
	let saving = false;
	let uploadingAvatar = false;

	// ── Notifications ─────────────────────────────────────────────────────────
	let valeursNotifs: Record<string, boolean> = { ...DEFAUTS_NOTIFS };
	let restreindreAMesBatiments = false;

	// ── Lots ──────────────────────────────────────────────────────────────────
	let mesLots: any[] = [];

	// ── Demandes de modif profil ───────────────────────────────────────────────
	let demandes: any[] = [];
	let demandesLoading = true;
	/** Non vide = une des trois listes du profil n'a pas pu être chargée. */
	let erreurChargement = '';
	let showDemandeForm = false;
	let batiments: { id: number; numero: string }[] = [];
	let demandeStatut = '';
	let demandeBatimentId: number | null = null;
	let demandeMotif = '';
	let savingDemande = false;
	let arrivantBatimentNumero = '';
	let arrivantAncienResident = '';
	let arrivantAncienResidentInconnu = false;
	let savingArrivant = false;
	let arrivantChoix: '' | 'nouvel_arrivant' | 'deja_resident' = '';

	// ── RGPD Télémétrie ───────────────────────────────────────────────────────
	let optOutTelemetrie = false;
	let savingOptOut = false;
	let deletingTelemetrie = false;
	let exportingTelemetrie = false;
	let confirmDeleteTelemetrie = false;

	$: demandePending = demandes.find((d) => d.statut_demande === 'en_attente') ?? null;

	// ── Labels ─────────────────────────────────────────────────────────────────
	const statutLabels: Record<string, string> = {
		copropriétaire_résident: 'Copropriétaire résident',
		copropriétaire_bailleur: 'Copropriétaire bailleur',
		locataire: 'Locataire',
		syndic: 'Syndic',
		mandataire: 'Mandataire',
	};

	const roleLabels: Record<string, string> = {
		résident: 'Résident',
		locataire: 'Locataire',
		copropriétaire_résident: 'Copropriétaire Résident',
		copropriétaire_bailleur: 'Copropriétaire Bailleur',
		bailleur: 'Copropriétaire Bailleur',
		syndic: 'Syndic',
		mandataire: 'Mandataire',
		conseil_syndical: 'Conseil syndical',
		admin: 'Admin',
	};

	const roleBadge: Record<string, string> = {
		résident: 'badge-gray',
		locataire: 'badge-gray',
		copropriétaire_résident: 'badge-teal',
		copropriétaire_bailleur: 'badge-purple',
		bailleur: 'badge-purple',
		syndic: 'badge-orange',
		mandataire: 'badge-yellow',
		conseil_syndical: 'badge-blue',
		admin: 'badge-orange',
	};

	//  ⚠️ Le vocabulaire d'une demande vit dans `$lib/demandes` : cette page ET
	//  `HistoriqueDemandes` le lisent. Je l'avais d'abord emporté avec la table
	//  extraite — la page s'en sert aussi, quarante lignes plus haut.
	$: derniereConnexion = ($currentUser as any)?.derniere_connexion ?? null;

	// ── Init ──────────────────────────────────────────────────────────────────
	//  L'initialisation suit le STORE, pas le montage : le layout `(app)` peuple
	//  `currentUser` dans SON `onMount`, et les `onMount` des enfants s'exécutent
	//  AVANT ceux du parent. Sur un rechargement direct de /profil, cette page
	//  lisait donc un store vide et laissait prénom, nom et e-mail blancs —
	//  « Enregistrer » aurait écrasé les vraies valeurs (signalé le 14/08/2026).
	//  Le drapeau évite d'écraser une saisie en cours quand `setUser` réassigne.
	let champsInitialises = false;
	$: if ($currentUser && !champsInitialises) {
		champsInitialises = true;
		initialiserDepuis($currentUser);
	}

	function initialiserDepuis(u: any) {
		{
			// bloc nu : le corps n'a pas changé, seul son déclencheur

			prenom = u.prenom ?? '';
			nom = u.nom ?? '';
			telephone = (u as any).telephone ?? '';
			societe = u.societe ?? '';
			fonction = (u as any).fonction ?? '';
			email = u.email ?? '';
			arrivantBatimentNumero = (u as any).batiment_nom?.replace(/[^0-9]/g, '') ?? '';
			optOutTelemetrie = u.opt_out_telemetrie ?? false;

			// Démarche arrivant : lire depuis la base (fallback localStorage pour migration)
			if (u.demarche_arrivant === 'nouvel_arrivant' || u.demarche_arrivant === 'deja_resident') {
				arrivantChoix = u.demarche_arrivant;
			} else {
				const savedChoix = localStorage.getItem(`profil_arrivant_choix_${u.id}`);
				if (savedChoix === 'nouvel_arrivant' || savedChoix === 'deja_resident') {
					arrivantChoix = savedChoix;
					// Migrer vers la base
					authApi
						.updateMe({ demarche_arrivant: savedChoix })
						.then((updated) => setUser(updated))
						.catch(() => {});
				}
			}

			//  Préférences d'e-mail. L'ancien format (huit clés `*_app` / `*_mail`) est
			//  converti par la migration 0145 ; le repli sur les défauts couvre les
			//  comptes qu'elle n'aurait pas atteints — un compte créé entre le
			//  déploiement de l'API et celui du front, par exemple.
			try {
				const lues = JSON.parse(u.preferences_notifications || '{}');
				for (const cle of Object.keys(DEFAUTS_NOTIFS)) {
					valeursNotifs[cle] = typeof lues?.[cle] === 'boolean' ? lues[cle] : DEFAUTS_NOTIFS[cle];
				}
			} catch {
				valeursNotifs = { ...DEFAUTS_NOTIFS };
			}
			valeursNotifs = valeursNotifs; // Svelte 4 : réassigner pour propager
			restreindreAMesBatiments = u.restreindre_a_mes_batiments ?? false;
		}
	}

	onMount(async () => {
		//  🔴 Aucune de ces trois listes n'a d'état « vide » à l'écran : elles se
		//  rendent `{#if …length > 0}`. Un échec ne produisait donc RIEN — ni
		//  liste, ni message —, et la ligne « Lot(s) » disparaissait comme si le
		//  compte n'en avait aucun (#522). D'où le bandeau plutôt qu'un état de
		//  liste : il n'y a pas de vide à distinguer, il y a un silence à rompre.
		const [[lots, eLots], [bats, eBats]] = await Promise.all([
			essayer<any[]>(lotsApi.mesList(), []),
			essayer<any[]>(authApi.batiments(), []),
		]);
		mesLots = lots;
		batiments = bats;

		const [dem, eDem] = await essayer<any[]>(authApi.mesDemandes(), []);
		demandes = dem;
		demandesLoading = false;
		erreurChargement = messagePartiel(eLots, eBats, eDem);
	});

	// ── Actions ───────────────────────────────────────────────────────────────
	async function saveProfile() {
		saving = true;
		try {
			const emailChanged = email && email !== $currentUser?.email;
			const updated = await authApi.updateMe({
				prenom,
				nom,
				telephone: telephone || null,
				societe: societe || null,
				fonction: fonction || null,
				...(emailChanged ? { email } : {}),
			});
			setUser(updated);
			toast('success', 'Profil mis à jour');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			saving = false;
		}
	}

	async function handleAvatarChange(e: CustomEvent<File>) {
		uploadingAvatar = true;
		try {
			const { url } = await uploadsApi.avatar(e.detail);
			const updated = { ...$currentUser!, photo_url: url };
			setUser(updated as any);
			toast('success', 'Photo de profil mise à jour');
		} catch (err) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur upload');
		} finally {
			uploadingAvatar = false;
		}
	}

	async function saveNotifs(valeurs: Record<string, boolean>, restreindre: boolean) {
		const prefs = JSON.stringify(valeurs);
		try {
			const updated = await authApi.updateMe({
				preferences_notifications: prefs,
				restreindre_a_mes_batiments: restreindre,
			});
			setUser(updated);
			valeursNotifs = valeurs;
			restreindreAMesBatiments = restreindre;
			toast('success', 'Préférences enregistrées');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : "Erreur lors de l'enregistrement");
		}
	}

	async function soumettreDemandeModif() {
		if (!demandeStatut && !demandeBatimentId) {
			toast('error', "Sélectionnez au moins un changement (profil d'utilisateur ou bâtiment)");
			return;
		}
		savingDemande = true;
		try {
			const d = await authApi.demanderModification({
				statut_souhaite: demandeStatut || null,
				batiment_id_souhaite: demandeBatimentId || null,
				motif: demandeMotif || null,
			});
			demandes = [d, ...demandes];
			showDemandeForm = false;
			demandeStatut = '';
			demandeBatimentId = null;
			demandeMotif = '';
			toast('success', 'Demande envoyée au conseil syndical');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingDemande = false;
		}
	}

	async function declarerNouvelArrivant() {
		if (!arrivantAncienResidentInconnu && !arrivantAncienResident.trim()) {
			toast('error', "Indiquez l'ancien résident ou cochez 'Je ne sais pas'.");
			return;
		}
		savingArrivant = true;
		try {
			const batimentFinal = arrivantBatimentNumero
				? `Bât. ${arrivantBatimentNumero}`
				: ($currentUser?.batiment_nom || '').trim() || null;
			await authApi.declarerNouvelArrivant({
				batiment: batimentFinal,
				ancien_resident: arrivantAncienResidentInconnu
					? null
					: arrivantAncienResident.trim() || null,
				ancien_resident_inconnu: arrivantAncienResidentInconnu,
			});
			arrivantChoix = 'nouvel_arrivant';
			// Rafraîchir le user en store (la base a été mise à jour côté serveur)
			authApi
				.me()
				.then((u) => setUser(u))
				.catch(() => {});
			toast('success', 'Déclaration Nouvel Arrivant envoyée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingArrivant = false;
		}
	}

	async function declarerDejaResident() {
		try {
			const updated = await authApi.updateMe({ demarche_arrivant: 'deja_resident' });
			setUser(updated);
			arrivantChoix = 'deja_resident';
			toast('success', 'Choix enregistré : déjà résident (aucune démarche nouvel arrivant).');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} icone={_pc.icone || 'user'} />

<ChargementPartiel
	erreur={erreurChargement}
	consequence="Vos lots, la liste des bâtiments et l'historique de vos demandes peuvent être absents de cet écran."
/>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

<div class="largeur-saisie">
	<!-- ── Avatar + Infos personnelles ──────────────────────────────────────── -->
	<section class="card" style="margin-bottom:1.5rem">
		<h2 class="section-title">Informations personnelles</h2>

		<div style="display:flex;justify-content:center;margin-bottom:1.25rem">
			<ImageUpload
				currentUrl={$currentUser?.photo_url}
				placeholder="&#x1F464;"
				label="Changer la photo"
				shape="circle"
				previewSize="100px"
				uploading={uploadingAvatar}
				on:change={handleAvatarChange}
			/>
		</div>

		<form on:submit|preventDefault={saveProfile}>
			<div class="form-row">
				<div class="field">
					<label for="p-prenom">Prénom *</label>
					<input id="p-prenom" type="text" bind:value={prenom} required />
				</div>
				<div class="field">
					<label for="p-nom">Nom *</label>
					<input id="p-nom" type="text" bind:value={nom} required />
				</div>
			</div>
			<div class="field">
				<label for="p-email">Adresse e-mail *</label>
				<input id="p-email" type="email" bind:value={email} required />
			</div>
			<div class="field">
				<label for="p-tel">Téléphone</label>
				<input id="p-tel" type="tel" bind:value={telephone} placeholder="+33 6 00 00 00 00" />
			</div>
			<div class="field">
				<label for="p-societe">Société</label>
				<input
					id="p-societe"
					type="text"
					bind:value={societe}
					placeholder="Ex : Agence Dupont, Cabinet ABC…"
				/>
			</div>
			<div class="field">
				<label for="p-fonction">Fonction</label>
				<input
					id="p-fonction"
					type="text"
					bind:value={fonction}
					placeholder="Ex : Gestionnaire, Mandataire…"
				/>
			</div>
			<div class="form-actions">
				<button type="submit" class="btn btn-primary" disabled={saving}>
					{saving ? 'Enregistrement…' : 'Enregistrer'}
				</button>
			</div>
		</form>
	</section>

	<!-- ── Informations résidence ────────────────────────────────────────────── -->
	<section class="card" style="margin-bottom:1.5rem">
		<h2 class="section-title">Résidence &amp; statut</h2>

		<dl class="info-grid">
			<dt>Profil d'utilisateur</dt>
			<dd>{statutLabels[$currentUser?.statut ?? ''] ?? $currentUser?.statut ?? '—'}</dd>

			<dt>Bâtiment</dt>
			<dd>{$currentUser?.batiment_nom ?? '—'}</dd>

			{#if mesLots.length > 0}
				<dt>Lot{mesLots.length > 1 ? 's' : ''}</dt>
				<dd>
					{#each mesLots as lot (lot.id)}
						<span style="display:block">
							{#if lot.batiment_nom}{lot.batiment_nom} —
							{/if}
							N° {lot.numero}
							· {(
								{ appartement: 'Appartement', cave: 'Cave', parking: 'Parking' } as Record<
									string,
									string
								>
							)[lot.type] ?? lot.type}
							{#if lot.type_appartement} ({lot.type_appartement}){/if}
							{#if lot.etage !== null && lot.etage !== undefined}
								· {lot.etage === 0
									? 'RDC'
									: lot.etage < 0
										? 'SS ' + Math.abs(lot.etage)
										: lot.etage + (lot.etage === 1 ? 'er' : 'ème') + ' étage'}
							{/if}
							{#if lot.superficie} · {lot.superficie} m²{/if}
						</span>
					{/each}
				</dd>
			{/if}

			<dt>Rôle(s)</dt>
			<dd style="display:flex;gap:0.35rem;flex-wrap:wrap">
				{#each $currentUser?.roles?.length ? $currentUser.roles : [$currentUser?.role ?? 'résident'] as r (r)}
					<span class="badge {roleBadge[r] ?? 'badge-gray'}">{roleLabels[r] ?? r}</span>
				{/each}
			</dd>

			<dt>Statut du compte</dt>
			<dd>
				{#if $currentUser?.actif}
					<span class="badge badge-green">Actif</span>
				{:else}
					<span class="badge badge-red">Inactif</span>
				{/if}
			</dd>

			<dt>Membre depuis</dt>
			<dd>{fmtDate($currentUser?.cree_le)}</dd>

			<dt>Dernière connexion</dt>
			<dd>{fmtDatetime(derniereConnexion)}</dd>
		</dl>

		<!-- Demande de modification -->
		{#if demandePending}
			<div class="info-banner info-yellow" style="margin-top:1rem">
				<strong>Demande en attente</strong> :
				{#if demandePending.statut_souhaite}
					changement de type vers «&nbsp;{statutLabels[demandePending.statut_souhaite] ??
						demandePending.statut_souhaite}&nbsp;»
				{/if}
				{#if demandePending.statut_souhaite && demandePending.batiment_nom_souhaite}&nbsp;+&nbsp;{/if}
				{#if demandePending.batiment_nom_souhaite}
					déménagement vers {demandePending.batiment_nom_souhaite}
				{/if}
				<span
					class="badge {STATUT_DEMANDE_BADGE[demandePending.statut_demande]}"
					style="margin-left:.5rem"
				>
					{STATUT_DEMANDE_LABEL[demandePending.statut_demande]}
				</span>
			</div>
		{:else}
			<button
				class="btn btn-outline btn-sm"
				style="margin-top:1rem"
				on:click={() => (showDemandeForm = !showDemandeForm)}
			>
				{showDemandeForm ? 'Annuler' : '✏️ Demander une modification (profil / bâtiment)'}
			</button>
		{/if}

		{#if showDemandeForm && !demandePending}
			<div class="demande-form" style="margin-top:1rem">
				<p class="hint" style="margin-bottom:.75rem">
					Les modifications du profil d'utilisateur et du bâtiment sont soumises à validation du
					conseil syndical.
				</p>
				<div class="field">
					<label for="dm-statut">Nouveau profil d'utilisateur</label>
					<select id="dm-statut" bind:value={demandeStatut}>
						<option value="">— Inchangé —</option>
						<option value="copropriétaire_résident">Copropriétaire résident</option>
						<option value="copropriétaire_bailleur">Copropriétaire bailleur</option>
						<option value="locataire">Locataire</option>
						<option value="mandataire">Mandataire</option>
						<option value="syndic">Syndic</option>
					</select>
				</div>
				<div class="field">
					<label for="dm-bat">Bâtiment souhaité</label>
					<select id="dm-bat" bind:value={demandeBatimentId}>
						<option value={null}>— Inchangé —</option>
						{#each batiments as bat (bat.id)}
							<option value={bat.id}>Bât. {bat.numero}</option>
						{/each}
					</select>
				</div>
				<div class="field">
					<label for="dm-motif">Motif / justification</label>
					<textarea
						id="dm-motif"
						rows="2"
						bind:value={demandeMotif}
						placeholder="Expliquez brièvement…"></textarea>
				</div>
				<div class="form-actions">
					<button
						class="btn btn-primary btn-sm"
						disabled={savingDemande}
						on:click={soumettreDemandeModif}
					>
						{savingDemande ? 'Envoi…' : 'Envoyer la demande'}
					</button>
				</div>
			</div>
		{/if}

		<!-- Historique des demandes -->
		<HistoriqueDemandes {demandes} chargement={demandesLoading} {statutLabels} />
	</section>

	{#if !arrivantChoix}
		<section class="card" style="margin-bottom:1.5rem">
			<h2 class="section-title">Démarche Nouvel Arrivant</h2>
			<p class="hint" style="margin-bottom:.6rem">
				Ce choix vous appartient : vous êtes la meilleure personne pour savoir si vous venez
				d'arriver dans la résidence.
			</p>
			<div class="info-banner info-yellow" style="margin-bottom:.8rem">
				Vous venez de créer un compte sur la plateforme.
				<br />
				<strong>Nouvel arrivant</strong> : vous emménagez réellement dans la résidence (Démarches
				nouvel arrivant : interphone, BAL, ...)
				<br />
				<strong>Déjà résident</strong> : vous venez de créer un compte mais vous étiez déjà résident (donc
				pas de démarche nouvel arrivant)
			</div>

			<div class="field">
				<label for="arr-bat">Bâtiment concerné</label>
				<select id="arr-bat" bind:value={arrivantBatimentNumero}>
					<option value="">— Sélectionner —</option>
					{#if batiments.length > 0}
						{#each batiments as bat (bat.numero)}
							<option value={String(bat.numero)}>{`Bât. ${bat.numero}`}</option>
						{/each}
					{:else}
						<option value="1">Bât. 1</option>
						<option value="2">Bât. 2</option>
						<option value="3">Bât. 3</option>
						<option value="4">Bât. 4</option>
					{/if}
				</select>
			</div>
			<div class="field">
				<label for="arr-ancien">Nom de l'ancien résident</label>
				<input
					id="arr-ancien"
					type="text"
					bind:value={arrivantAncienResident}
					disabled={arrivantAncienResidentInconnu}
					placeholder="Ex : Mme Dupont"
				/>
			</div>
			<label
				style="display:flex;align-items:center;gap:.5rem;margin-top:-.35rem;margin-bottom:.7rem;font-size:.88rem;color:var(--color-text-muted)"
			>
				<input type="checkbox" bind:checked={arrivantAncienResidentInconnu} />
				Je ne sais pas
			</label>
			<div class="form-actions">
				<button class="btn btn-primary" on:click={declarerNouvelArrivant} disabled={savingArrivant}>
					{savingArrivant ? 'Envoi…' : 'Je suis un nouvel arrivant'}
				</button>
				<button
					class="btn btn-arrivant-deja"
					type="button"
					on:click={declarerDejaResident}
					disabled={savingArrivant}
				>
					Je suis déjà résident
				</button>
			</div>
		</section>
	{/if}

	<ChangementMotDePasse />

	<!-- ── Ce que j'affiche, ce que je reçois ──────────────────────────────── -->
	<PreferencesAffichageNotifs
		valeurs={valeursNotifs}
		bind:restreindre={restreindreAMesBatiments}
		onSave={saveNotifs}
	/>

	<!-- ── RGPD ─────────────────────────────────────────────────────────────── -->
	<section class="card" style="border-color:#fde68a;background:#fffbeb">
		<h2 style="font-size:.95rem;font-weight:600;margin-bottom:.5rem">Vos droits (RGPD)</h2>
		<p style="font-size:.8rem;line-height:1.55;color:var(--color-text-muted)">
			Conformément au RGPD, vous pouvez exercer vos droits d'accès, rectification, portabilité et
			effacement en contactant le responsable de traitement à l'adresse indiquée dans la
			<a href="/politique-de-confidentialite" style="color:var(--color-primary)"
				>politique de confidentialité</a
			>.
		</p>

		<!-- Télémétrie opt-out -->
		<div style="margin-top:1rem;padding-top:.75rem;border-top:1px solid #fde68a">
			<label class="checkbox-field" style="margin-bottom:.4rem">
				<input
					type="checkbox"
					bind:checked={optOutTelemetrie}
					disabled={savingOptOut}
					on:change={async () => {
						savingOptOut = true;
						try {
							await authApi.toggleOptOutTelemetrie({ opt_out_telemetrie: optOutTelemetrie });
							setTelemetryOptOut(optOutTelemetrie);
							const updated = await authApi.me();
							setUser(updated);
							toast(
								'success',
								optOutTelemetrie
									? 'Collecte de statistiques désactivée.'
									: 'Collecte de statistiques réactivée.',
							);
						} catch {
							optOutTelemetrie = !optOutTelemetrie;
							toast('error', 'Erreur lors de la mise à jour.');
						}
						savingOptOut = false;
					}}
				/>
				Refuser la collecte de statistiques de navigation
			</label>
			<p
				style="font-size:.78rem;color:var(--color-text-muted);margin:0 0 .75rem;padding-left:1.55rem"
			>
				Ces statistiques anonymisées permettent au gestionnaire d'identifier les fonctionnalités les
				plus utilisées, de détecter d'éventuels problèmes de navigation et d'orienter les
				améliorations futures vers ce qui vous est réellement utile au quotidien. Elles ne
				contiennent aucune donnée personnelle sensible et ne sont jamais partagées avec des tiers.
				En les désactivant, vous nous privez d'informations précieuses pour vous offrir une
				meilleure expérience.
			</p>

			<div style="display:flex;gap:.5rem;flex-wrap:wrap">
				<button
					type="button"
					class="btn btn-sm"
					style="font-size:.8rem"
					disabled={exportingTelemetrie}
					on:click={async () => {
						exportingTelemetrie = true;
						try {
							const data = await authApi.exportTelemetrie();
							const json = JSON.stringify(data, null, 2);
							const blob = new Blob([json], { type: 'application/json' });
							const url = URL.createObjectURL(blob);
							const a = document.createElement('a');
							a.href = url;
							a.download = 'mes-donnees-telemetrie.json';
							a.click();
							URL.revokeObjectURL(url);
							toast('success', 'Export téléchargé.');
						} catch {
							toast('error', "Erreur lors de l'export.");
						}
						exportingTelemetrie = false;
					}}
				>
					📥 Exporter mes données de navigation
				</button>

				{#if !confirmDeleteTelemetrie}
					<button
						type="button"
						class="btn btn-sm btn-danger"
						style="font-size:.8rem"
						on:click={() => (confirmDeleteTelemetrie = true)}
					>
						🗑️ Effacer mes données de navigation
					</button>
				{:else}
					<span style="display:inline-flex;gap:.35rem;align-items:center;font-size:.8rem">
						<strong style="color:var(--color-danger)">Confirmer ?</strong>
						<button
							type="button"
							class="btn btn-sm btn-danger"
							style="font-size:.78rem"
							disabled={deletingTelemetrie}
							on:click={async () => {
								deletingTelemetrie = true;
								try {
									await authApi.effacerTelemetrie();
									toast('success', 'Données de navigation effacées.');
								} catch {
									toast('error', 'Erreur lors de la suppression.');
								}
								deletingTelemetrie = false;
								confirmDeleteTelemetrie = false;
							}}
						>
							Oui, effacer
						</button>
						<button
							type="button"
							class="btn btn-sm"
							style="font-size:.78rem"
							on:click={() => (confirmDeleteTelemetrie = false)}
						>
							Annuler
						</button>
					</span>
				{/if}
			</div>
		</div>
	</section>
</div>

<style>
	/*  `.section-title` : la charte porte tout (composants.css). Retiree le 28/08/2026 (#607). */
	.form-row {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
	}
	.form-actions {
		flex-wrap: wrap;
	} /* le reste vient de la charte (#607) */

	.hint {
		font-size: 0.78rem;
		color: var(--color-text-muted);
	}
	.info-grid {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.4rem 0.75rem;
		font-size: 0.875rem;
		margin-bottom: 0.25rem;
	}
	.info-grid dt {
		font-weight: 500;
		color: var(--color-text-muted);
		white-space: nowrap;
	}
	.info-grid dd {
		margin: 0;
	}
	.info-banner {
		padding: 0.6rem 0.9rem;
		border-radius: var(--radius);
		font-size: 0.85rem;
	}
	.info-yellow {
		background: #fffbeb;
		border: 1px solid #fde68a;
	}
	.btn-arrivant-deja {
		background: var(--color-success);
		color: #fff;
	}
	.btn-arrivant-deja:hover:not(:disabled) {
		background: #256f47;
	}
	.demande-form {
		background: var(--color-bg-subtle, #f9fafb);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 1rem;
	}
</style>
