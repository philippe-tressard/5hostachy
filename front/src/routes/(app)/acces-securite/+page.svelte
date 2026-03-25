<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
import { onMount } from 'svelte';
	import { acces as accesApi, lots as lotsApi, bailleur as bailApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { isCS, currentUser } from '$lib/stores/auth';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';

	$: _pc = getPageConfig($configStore, 'acces-badges', { titre: 'Accès & badges', navLabel: 'Accès & badges', icone: 'key-round', descriptif: 'Gestion de vos télécommandes parkings & Vigiks. <a href="/faq#badge-prix" style="font-size:.85rem">Quel prix pour un badge ?</a>' });
	$: _siteNom = $siteNomStore;

	let vigiks: any[] = [];
	let telecommandes: any[] = [];
	let commandes: any[] = [];
	let mesLots: any[] = [];
	let accesRecus: any[] = [];
	let mesBaux: any[] = [];
	let loading = true;

	// Formulaire demande
	let showForm = false;
	let formLotId = '';
	let formType = 'vigik';
	let formQuantite = 1;
	let formMotif = '';
	let submitting = false;

	onMount(async () => {
		try {
			const isLocataire = $currentUser?.statut === 'locataire';
			const isBailleur = $currentUser?.statut === 'copropriétaire_bailleur';
			const tasks: Promise<any>[] = [
				accesApi.mesVigiks(),
				accesApi.mesTelecommandes(),
				accesApi.mesCommandes(),
				lotsApi.mesList(),
			];
			if (isLocataire) tasks.push(bailApi.mesAccesRecus());
			if (isBailleur) tasks.push(bailApi.mesBaux());
			const results = await Promise.all(tasks);
			[vigiks, telecommandes, commandes, mesLots] = results;
			if (isLocataire) accesRecus = results[4] ?? [];
			if (isBailleur) mesBaux = results[4] ?? [];
		} catch (e) {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
	});

	async function soumettreCommande() {
		if (!formLotId) { toast('error', 'Sélectionnez un lot'); return; }
		submitting = true;
		try {
			await accesApi.creerCommande({
				lot_id: Number(formLotId),
				type: formType,
				quantite: formQuantite,
				motif: formMotif || undefined,
			});
			commandes = await accesApi.mesCommandes();
			showForm = false;
			formMotif = '';
			toast('success', 'Demande envoyée au conseil syndical');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			submitting = false;
		}
	}

	async function signalerPerdu(id: number, typeAcces: 'vigik' | 'tc') {
		if (!confirm('Signaler cet accès comme perdu ?')) return;
		try {
			if (typeAcces === 'vigik') {
				await accesApi.signalerVigiKPerdu(id);
				vigiks = vigiks.map(v => v.id === id ? { ...v, statut: 'perdu' } : v);
			} else {
				await accesApi.signalerTcPerdu(id);
				telecommandes = telecommandes.map(t => t.id === id ? { ...t, statut: 'perdu' } : t);
			}
			toast('success', 'Signalement enregistré');
		} catch (e) {
			toast('error', 'Erreur');
		}
	}

	async function supprimer(id: number, typeAcces: 'vigik' | 'tc') {
		if (!confirm('Supprimer cet accès de votre compte ?')) return;
		try {
			if (typeAcces === 'vigik') {
				await accesApi.supprimerVigik(id);
				vigiks = vigiks.filter(v => v.id !== id);
				toast('success', 'Badge supprimé');
			} else {
				await accesApi.supprimerTc(id);
				telecommandes = telecommandes.filter(t => t.id !== id);
				toast('success', 'Télécommande supprimée');
			}
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	// Déclaration d'accès existant
	let showDeclareForm = false;
	let declareType = 'telecommande';
	let declareCode = '';
	let declaring = false;

	async function declarerBadge() {
		if (!declareCode.trim()) { toast('error', 'Saisissez un code'); return; }
		declaring = true;
		try {
			const r = await accesApi.declarerBadge({ type: declareType, code: declareCode.trim() });
			if (declareType === 'vigik') {
				vigiks = await accesApi.mesVigiks();
			} else {
				telecommandes = await accesApi.mesTelecommandes();
			}
			const msg = r.import_resolu ? ' (import mis à jour)' : '';
			toast('success', `Accès enregistré${msg}`);
			declareCode = '';
			showDeclareForm = false;
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			declaring = false;
		}
	}

	function statutClass(s: string) {
		return { actif: 'badge-green', suspendu: 'badge-orange', perdu: 'badge-red' }[s] ?? 'badge-gray';
	}

	function commandeStatutClass(s: string) {
		return { en_attente: 'badge-orange', acceptee: 'badge-green', refusee: 'badge-red' }[s] ?? 'badge-gray';
	}

	// ── Bailleur : vue par locataire ─────────────────────────────────────────
	// Regroupement des vigiks/TCs confiés (chez_locataire) par locataire (email/nom)
	$: locatairesAcces = (() => {
		const bauxActifs = (mesBaux as any[]).filter(b => b.statut === 'actif' || b.statut === 'en_cours_sortie');
		const all = [
			...vigiks.filter(v => v.chez_locataire).map(v => ({ ...v, typeAcces: 'vigik' as const })),
			...telecommandes.filter(t => t.chez_locataire).map(t => ({ ...t, typeAcces: 'telecommande' as const })),
		];
		// Grouper par identité du locataire (email prioritaire, sinon nom+prénom)
		const groupMap = new Map<string, { baux: any[]; items: any[] }>();
		for (const bail of bauxActifs) {
			const key = bail.locataire_email?.trim().toLowerCase() || `${bail.locataire_prenom}|${bail.locataire_nom}`;
			if (!groupMap.has(key)) groupMap.set(key, { baux: [bail], items: [] });
			else groupMap.get(key)!.baux.push(bail);
		}
		for (const group of groupMap.values()) {
			const bailIds = new Set(group.baux.map((b: any) => b.id));
			group.items = all.filter(a => bailIds.has(a.bail_id));
		}
		return [...groupMap.values()];
	})();

	async function recupererTousLocataireAcces(bailIds: number[]) {
		if (!confirm('Récupérer tous les accès confiés à ce locataire ?')) return;
		try {
			const updates = await Promise.all(bailIds.map(id => bailApi.recupererAcces(id)));
			const ids = new Set(updates.flat().map((u: any) => `${u.type}:${u.id}`));
			vigiks = vigiks.map(v => ids.has(`vigik:${v.id}`) ? { ...v, chez_locataire: false, bail_id: null } : v);
			telecommandes = telecommandes.map(t => ids.has(`telecommande:${t.id}`) ? { ...t, chez_locataire: false, bail_id: null } : t);
			toast('success', 'Accès récupérés');
		} catch {
			toast('error', 'Erreur lors de la récupération');
		}
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<div class="page-header">
	<h1 style="display:flex;align-items:center;gap:.4rem;font-size:1.4rem;font-weight:700"><Icon name={_pc.icone || 'key-round'} size={20} />{_pc.titre}</h1>
</div>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else}

<!-- Mes vigiks -->
{#if vigiks.length > 0 || $currentUser?.statut !== 'locataire'}
<section class="section card">
	<div class="section-header">
		<h2 class="section-title">Badges d'accès (Vigik)</h2>
	</div>
	{#if vigiks.length === 0}
		<p style="color:var(--color-text-muted);font-size:.9rem">Aucun badge enregistré.</p>
	{:else}
		<table class="table" style="table-layout:fixed;width:100%">
			<colgroup><col style="width:35%"><col style="width:9rem"><col></colgroup>
			<thead><tr><th>Code</th><th>Statut</th><th>Actions</th></tr></thead>
			<tbody>
				{#each vigiks as v}
					<tr>
						<td style="font-family:monospace">{v.code}</td>
						<td><span class="badge {statutClass(v.statut)}">{v.statut}</span></td>
						<td style="display:flex;gap:.35rem;flex-wrap:wrap">
							{#if v.statut === 'actif'}
								<button class="btn btn-sm btn-outline" on:click={() => signalerPerdu(v.id, 'vigik')}>Signaler perdu</button>
							{/if}
							{#if $isCS}
								<button class="btn-icon-danger" aria-label="Supprimer ce badge Vigik" title="Supprimer" on:click={() => supprimer(v.id, 'vigik')}>&#x1F5D1;️</button>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
</section>
{/if}

<!-- Mes télécommandes -->
{#if telecommandes.length > 0 || $currentUser?.statut !== 'locataire'}
<section class="section card" style="margin-top:1rem">
	<div class="section-header">
		<h2 class="section-title">Télécommandes de parking</h2>
	</div>
	{#if telecommandes.length === 0}
		<p style="color:var(--color-text-muted);font-size:.9rem">Aucune télécommande enregistrée.</p>
	{:else}
		<table class="table" style="table-layout:fixed;width:100%">
			<colgroup><col style="width:35%"><col style="width:9rem"><col></colgroup>
			<thead><tr><th>Code</th><th>Statut</th><th>Actions</th></tr></thead>
			<tbody>
				{#each telecommandes as tc}
					<tr>
						<td style="font-family:monospace">{tc.code}</td>
						<td><span class="badge {statutClass(tc.statut)}">{tc.statut}</span></td>
						<td style="display:flex;gap:.35rem;flex-wrap:wrap">
							{#if tc.statut === 'actif'}
								<button class="btn btn-sm btn-outline" on:click={() => signalerPerdu(tc.id, 'tc')}>Signaler perdu</button>
							{/if}
							{#if $isCS}
								<button class="btn-icon-danger" aria-label="Supprimer cette télécommande" title="Supprimer" on:click={() => supprimer(tc.id, 'tc')}>&#x1F5D1;️</button>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
</section>
{/if}

<!-- Nouvelle demande -->
<section id="nouvelle-demande" class="section card" style="margin-top:1rem;scroll-margin-top:6rem">
	<div class="section-header">
		<h2 class="section-title">Faire une demande d'un nouvel accès</h2>
		<button class="btn btn-primary btn-sm" on:click={() => showForm = !showForm}>
			{showForm ? 'Annuler' : '+ Nouvelle demande'}
		</button>
	</div>

	{#if showForm}
		<form class="form" on:submit|preventDefault={soumettreCommande} style="margin-top:1rem">
			<div class="form-row">
				<label>
					Type d'accès *
					<select bind:value={formType}>
						<option value="vigik">Badge Vigik</option>
						<option value="telecommande">Télécommande parking</option>
					</select>
				</label>
				<label>
					Lot concerné *
					<select bind:value={formLotId} required>
						<option value="">— Sélectionner —</option>
						{#each mesLots as lot}
							<option value={lot.id}>Lot {lot.numero}</option>
						{/each}
					</select>
				</label>
				<label>
					Quantité *
					<input type="number" bind:value={formQuantite} min="1" max="5" />
				</label>
			</div>
			<label>
				Motif
				<textarea bind:value={formMotif} rows="2" placeholder="Raison de la demande…"></textarea>
			</label>
			<button class="btn btn-primary" disabled={submitting}>
				{submitting ? 'Envoi…' : 'Soumettre la demande'}
			</button>
		</form>
	{/if}
</section>

<!-- Déclarer un accès existant -->
<section class="section card" style="margin-top:1rem">
	<div class="section-header">
		<h2 class="section-title">&#x1F4CB; J'ai déjà un accès non enregistré (ci-dessus)</h2>
		<button class="btn btn-secondary btn-sm" on:click={() => (showDeclareForm = !showDeclareForm)}>
			{showDeclareForm ? 'Annuler' : 'Ajouter'}
		</button>
	</div>
	{#if showDeclareForm}
		<form class="form" on:submit|preventDefault={declarerBadge} style="margin-top:1rem">
			<div class="form-row">
				<label>
					Type d'accès *
					<select bind:value={declareType}>
						<option value="telecommande">Télécommande parking</option>
						<option value="vigik">Badge Vigik</option>
					</select>
				</label>
				<label>
					Code / référence *
					<input type="text" bind:value={declareCode} placeholder="Ex : 1234567890" style="font-family:monospace" required />
				</label>
			</div>
			<p style="font-size:.82rem;color:var(--color-text-muted);margin:.25rem 0 .75rem">
				Si ce code figure dans nos imports, l'entrée sera automatiquement liée à votre compte.
			</p>
			<button class="btn btn-primary" disabled={declaring}>
				{declaring ? 'Enregistrement…' : 'Enregistrer cet accès'}
			</button>
		</form>
	{/if}
</section>

<!-- Historique des demandes -->
<section class="section card" style="margin-top:1rem">
	<h2 class="section-title">Historique de mes demandes</h2>
	{#if commandes.length === 0}
		<p style="color:var(--color-text-muted);font-size:.9rem">Aucune demande passée.</p>
	{:else}
		{#each commandes as cmd}
			<div class="commande-row">
				<div>
					<strong>{cmd.type === 'vigik' ? 'Badge Vigik' : 'Télécommande'}</strong>
					<span style="color:var(--color-text-muted);font-size:.8rem;margin-left:.5rem">
						× {cmd.quantite} — {new Date(cmd.cree_le).toLocaleDateString('fr-FR')}
					</span>
					{#if cmd.motif}<p style="font-size:.85rem;color:var(--color-text-muted);margin:.2rem 0 0">{cmd.motif}</p>{/if}
				</div>
				<span class="badge {commandeStatutClass(cmd.statut)}">{cmd.statut.replace('_', ' ')}</span>
			</div>
		{/each}
	{/if}
</section>

<!-- Accès reçus du bailleur (locataires uniquement) -->
{#if $currentUser?.statut === 'locataire'}
<section class="section card" style="margin-top:1rem;border-left:3px solid var(--color-primary)">
	<div class="section-header">
		<h2 class="section-title">&#x1F3E0; Accès confiés par votre bailleur</h2>
	</div>
	{#if accesRecus.length === 0}
		<p style="font-size:.85rem;color:var(--color-text-muted)">
			Aucun accès ne vous a encore été confié par votre propriétaire.
		</p>
	{:else}
		<p style="font-size:.85rem;color:var(--color-text-muted);margin-bottom:.75rem">
			Ces accès vous ont été confiés par votre propriétaire pour la durée de votre bail.
		</p>
		<table class="table" style="table-layout:fixed;width:100%">
			<colgroup><col style="width:30%"><col style="width:10rem"><col style="width:9rem"></colgroup>
			<thead><tr><th>Code</th><th>Type</th><th>Statut</th></tr></thead>
			<tbody>
				{#each accesRecus as a}
					<tr>
						<td style="font-family:monospace">{a.code}</td>
						<td>{a.type === 'vigik' ? '\u{1F3F7}️ Vigik' : '\u{1F4E1} Télécommande'}</td>
						<td><span class="badge {statutClass(a.statut)}">{a.statut}</span></td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
</section>
{/if}

<!-- Vue par locataire (bailleurs uniquement) -->
{#if $currentUser?.statut === 'copropriétaire_bailleur' && mesBaux.length > 0}
<section class="section card" style="margin-top:1rem;border-left:3px solid var(--color-accent,#C9983A)">
	<div class="section-header">
		<h2 class="section-title">👥 Vue par locataire</h2>
	</div>
	{#if mesBaux.filter((b) => b.statut === 'actif' || b.statut === 'en_cours_sortie').length === 0}
		<p style="font-size:.85rem;color:var(--color-text-muted)">Aucun bail actif.</p>
	{:else}
		<p style="font-size:.85rem;color:var(--color-text-muted);margin-bottom:.9rem">
			Résumé des accès (Vigik / télécommandes) confiés à vos locataires.
		</p>
		{#each locatairesAcces as { baux, items }}
			{@const premierBail = baux[0]}
			<div class="locataire-acces-row">
				<div class="lar-header">
					<div class="lar-tenant">
						<strong>{[premierBail.locataire_prenom, premierBail.locataire_nom].filter(Boolean).join(' ') || 'Locataire non renseigné'}</strong>
						{#if premierBail.locataire_email}<a href="mailto:{premierBail.locataire_email}" style="font-size:.8rem;color:var(--color-primary)">{premierBail.locataire_email}</a>{/if}
					</div>
					<div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap">
						{#if items.length > 0}
							<span class="badge badge-yellow" style="font-size:.72rem">{items.length} accès confié{items.length > 1 ? 's' : ''}</span>
							<button class="btn btn-sm btn-outline" on:click={() => recupererTousLocataireAcces(baux.map((b: any) => b.id))}>↩ Tout récupérer</button>
						{:else}
							<span class="badge badge-gray" style="font-size:.72rem">Aucun accès confié</span>
						{/if}
					</div>
				</div>
				{#if items.length > 0}
				<div class="lar-items">
					{#each items as item}
						<div class="lar-item">
							<span style="font-family:monospace;font-size:.85rem">{item.code}</span>
							<span class="badge {item.typeAcces === 'vigik' ? 'badge-blue' : 'badge-purple'}" style="font-size:.68rem">
								{item.typeAcces === 'vigik' ? '🏷️ Vigik' : '📡 TC'}
							</span>
							<span class="badge {statutClass(item.statut)}" style="font-size:.68rem">{item.statut}</span>
						</div>
					{/each}
				</div>
				{/if}
			</div>
		{/each}
	{/if}
</section>
{/if}

{/if}<!-- /loading -->

<style>
	.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: .75rem; }
	.section-title { font-size: .85rem; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: var(--color-text-muted); margin: 0; }
	.section { padding: 1.25rem; }
	.table { width: 100%; border-collapse: collapse; font-size: .9rem; }
	.table th { text-align: left; padding: .4rem .5rem; font-size: .8rem; color: var(--color-text-muted); border-bottom: 1px solid var(--color-border); }
	.table td { padding: .5rem; border-bottom: 1px solid var(--color-border); }
	.form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
	.form label { display: flex; flex-direction: column; gap: .3rem; font-size: .9rem; }
	.form select, .form input, .form textarea {
		padding: .45rem .6rem; border: 1px solid var(--color-border);
		border-radius: var(--radius); font-size: .9rem; background: var(--color-bg);
	}
	.commande-row { display: flex; justify-content: space-between; align-items: flex-start; padding: .65rem 0; border-bottom: 1px solid var(--color-border); }
	.commande-row:last-child { border-bottom: none; }
	/* Vue locataire bailleur */
	.locataire-acces-row { padding: .7rem 0; border-bottom: 1px solid var(--color-border); }
	.locataire-acces-row:last-child { border-bottom: none; }
	.lar-header { display: flex; justify-content: space-between; align-items: flex-start; gap: .75rem; flex-wrap: wrap; margin-bottom: .45rem; }
	.lar-tenant { display: flex; flex-direction: column; gap: .15rem; }
	.lar-items { display: flex; flex-wrap: wrap; gap: .4rem; }
	.lar-item { display: flex; align-items: center; gap: .3rem; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius); padding: .2rem .55rem; font-size: .82rem; }
</style>
