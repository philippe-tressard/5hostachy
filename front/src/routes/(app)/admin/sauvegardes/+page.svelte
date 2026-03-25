<script lang="ts">
	import { onMount } from 'svelte';
	import { admin, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { siteNomStore } from '$lib/stores/pageConfig';

	$: _siteNom = $siteNomStore;

	let config: any = { frequence: 'quotidienne', heure: '02:00', nb_versions: 7 };
	let history: any[] = [];
	let loading = true;
	let saving = false;
	let triggering = false;

	onMount(async () => {
		try {
			const [cfg, hist] = await Promise.all([
				admin.backupConfig().catch(() => config),
				admin.backupHistory().catch(() => []),
			]);
			config = cfg;
			history = hist;
		} catch { toast('error', 'Erreur de chargement'); }
		finally { loading = false; }
	});

	async function saveConfig() {
		saving = true;
		try {
			await admin.updateBackupConfig(config);
			toast('success', 'Configuration sauvegardée');
		} catch { toast('error', 'Erreur lors de la sauvegarde'); }
		finally { saving = false; }
	}

	async function triggerNow() {
		triggering = true;
		try {
			await admin.triggerBackup();
			toast('success', 'Sauvegarde lancée');
			setTimeout(async () => {
				history = await admin.backupHistory().catch(() => history);
			}, 2000);
		} catch { toast('error', 'Erreur lors du déclenchement'); }
		finally { triggering = false; }
	}

	function fileSize(bytes: number) {
		if (!bytes) return '—';
		if (bytes < 1024) return bytes + ' B';
		if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
		return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
	}
</script>

<svelte:head><title>Admin — Sauvegardes — {_siteNom}</title></svelte:head>

<h1 style="font-size:1.3rem;font-weight:700;margin-bottom:1.5rem">&#x1F4BE; Sauvegardes</h1>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else}
<div style="max-width:600px;display:flex;flex-direction:column;gap:1.5rem">

	<!-- Config -->
	<section class="card" style="padding:1.25rem">
		<h2 class="section-title">Configuration automatique</h2>
		<form on:submit|preventDefault={saveConfig} style="display:flex;flex-direction:column;gap:.75rem">
			<label class="form-group">
				<span>Fréquence</span>
				<select class="input" bind:value={config.frequence}>
					<option value="quotidienne">Quotidienne</option>
					<option value="hebdomadaire">Hebdomadaire</option>
					<option value="mensuelle">Mensuelle</option>
					<option value="desactivee">Désactivée</option>
				</select>
			</label>
			<label class="form-group">
				<span>Heure d'exécution</span>
				<input class="input" type="time" bind:value={config.heure} />
			</label>
			<label class="form-group">
				<span>Nombre de versions à conserver</span>
				<input class="input" type="number" min="1" max="99" bind:value={config.nb_versions} />
			</label>
			<button class="btn btn-primary" type="submit" style="align-self:flex-start" disabled={saving}>
				{saving ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</form>
	</section>

	<!-- Sauvegarde manuelle -->
	<section class="card" style="padding:1.25rem">
		<h2 class="section-title">Sauvegarde immédiate</h2>
		<p style="font-size:.875rem;color:var(--color-text-muted);margin-bottom:.75rem">
			Déclenche une sauvegarde de la base de données maintenant.
		</p>
		<button class="btn btn-secondary" on:click={triggerNow} disabled={triggering}>
			{triggering ? '⏳ En cours…' : '\u{1F680} Sauvegarder maintenant'}
		</button>
	</section>

	<!-- Historique -->
	<section>
		<h2 class="section-title">Historique des sauvegardes</h2>
		{#if history.length === 0}
			<div class="empty-state">
				<p>Aucune sauvegarde trouvée.</p>
			</div>
		{:else}
			{#each history as entry}
				<div class="card backup-row" style="margin-bottom:.35rem">
					<div>
						<strong style="font-size:.9rem">{entry.nom ?? entry.fichier ?? 'Sauvegarde'}</strong>
						<small style="display:block;color:var(--color-text-muted)">
							{new Date(entry.cree_le ?? entry.date).toLocaleDateString('fr-FR')}
							{new Date(entry.cree_le ?? entry.date).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
						</small>
					</div>
					<div style="display:flex;align-items:center;gap:.75rem">
						<span style="font-size:.85rem;color:var(--color-text-muted)">{fileSize(entry.taille)}</span>
						<span class="badge {entry.statut === 'ok' ? 'badge-green' : 'badge-red'}">
							{entry.statut ?? 'ok'}
						</span>
					</div>
				</div>
			{/each}
		{/if}
	</section>
</div>
{/if}

<style>
	.section-title { font-size: .8rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--color-text-muted); margin-bottom: .75rem; }
	.form-group { display: flex; flex-direction: column; gap: .25rem; font-size: .875rem; }
	.form-group span { color: var(--color-text-muted); font-size: .8rem; }
	.backup-row { display: flex; justify-content: space-between; align-items: center; padding: .7rem 1rem; }
</style>
