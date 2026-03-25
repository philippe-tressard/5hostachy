<script lang="ts">
	import { onMount } from 'svelte';
	import { admin, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { siteNomStore } from '$lib/stores/pageConfig';

	$: _siteNom = $siteNomStore;

	let templates: any[] = [];
	let loading = true;
	let editing: any = null;
	let saving = false;

	onMount(async () => {
		try {
			templates = await admin.emailTemplates();
		} catch { toast('error', 'Erreur de chargement'); }
		finally { loading = false; }
	});

	function startEdit(t: any) {
		editing = { ...t };
	}

	function cancelEdit() {
		editing = null;
	}

	async function saveTemplate() {
		saving = true;
		try {
			await admin.updateEmailTemplate(editing.id, {
				sujet: editing.sujet,
				corps: editing.corps,
				actif: editing.actif
			});
			templates = templates.map(t => t.id === editing.id ? { ...t, ...editing } : t);
			toast('success', 'Template mis à jour');
			editing = null;
		} catch { toast('error', 'Erreur lors de la sauvegarde'); }
		finally { saving = false; }
	}

	// Group by domain key prefix
	$: grouped = (() => {
		const map: Record<string, any[]> = {};
		for (const t of templates) {
			const domain = t.domaine ?? t.categorie ?? 'général';
			if (!map[domain]) map[domain] = [];
			map[domain].push(t);
		}
		return map;
	})();
</script>

<svelte:head><title>Admin — Templates email — {_siteNom}</title></svelte:head>

<h1 style="font-size:1.3rem;font-weight:700;margin-bottom:1.5rem">✉️ Templates email</h1>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if templates.length === 0}
	<div class="empty-state">
		<h3>Aucun template configuré</h3>
		<p>Les templates sont définis côté serveur.</p>
	</div>
{:else}
	{#each Object.entries(grouped) as [domain, items]}
		<h2 class="domain-title">{domain}</h2>
		{#each items as t}
			<div class="card template-row">
				<div class="template-info">
					<span class="template-code">{t.code ?? t.nom}</span>
					<span style="font-size:.85rem;color:var(--color-text-muted)">{t.sujet}</span>
				</div>
				<div style="display:flex;align-items:center;gap:.5rem">
					<span class="badge {t.actif ? 'badge-green' : 'badge-red'}">{t.actif ? 'Actif' : 'Inactif'}</span>
					<button class="btn btn-secondary btn-sm" on:click={() => startEdit(t)}>Modifier</button>
				</div>
			</div>
		{/each}
	{/each}

	<!-- Edit modal -->
	{#if editing}
		<div class="modal-overlay" on:click={cancelEdit} role="presentation">
			<div class="modal" on:click|stopPropagation on:keydown role="dialog" aria-modal="true" tabindex="-1">
				<h2 style="font-size:1rem;font-weight:700;margin-bottom:1rem">Modifier — {editing.code ?? editing.nom}</h2>
				<label class="form-group" style="margin-bottom:.75rem">
					<span>Sujet</span>
					<input class="input" bind:value={editing.sujet} />
				</label>
				<label class="form-group" style="margin-bottom:.75rem">
					<span>Corps du message</span>
					<textarea class="input" rows="10" bind:value={editing.corps} style="font-family:monospace;font-size:.8rem"></textarea>
				</label>
				<label class="form-group" style="flex-direction:row;align-items:center;gap:.5rem;margin-bottom:1rem">
					<input type="checkbox" bind:checked={editing.actif} />
					<span>Actif</span>
				</label>
				<div style="background:var(--color-bg-subtle);border:1px solid var(--color-border);border-radius:6px;padding:.75rem;margin-bottom:1rem;font-size:.8rem;color:var(--color-text-muted)">
					<strong>Variables disponibles :</strong> <code>[[prenom]]</code>, <code>[[nom]]</code>, <code>[[lot]]</code>, <code>[[batiment]]</code>, <code>[[lien]]</code>
				</div>
				<div style="display:flex;gap:.5rem;justify-content:flex-end">
					<button class="btn btn-secondary" on:click={cancelEdit}>Annuler</button>
					<button class="btn btn-primary" on:click={saveTemplate} disabled={saving}>
						{saving ? 'Enregistrement…' : 'Enregistrer'}
					</button>
				</div>
			</div>
		</div>
	{/if}
{/if}

<style>
	.domain-title { font-size: .8rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--color-text-muted); margin: 1.25rem 0 .5rem; }
	.template-row { display: flex; justify-content: space-between; align-items: center; padding: .75rem 1rem; margin-bottom: .35rem; }
	.template-info { display: flex; flex-direction: column; gap: .1rem; }
	.template-code { font-weight: 600; font-size: .9rem; }
	.form-group { display: flex; flex-direction: column; gap: .25rem; font-size: .875rem; }
	.form-group span { color: var(--color-text-muted); font-size: .8rem; }
	.modal-overlay { position: fixed; top: 0; right: 0; bottom: 0; left: 0; background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 1rem; }
	.modal { background: var(--color-card); border: 1px solid var(--color-border); border-radius: var(--radius); padding: 1.5rem; width: 100%; max-width: 600px; max-height: 90vh; overflow-y: auto; }
</style>
