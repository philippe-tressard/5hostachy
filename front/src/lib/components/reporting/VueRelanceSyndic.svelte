<!--
  Reporting CS — **relance syndic** : les tickets adressés au syndic, ceux que le
  délai rend éligibles à une relance, et l'envoi groupé.

  Extrait d'`espace-cs/+page.svelte` avec #453. Autonome : c'est la seule vue dont
  les données ne viennent pas du chargement commun — `relanceSyndicList` applique
  le délai côté serveur. Elle expose `chargement` et `estVide` à la barre d'outils
  du parent, qui en a besoin : « Imprimer » refuse une page vide, et
  « Rafraîchir » doit savoir quoi recharger.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { tickets as ticketsApi, type Ticket } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { apiMessage } from '$lib/utils';
	import { daysSince } from '$lib/date';
	import { STATUT_TICKET_BADGE as TK_STATUT_BADGE, STATUT_TICKET_LABELS as TK_STATUT_LABELS } from '$lib/tickets';

	let relanceList: Ticket[] = [];
	let relanceDelaiJours = 30;
	let relanceLoading = false;
	let relanceLoaded = false;
	let relanceSelected: Set<number> = new Set();
	let relanceSending = false;
	let relanceNonRelancableEditing: number | null = null;
	let relanceMotifTemp = '';

	/** Lu par la barre d'outils du parent — ne pas écrire depuis l'extérieur. */
	export let chargement = false;
	/** Idem : « rien à imprimer » se décide ici, pas dans la barre d'outils. */
	export let estVide = true;
	$: chargement = relanceLoading;
	$: estVide = relanceList.length === 0;

	async function loadRelanceSyndic(force = false) {
		if (relanceLoaded && !force) return;
		relanceLoading = true;
		try {
			const resp = await ticketsApi.relanceSyndicList();
			relanceDelaiJours = resp.delai_jours;
			relanceList = resp.tickets;
			// Pré-sélectionner uniquement les tickets éligibles (passé le délai)
			relanceSelected = new Set(relanceList.filter(t => daysSince(t.mis_a_jour_le) >= relanceDelaiJours).map(t => t.id));
			relanceLoaded = true;
		} catch (e: any) {
			toast('error', apiMessage(e, 'Erreur chargement relances syndic'));
		} finally {
			relanceLoading = false;
		}
	}

	async function envoiRelance() {
		const ids = Array.from(relanceSelected);
		if (ids.length === 0) return;
		if (!confirm(`Envoyer la relance pour ${ids.length} ticket(s) au syndic ?`)) return;
		relanceSending = true;
		try {
			const res = await ticketsApi.envoiRelance(ids);
			toast('success', `✅ Relance envoyée à ${res.relance_to}`);
			await loadRelanceSyndic(true);
		} catch (e: any) {
			toast('error', apiMessage(e, 'Erreur envoi relance'));
		} finally {
			relanceSending = false;
		}
	}

	async function saveNonRelancable(t: Ticket, val: boolean, motif: string) {
		try {
			await ticketsApi.update(t.id, { non_relancable: val, non_relancable_motif: motif || null });
			relanceNonRelancableEditing = null;
			await loadRelanceSyndic(true);
		} catch (e: any) {
			toast('error', apiMessage(e, 'Erreur mise à jour ticket'));
		}
	}

	/** Rechargement demandé par la barre d'outils du parent. */
	export function recharger() {
		loadRelanceSyndic(true);
	}

	onMount(() => loadRelanceSyndic());
</script>

{#if relanceLoading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if relanceList.length === 0}
	<div class="empty-state">
		<h3>✅ Aucun ticket syndic en cours</h3>
		<p>Aucun ticket adressé au syndic n'est actuellement ouvert ou en cours.</p>
	</div>
{:else}
	{@const eligibles = relanceList.filter(t => daysSince(t.mis_a_jour_le) >= relanceDelaiJours)}
	{@const enAttente = relanceList.filter(t => daysSince(t.mis_a_jour_le) < relanceDelaiJours)}
	<section class="report-card" style="margin-bottom:1.5rem">
		<h3>🔔 Tickets syndic — suivi des relances</h3>
		<p class="report-intro">
			{relanceList.length} ticket(s) adressé(s) au syndic en cours.
			{#if eligibles.length > 0}
				<strong>{eligibles.length} éligible(s) à la relance</strong> (sans modification depuis plus de {relanceDelaiJours} jours).
			{:else}
				Aucun ticket ne dépasse le délai de {relanceDelaiJours} jours pour l'instant.
			{/if}
		</p>

		<div style="display:flex;flex-direction:column;gap:.75rem;margin-bottom:1.25rem">
			{#each relanceList as t (t.id)}
				{@const jours = daysSince(t.mis_a_jour_le)}
				{@const eligible = jours >= relanceDelaiJours}
				{@const selected = relanceSelected.has(t.id)}
				{@const isEditingMotif = relanceNonRelancableEditing === t.id}
				<div class="relance-item" class:relance-item-unselected={!selected} class:relance-item-pending={!eligible}>
					<div class="relance-item-top">
						<label style="display:flex;align-items:center;gap:.5rem;cursor:pointer;flex:1;min-width:0">
							<input type="checkbox" checked={selected}
								on:change={() => {
									const s = new Set(relanceSelected);
									if (s.has(t.id)) s.delete(t.id); else s.add(t.id);
									relanceSelected = s;
								}} />
							<span class="relance-numero">{t.numero}</span>
							<span class="relance-titre">{t.titre}</span>
						</label>
						<div class="relance-item-right">
							{#if eligible}
								{#if (t.relance_count ?? 0) > 0}
									<span class="badge badge-red">Relance n°{(t.relance_count ?? 0) + 1}</span>
								{:else}
									<span class="badge badge-orange">1ère relance</span>
								{/if}
								<span class="relance-date relance-date-overdue" title="Dernière modification">{jours}j sans modif.</span>
							{:else}
								<span class="badge badge-gray">En attente</span>
								<span class="relance-date" title="Dernière modification">{jours}j / {relanceDelaiJours}j</span>
							{/if}
						</div>
					</div>
					<!-- Tag non-relançable -->
					<div class="relance-item-meta">
						<span class="badge {TK_STATUT_BADGE[t.statut] ?? 'badge-gray'}">{TK_STATUT_LABELS[t.statut] ?? t.statut}</span>
						<span class="badge badge-gray">{t.categorie}</span>
						{#if t.non_relancable}
							<span class="badge badge-red">🚫 Non relançable{t.non_relancable_motif ? ` — ${t.non_relancable_motif}` : ''}</span>
						{/if}
						{#if !isEditingMotif}
							<!-- Libellé à l'infinitif : posé au milieu des badges d'état, « Non
							     relançable » se lisait comme un ÉTAT alors que c'est l'ACTION de
							     le poser. Les sept lignes l'affichaient sans qu'aucun ticket ne
							     le soit (signalé le 04/08/2026). -->
							<button class="btn-icon relance-tag-action no-print" title={t.non_relancable ? 'Retirer le tag non-relançable' : 'Marquer comme non-relançable'}
								on:click={() => {
									if (t.non_relancable) {
										saveNonRelancable(t, false, '');
									} else {
										relanceNonRelancableEditing = t.id;
										relanceMotifTemp = t.non_relancable_motif ?? '';
									}
								}}>
								{t.non_relancable ? '✅ Réactiver' : '🚫 Marquer non relançable'}
							</button>
						{:else}
							<div style="display:flex;gap:.4rem;align-items:center;flex-wrap:wrap">
								<input type="text" placeholder="Motif (optionnel)" bind:value={relanceMotifTemp}
									style="font-size:.8rem;padding:2px 6px;border:1px solid var(--color-border);border-radius:4px;width:180px" />
								<button class="btn btn-sm btn-primary" on:click={() => saveNonRelancable(t, true, relanceMotifTemp)}>Confirmer</button>
								<button class="btn btn-sm btn-outline" on:click={() => relanceNonRelancableEditing = null}>Annuler</button>
							</div>
						{/if}
					</div>
				</div>
			{/each}
		</div>

		<div class="form-actions no-print">
			<button class="btn btn-primary" disabled={relanceSending || relanceSelected.size === 0}
				on:click={envoiRelance}>
				{relanceSending ? '…' : `📧 Envoyer la relance (${relanceSelected.size} ticket${relanceSelected.size > 1 ? 's' : ''})`}
			</button>
		</div>
	</section>
{/if}

<style>
  /* ── Relance syndic ───────────────────────────────────────────────── */
  .relance-item {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-left: 4px solid var(--color-primary);
          border-radius: var(--radius);
          padding: .65rem .9rem;
          transition: opacity .15s;
  }
  .relance-item-unselected { opacity: .5; border-left-color: var(--color-border); }
  .relance-item-pending { border-left-color: var(--color-text-muted); background: var(--color-bg-subtle, #f9fafb); }
  .relance-item-top { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }
  .relance-item-meta { display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; margin-top: .4rem; }
  /* `nowrap` comme `.relance-numero` juste en dessous : sans lui le libellé se
     coupait entre « Non » et « relançable », et la seconde ligne chevauchait le
     badge voisin — à l'écran comme à l'impression. */
  .relance-tag-action { font-size: .75rem; padding: 1px 6px; white-space: nowrap; }
  .relance-numero { font-size: .8rem; font-weight: 700; color: var(--color-primary); white-space: nowrap; }
  .relance-titre { font-size: .88rem; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; flex: 1; }
  .relance-item-right { display: flex; align-items: center; gap: .4rem; margin-left: auto; flex-shrink: 0; }
  .relance-date { font-size: .75rem; color: var(--color-text-muted); white-space: nowrap; }
  .relance-date-overdue { color: #b45309; font-weight: 600; }
</style>
