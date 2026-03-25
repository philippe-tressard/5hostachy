<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
import { onMount } from 'svelte';
	import { notifications as notifApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml, safeRichContent } from '$lib/sanitize';

	$: _pc = getPageConfig($configStore, 'notifications', { titre: 'Notifications', navLabel: 'Notifications', icone: 'bell', descriptif: 'Vos alertes et messages.' });
	$: _siteNom = $siteNomStore;

	let items: any[] = [];
	let loading = true;
	let deleting = new Set<number>();

	onMount(async () => {
		await load();
	});

	async function load() {
		loading = true;
		try {
			items = await notifApi.list();
		} catch {
			toast('error', 'Erreur lors du chargement');
		} finally {
			loading = false;
		}
	}

	async function markRead(id: number) {
		try {
			await notifApi.markRead(id);
			items = items.map(n => n.id === id ? { ...n, lue: true } : n);
		} catch { toast('error', 'Erreur'); }
	}

	async function markAll() {
		try {
			await notifApi.markAllRead();
			items = items.map(n => ({ ...n, lue: true }));
			toast('success', 'Toutes les notifications marquées comme lues');
		} catch { toast('error', 'Erreur'); }
	}

	async function remove(id: number) {
		if (!confirm('Supprimer cette notification ?')) return;
		deleting = new Set([...deleting, id]);
		try {
			await notifApi.delete(id);
			items = items.filter(n => n.id !== id);
		} catch { toast('error', 'Erreur lors de la suppression'); }
		finally { deleting.delete(id); deleting = deleting; }
	}

	$: unread = items.filter(n => !n.lue).length;
	$: grouped = group(items);

	function group(notifs: any[]) {
		const today: any[] = [];
		const older: any[] = [];
		const now = Date.now();
		notifs.forEach(n => {
			const age = now - new Date(n.cree_le).getTime();
			if (age < 86400000) today.push(n);
			else older.push(n);
		});
		return { today, older };
	}

	function urgenceClass(n: any) {
		if (n.urgente) return 'badge badge-red';
		return '';
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<a href="/tableau-de-bord" class="back-link">← Tableau de bord</a>

<div class="page-header" style="justify-content:space-between;flex-wrap:wrap;gap:.5rem">
	<h1 style="display:flex;align-items:center;gap:.4rem;font-size:1.4rem;font-weight:700"><Icon name={_pc.icone || 'bell'} size={20} />{_pc.titre}</h1>
	<div style="display:flex;gap:.5rem;align-items:center">
		{#if unread > 0}
			<span style="font-size:.85rem;color:var(--color-text-muted)">{unread} non lue{unread > 1 ? 's' : ''}</span>
			<button class="btn btn-secondary btn-sm" on:click={markAll}>Tout marquer lu</button>
		{/if}
	</div>
</div>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if items.length === 0}
	<div class="empty-state">
		<h3>Aucune notification</h3>
		<p>Vous êtes à jour !</p>
	</div>
{:else}
	{#if grouped.today.length > 0}
		<h2 class="section-title">Aujourd'hui</h2>
		{#each grouped.today as n}
			<div class="notif-row card {n.lue ? 'notif-read' : 'notif-unread'}" role="article">
				<div class="notif-body">
					{#if !n.lue}<div class="unread-dot"></div>{/if}
					<div class="notif-content">
						<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.2rem">
							<strong style="font-size:.95rem">{n.titre}</strong>
							{#if n.urgente}<span class="badge badge-red">Urgent</span>{/if}
						</div>
						<p style="font-size:.875rem;color:var(--color-text-muted);margin:0">{@html safeRichContent(n.corps)}</p>
						<small style="color:var(--color-text-muted);font-size:.75rem">{new Date(n.cree_le).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</small>
					</div>
				</div>
				<div class="notif-actions">
					{#if !n.lue}
						<button class="btn btn-secondary btn-sm" on:click={() => markRead(n.id)}>Marquer lu</button>
					{/if}
					<button class="btn btn-danger btn-sm" disabled={deleting.has(n.id)} on:click={() => remove(n.id)}>✕</button>
				</div>
			</div>
		{/each}
	{/if}

	{#if grouped.older.length > 0}
		<h2 class="section-title" style="margin-top:1.25rem">Plus anciennes</h2>
		{#each grouped.older as n}
			<div class="notif-row card {n.lue ? 'notif-read' : 'notif-unread'}" role="article">
				<div class="notif-body">
					{#if !n.lue}<div class="unread-dot"></div>{/if}
					<div class="notif-content">
						<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.2rem">
							<strong style="font-size:.95rem">{n.titre}</strong>
							{#if n.urgente}<span class="badge badge-red">Urgent</span>{/if}
						</div>
						<p style="font-size:.875rem;color:var(--color-text-muted);margin:0">{@html safeRichContent(n.corps)}</p>
						<small style="color:var(--color-text-muted);font-size:.75rem">{new Date(n.cree_le).toLocaleDateString('fr-FR')}</small>
					</div>
				</div>
				<div class="notif-actions">
					{#if !n.lue}
						<button class="btn btn-secondary btn-sm" on:click={() => markRead(n.id)}>Marquer lu</button>
					{/if}
					<button class="btn btn-danger btn-sm" disabled={deleting.has(n.id)} on:click={() => remove(n.id)}>✕</button>
				</div>
			</div>
		{/each}
	{/if}
{/if}

<style>
	.header-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: .5rem; }
	.section-title { font-size: .8rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--color-text-muted); margin-bottom: .5rem; }
	.notif-row { display: flex; justify-content: space-between; align-items: flex-start; padding: .85rem 1rem; margin-bottom: .4rem; gap: .5rem; }
	.notif-unread { border-left: 3px solid var(--color-primary); }
	.notif-read { opacity: .7; }
	.notif-body { display: flex; align-items: flex-start; gap: .6rem; flex: 1; min-width: 0; }
	.notif-content { flex: 1; min-width: 0; }
	.notif-actions { display: flex; gap: .35rem; flex-shrink: 0; }
	.unread-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--color-primary); margin-top: 6px; flex-shrink: 0; }

	.back-link { display: inline-flex; align-items: center; gap: .3rem; font-size: .85rem; color: var(--color-text-muted); text-decoration: none; margin-bottom: .75rem; }
	.back-link:hover { color: var(--color-primary); }
</style>
