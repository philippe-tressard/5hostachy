<!--
  L'écran d'import d'ACCÈS — un seul, piloté par un modèle.

  ## Pourquoi ce composant existe (27/08/2026, #453)

  `OngletImportTelecommandes.svelte` (349 l.) et `OngletImportVigik.svelte`
  (329 l.) étaient **identiques à 87 %** : 263 lignes communes sur 314. Même
  écran, même geste, même tableau, écrits deux fois.

  Ce qui les distinguait tenait dans une table de données — endpoints, colonnes,
  vocabulaire, une tuile de statistique. Elle vit dans `$lib/imports-acces.ts`,
  avec la seule vraie divergence de comportement que la fusion a révélée
  (`remettreEnAttente`, absent côté Vigik).

  ⚠️ Ce composant ne connaît **aucun** nom de type d'import : ni « Vigik », ni
  « télécommande », ni un seul chemin d'API. S'il en connaissait un, la troisième
  instance rouvrirait la porte à la quatrième copie — c'est ce qui est arrivé ici.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { siteNomStore } from '$lib/stores/pageConfig';
	import { STATUT_BADGE, STATUT_LABEL, type ModeleImportAcces } from '$lib/imports-acces';
	import BarreImport from '$lib/components/BarreImport.svelte';

	export let modele: ModeleImportAcces;

	$: _siteNom = $siteNomStore;

	// ── Données ────────────────────────────────────────────────────────────────
	let imports: any[] = [];
	let stats: any = null;
	let utilisateurs: any[] = [];
	let lots: any[] = [];
	let loading = true;
	let filtre = '';

	// ── Téléversement ──────────────────────────────────────────────────────────
	//  Le FORMULAIRE vit dans `BarreImport` ; il ne reste ici que ce qui dépend du
	//  modèle : l'appel et son compte rendu.
	let televersement = false;

	async function televerser(fichier: File, remplacer: boolean) {
		televersement = true;
		try {
			const r = await modele.api.upload(fichier, remplacer);
			toast(
				'success',
				`Import : ${r.importes} ajoutés, ${r.doublons} doublons, ${r.ignores} ignorés`,
			);
			await recharger();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur import');
		} finally {
			televersement = false;
		}
	}

	// ── Rapprochement automatique ──────────────────────────────────────────────
	let rapprochement = false;

	async function autoMatch() {
		rapprochement = true;
		try {
			const r = await modele.api.autoMatch();
			toast('success', `${r.matches} liaison(s) automatique(s) trouvée(s)`);
			await recharger();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			rapprochement = false;
		}
	}

	// ── Édition en ligne ───────────────────────────────────────────────────────
	let editId: number | null = null;
	let editProprio = '';
	let editLoc = '';
	let editLot = '';
	let editChezLoc = false;
	let editNotes = '';
	//  Les cases propres à un type (« Locataire a refusé ») : le modèle les
	//  déclare, le formulaire les tient dans un seul objet plutôt qu'en variables
	//  nommées — sans quoi ajouter un champ demanderait de toucher ce fichier.
	let editBooleens: Record<string, boolean> = {};
	let enregistrement = false;

	function ouvrirEdition(imp: any) {
		editId = imp.id;
		editProprio = String(imp.user_proprietaire_id ?? '');
		editLoc = String(imp.user_locataire_id ?? '');
		editLot = String(imp.lot_id ?? '');
		editChezLoc = imp.chez_locataire;
		editNotes = imp.notes_admin ?? '';
		editBooleens = Object.fromEntries(
			modele.champsBooleens.map((c) => [c.cle, imp[c.cle] ?? false]),
		);
	}

	function annulerEdition() {
		editId = null;
	}

	async function enregistrer() {
		if (editId === null) return;
		enregistrement = true;
		try {
			await modele.api.patch(editId, {
				user_proprietaire_id: editProprio ? Number(editProprio) : null,
				user_locataire_id: editLoc ? Number(editLoc) : null,
				lot_id: editLot ? Number(editLot) : null,
				chez_locataire: editChezLoc,
				notes_admin: editNotes || null,
				...editBooleens,
			});
			toast('success', 'Liaisons mises à jour');
			editId = null;
			await recharger();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			enregistrement = false;
		}
	}

	// ── Résolution / ignorer / reprise ─────────────────────────────────────────
	async function resoudre(id: number) {
		if (!confirm(`Créer ${modele.objet} et marquer cet import comme résolu ?`)) return;
		try {
			await modele.api.resoudre(id);
			toast('success', `Création de ${modele.objet} : liaison faite`);
			await recharger();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur résolution');
		}
	}

	async function ignorer(id: number) {
		if (!confirm('Ignorer cet import ?')) return;
		try {
			await modele.api.ignorer(id);
			toast('info', 'Import ignoré');
			await recharger();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	async function remettreEnAttente(id: number) {
		try {
			await modele.api.remettreEnAttente(id);
			toast('success', 'Import remis en attente');
			await recharger();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	// ── Chargement ─────────────────────────────────────────────────────────────
	async function recharger() {
		[imports, stats] = await Promise.all([
			modele.api.list(filtre || undefined),
			modele.api.stats(),
		]);
	}

	onMount(async () => {
		loading = true;
		try {
			[utilisateurs, lots] = await Promise.all([
				api.get<any[]>('/admin/utilisateurs'),
				api.get<any[]>('/copropriete/lots'),
			]);
			await recharger();
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
	});

	/** Les colonnes propres au type, puis la colonne clé — l'ordre du tableau. */
	$: colonnesSpecifiques = modele.colonnes;
	/** `colspan` du formulaire d'édition : il suit le nombre réel de colonnes. */
	$: nbColonnes = colonnesSpecifiques.length + 8;
</script>

<svelte:head><title>{modele.titre} — {_siteNom}</title></svelte:head>

<BarreImport
	tuiles={stats
		? [
				{ valeur: stats.total, libelle: 'Total' },
				{ valeur: stats.en_attente, libelle: 'En attente', couleur: '#d97706' },
				{ valeur: stats.proprietaire_lie, libelle: 'Proprio lié', couleur: '#2563eb' },
				{ valeur: stats.resolu, libelle: 'Résolus', couleur: '#16a34a' },
				{ valeur: stats.ignore, libelle: 'Ignorés', couleur: '#6b7280' },
				{
					valeur: stats[modele.statSupplementaire.cle],
					libelle: modele.statSupplementaire.libelle,
				},
			]
		: []}
	colonnesAttendues={modele.colonnesAttendues}
	enCours={televersement}
	statuts={['', 'en_attente', 'proprietaire_lie', 'resolu', 'ignore']}
	libellesStatuts={STATUT_LABEL}
	bind:filtre
	on:importer={(e) => televerser(e.detail.fichier, e.detail.remplacer)}
	on:filtrer={recharger}
>
	<button
		slot="actions"
		class="btn btn-outline btn-sm"
		on:click={autoMatch}
		disabled={rapprochement}
	>
		{rapprochement ? 'Recherche…' : '\u{1F517} Auto-match'}
	</button>
</BarreImport>

<!-- ── Tableau ─────────────────────────────────────────────────────────────── -->
{#if loading}
	<p class="muted">Chargement…</p>
{:else if imports.length === 0}
	<div class="empty-state card">
		<h3>Aucun import</h3>
		<p>Importez un fichier .xlsx pour démarrer.</p>
	</div>
{:else}
	<div class="card" style="overflow:auto">
		<table class="table imp-table-dense">
			<thead>
				<tr>
					{#each colonnesSpecifiques as c (c.cle)}<th>{c.entete}</th>{/each}
					<th>Propriétaire (Excel)</th><th>Locataire (Excel)</th>
					<th>{modele.colonneCle.entete}</th><th>Lot lié</th>
					<th>Proprio lié</th><th>Locataire lié</th>
					<th>Statut</th><th>Actions</th>
				</tr>
			</thead>
			<tbody>
				{#each imports as imp (imp.id)}
					<tr
						class:imp-row-resolu={imp.statut === 'resolu'}
						class:imp-row-ignore={imp.statut === 'ignore'}
					>
						{#each colonnesSpecifiques as c (c.cle)}
							<td style="font-size:.8rem">{imp[c.cle] ?? '—'}</td>
						{/each}
						<td style="font-weight:500">{imp.nom_proprietaire}</td>
						<td style="color:var(--color-text-muted)">{imp.nom_locataire ?? '—'}</td>
						<td>
							{#if modele.colonneCle.code}
								<code style="font-size:.8rem">{imp[modele.colonneCle.cle] ?? '—'}</code>
							{:else}
								{imp[modele.colonneCle.cle] ?? '—'}
							{/if}
						</td>
						<td style="font-size:.8rem;color:var(--color-text-muted)">{imp.lot_label ?? '—'}</td>
						<td style="font-size:.8rem">
							{#if imp.proprietaire}
								<span style="color:#16a34a">{imp.proprietaire.prenom} {imp.proprietaire.nom}</span>
							{:else}
								<span style="color:#d97706">Non lié</span>
							{/if}
						</td>
						<td style="font-size:.8rem;color:var(--color-text-muted)">
							{#if imp.locataire}
								{imp.locataire.prenom} {imp.locataire.nom}
							{:else if imp.nom_locataire}
								<span style="color:#d97706">Non lié</span>
							{:else}—{/if}
						</td>
						<td>
							<span class="badge {STATUT_BADGE[imp.statut] ?? 'badge-gray'}"
								>{STATUT_LABEL[imp.statut] ?? imp.statut}</span
							>
							{#each modele.decorationsStatut(imp) as d (d.titre)}
								<span title={d.titre} style="margin-left:.25rem">{d.icone}</span>
							{/each}
						</td>
						<td>
							{#if imp.statut !== 'resolu' && imp.statut !== 'ignore'}
								<div class="action-row">
									<button
										class="btn-icon-edit"
										aria-label="Modifier"
										title="Modifier"
										on:click={() => ouvrirEdition(imp)}>✏️</button
									>
									{#if imp.user_proprietaire_id && imp[modele.colonneCle.cle]}
										<button class="btn btn-sm btn-primary" on:click={() => resoudre(imp.id)}
											>✓ Créer</button
										>
									{/if}
									<button
										class="btn-icon-warn"
										aria-label="Ignorer cet import"
										title="Ignorer"
										on:click={() => ignorer(imp.id)}>⊘</button
									>
								</div>
							{:else if imp.statut === 'resolu'}
								<div class="action-row">
									<span class="badge badge-green" style="font-size:.75rem"
										>{modele.badgeResolu(imp)}</span
									>
									<button
										class="btn-icon-edit"
										aria-label="Corriger les liens"
										title="Corriger les liens"
										on:click={() => ouvrirEdition(imp)}>✏️</button
									>
								</div>
							{:else if imp.statut === 'ignore'}
								<!--  Le geste vaut pour LES DEUX types depuis #576 : la condition sur le
								      modèle est tombée avec la divergence. Un mécanisme d'exception qui
								      survit à son exception invite la suivante (`ux-patterns` §13). -->
								<div class="action-row">
									<button
										class="btn-icon-success"
										aria-label="Remettre en attente"
										title="Remettre en attente"
										on:click={() => remettreEnAttente(imp.id)}>↩</button
									>
								</div>
							{/if}
						</td>
					</tr>

					<!-- Formulaire d'édition en ligne -->
					{#if editId === imp.id}
						<tr class="imp-edit-row">
							<td colspan={nbColonnes}>
								<div class="imp-edit-form card" style="margin:.5rem 0">
									<h3 style="font-size:.9rem;font-weight:700;margin-bottom:.75rem">
										Lier : <em>{imp.nom_proprietaire}</em>
									</h3>
									<div class="imp-edit-grid">
										<div class="field">
											<label for="imp-proprio">Propriétaire *</label>
											<select id="imp-proprio" bind:value={editProprio}>
												<option value="">— Non lié —</option>
												{#each utilisateurs as u (u.id)}
													<option value={String(u.id)}>{u.prenom} {u.nom} ({u.email})</option>
												{/each}
											</select>
										</div>
										<div class="field">
											<label for="imp-loc">Locataire</label>
											<select id="imp-loc" bind:value={editLoc}>
												<option value="">— Aucun —</option>
												{#each utilisateurs as u (u.id)}
													<option value={String(u.id)}>{u.prenom} {u.nom} ({u.email})</option>
												{/each}
											</select>
										</div>
										<div class="field">
											<label for="imp-lot">Lot</label>
											<select id="imp-lot" bind:value={editLot}>
												<option value="">— Auto / Inconnu —</option>
												{#each lots as l (l.id)}
													<option value={String(l.id)}
														>Bât.{l.batiment_nom ?? l.batiment_id} — {l.numero} ({l.type})</option
													>
												{/each}
											</select>
										</div>
										<div class="field imp-field-checkbox">
											<label>
												<input type="checkbox" bind:checked={editChezLoc} />
												{modele.libelleChezLocataire}
											</label>
										</div>
										{#each modele.champsBooleens as c (c.cle)}
											<div class="field imp-field-checkbox">
												<label>
													<input type="checkbox" bind:checked={editBooleens[c.cle]} />
													{c.libelle}
												</label>
											</div>
										{/each}
										<div class="field" style="grid-column:span 2">
											<label for="imp-notes">Notes admin</label>
											<input
												id="imp-notes"
												type="text"
												bind:value={editNotes}
												placeholder="Note interne…"
											/>
										</div>
									</div>
									<div class="form-actions">
										<button
											class="btn btn-outline"
											on:click={annulerEdition}
											disabled={enregistrement}>Annuler</button
										>
										<button
											class="btn btn-primary"
											on:click={enregistrer}
											disabled={enregistrement}
										>
											{enregistrement ? 'Enregistrement…' : 'Enregistrer'}
										</button>
									</div>
								</div>
							</td>
						</tr>
					{/if}
				{/each}
			</tbody>
		</table>
	</div>
{/if}
