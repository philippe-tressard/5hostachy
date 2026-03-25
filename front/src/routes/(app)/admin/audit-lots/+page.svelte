<script lang="ts">
	import { onMount } from 'svelte';
	import { admin as adminApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { siteNomStore } from '$lib/stores/pageConfig';
	import Icon from '$lib/components/Icon.svelte';

	$: _siteNom = $siteNomStore;

	let rows: any[] = [];
	let loading = true;
	let filtre = '';
	let deletingUserId: number | null = null;

	async function charger() {
		loading = true;
		try {
			rows = await adminApi.auditUserLots();
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur chargement');
		} finally {
			loading = false;
		}
	}

	async function supprimer(ul: any) {
		if (!confirm(`Supprimer l'association de « ${ul.user_nom} » au lot ${ul.lot_numero} (${ul.batiment}) ?`)) return;
		try {
			await adminApi.supprimerUserLot(ul.user_lot_id);
			toast('success', 'Association supprimée');
			rows = rows.filter(r => r.user_lot_id !== ul.user_lot_id);
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur suppression');
		}
	}

	async function supprimerToutesPourUtilisateur(g: { user_id: number; user_nom: string; lots: any[] }) {
		if (!g.lots.length) return;
		if (!confirm(`Supprimer ${g.lots.length} association(s) pour « ${g.user_nom} » ?`)) return;
		deletingUserId = g.user_id;
		try {
			const results = await Promise.allSettled(
				g.lots.map((ul) => adminApi.supprimerUserLot(ul.user_lot_id))
			);
			const ok = results.filter(r => r.status === 'fulfilled').length;
			const ko = results.length - ok;
			if (ok > 0) {
				const idsToDelete = new Set<number>();
				results.forEach((r, idx) => {
					if (r.status === 'fulfilled') idsToDelete.add(g.lots[idx].user_lot_id);
				});
				rows = rows.filter((r) => !idsToDelete.has(r.user_lot_id));
			}
			if (ko === 0) {
				toast('success', `${ok} association(s) supprimée(s)`);
			} else {
				// Rechargement pour garder un état cohérent si suppression partielle.
				await charger();
				toast('error', `${ko} suppression(s) en échec (${ok} réussie(s))`);
			}
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur suppression en masse');
		} finally {
			deletingUserId = null;
		}
	}

	$: grouped = (() => {
		const map = new Map<number, { user_id: number; user_nom: string; user_statut: string; lots: any[] }>();
		for (const r of filtered) {
			if (!map.has(r.user_id)) map.set(r.user_id, { user_id: r.user_id, user_nom: r.user_nom, user_statut: r.user_statut, lots: [] });
			map.get(r.user_id)!.lots.push(r);
		}
		return [...map.values()].sort((a, b) => a.user_nom.localeCompare(b.user_nom));
	})();

	$: filtered = filtre
		? rows.filter(r =>
			r.user_nom.toLowerCase().includes(filtre.toLowerCase()) ||
			r.lot_numero?.toLowerCase().includes(filtre.toLowerCase()) ||
			r.batiment?.toLowerCase().includes(filtre.toLowerCase())
		)
		: rows;

	onMount(charger);
</script>

<svelte:head><title>Audit associations lots — {_siteNom}</title></svelte:head>

<div class="page-header">
	<h1 style="display:flex;align-items:center;gap:.4rem"><Icon name="search" size={20} />Audit associations lots</h1>
	<a href="/admin" class="btn btn-sm btn-outline" style="margin-left:auto">← Retour admin</a>
</div>
<p style="color:var(--color-text-muted);font-size:.9rem;margin:0 0 1rem">
	Liste toutes les associations utilisateur ↔ lot actives. Permet de repérer et supprimer les affectations erronées (faux positifs de l'auto-match).
</p>

<div style="display:flex;gap:.5rem;align-items:center;margin-bottom:1rem;flex-wrap:wrap">
	<input class="input" type="text" placeholder="Filtrer par nom, lot ou bâtiment…" bind:value={filtre} style="max-width:320px" />
	<span style="color:var(--color-text-muted);font-size:.85rem">{filtered.length} association{filtered.length > 1 ? 's' : ''} — {grouped.length} utilisateur{grouped.length > 1 ? 's' : ''}</span>
</div>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if grouped.length === 0}
	<p style="color:var(--color-text-muted)">Aucune association trouvée.</p>
{:else}
	{#each grouped as g}
		<div class="card" style="margin-bottom:.75rem;padding:.75rem 1rem">
			<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem">
				<strong>{g.user_nom}</strong>
				<span class="badge badge-outline" style="font-size:.75rem">{g.user_statut}</span>
				<span style="color:var(--color-text-muted);font-size:.8rem">— {g.lots.length} lot{g.lots.length > 1 ? 's' : ''}</span>
				<button
					class="btn btn-sm btn-outline"
					style="margin-left:auto"
					disabled={deletingUserId === g.user_id}
					on:click={() => supprimerToutesPourUtilisateur(g)}
				>
					{deletingUserId === g.user_id ? 'Suppression…' : `Supprimer les ${g.lots.length} associations`}
				</button>
			</div>
			<table class="table" style="table-layout:fixed;width:100%;margin:0">
				<colgroup><col style="width:25%"><col style="width:20%"><col style="width:20%"><col style="width:20%"><col style="width:15%"></colgroup>
				<thead><tr><th>Lot</th><th>Type lot</th><th>Bâtiment</th><th>Lien</th><th></th></tr></thead>
				<tbody>
					{#each g.lots as ul}
						<tr>
							<td style="font-family:monospace">{ul.lot_numero}</td>
							<td>{ul.lot_type}</td>
							<td>{ul.batiment}</td>
							<td><span class="badge badge-blue">{ul.type_lien}</span></td>
							<td style="text-align:right">
								<button class="btn-icon-danger" title="Supprimer cette association" on:click={() => supprimer(ul)}>&#x1F5D1;️</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/each}
{/if}
