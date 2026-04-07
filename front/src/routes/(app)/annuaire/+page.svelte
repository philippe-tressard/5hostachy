<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import QRCode from '$lib/components/QRCode.svelte';
	import { onMount } from 'svelte';
	import { annuaire as annuaireApi } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';

	$: _pc = getPageConfig($configStore, 'annuaire', { titre: 'Annuaire', navLabel: 'Annuaire', icone: 'users', descriptif: "Coordonnées des membres du Conseil Syndical et du Syndic. En cas d'urgence, contactez le syndic directement par téléphone. Sinon, faites une demande depuis la plateforme." });
	$: _siteNom = $siteNomStore;

	interface MembreCS  { id: number; genre: string; prenom: string; nom: string; batiment_nom: string | null; etage: number | null; est_gestionnaire_site: boolean; est_president: boolean; photo_url: string | null; }
	interface MembreSyndic { id: number; genre: string; prenom: string; nom: string; fonction: string | null; email: string | null; telephone: string | null; est_principal: boolean; photo_url: string | null; }
	interface AnnuaireData {
		cs: { ag_annee: number | null; ag_date: string | null; membres: MembreCS[] };
		syndic: { nom_syndic: string; adresse: string; site_web: string | null; membres: MembreSyndic[] };
		whatsapp_url: string | null;
	}

	let data: AnnuaireData = { cs: { ag_annee: null, ag_date: null, membres: [] }, syndic: { nom_syndic: '', adresse: '', site_web: null, membres: [] }, whatsapp_url: null };
	let loading = true;

	onMount(async () => {
		try {
			data = await annuaireApi.get() as AnnuaireData;
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
	});

	function formatDate(iso: string | null): string {
		if (!iso) return '';
		return new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
	}

	$: batimentsCS = (() => {
		const groups = new Map<string, MembreCS[]>();
		for (const m of data.cs.membres) {
			const key = m.batiment_nom ?? '';
			if (!groups.has(key)) groups.set(key, []);
			groups.get(key)!.push(m);
		}
		const genreOrder = (g: string) => g === 'Mme' ? 0 : g === 'Mlle' ? 1 : 2;
		return [...groups.entries()]
			.sort(([a], [b]) => {
				if (!a && b) return 1;   // sans bâtiment en dernier
				if (a && !b) return -1;
				return a.localeCompare(b, 'fr');
			})
			.map(([key, membres]) => ({
				batiment: key || null,
				membres: [...membres].sort((a, b) => {
					const gd = genreOrder(a.genre) - genreOrder(b.genre);
					if (gd !== 0) return gd;
					return (a.nom ?? '').localeCompare(b.nom ?? '', 'fr');
				}),
			}));
	})();
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<div class="page-header">
	<h1 style="display:flex;align-items:center;gap:.4rem;font-size:1.4rem;font-weight:700"><Icon name={_pc.icone || 'users'} size={20} />{_pc.titre}</h1>
</div>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else}

<section style="margin-bottom:2rem">
	<div style="display:flex;align-items:baseline;gap:1rem;flex-wrap:wrap;margin-bottom:.75rem">
		<h2 class="section-title" style="margin-bottom:0">Conseil Syndical</h2>
		{#if data.cs.ag_annee}
			<span class="ag-info">
				Voté en AG {data.cs.ag_annee}{#if data.cs.ag_date} - {formatDate(data.cs.ag_date)}{/if}
			</span>
		{/if}
	</div>
	{#if data.whatsapp_url}
		<div class="url-block" style="margin-bottom:.75rem">
			<QRCode data={data.whatsapp_url} size={32} />
			<div>
				<strong>Groupe WhatsApp copropriété</strong>
				<span class="contact-societe"><a href={data.whatsapp_url} target="_blank" rel="noopener">{data.whatsapp_url}</a></span>
			</div>
		</div>
	{/if}
	{#if data.cs.membres.length === 0}
		<p style="color:var(--color-text-muted);font-size:.9rem">Aucun membre CS enregistré.</p>
	{:else if batimentsCS.length > 1}
		{#each batimentsCS as groupe}
			<div class="batiment-section">
				<div class="batiment-label">
					<Icon name="building-2" size={12} />
					{groupe.batiment ? `Bâtiment ${groupe.batiment}` : 'Sans bâtiment'}
				</div>
				<div class="contact-grid">
					{#each groupe.membres as m}
						<div class="contact-card card">
							{#if m.est_gestionnaire_site}
								<span class="site-manager-icon" title="Gestionnaire {_siteNom}" aria-label="Gestionnaire de {_siteNom}">
									<Icon name="building-2" size={12} />
								</span>
							{/if}
							{#if m.est_president}
								<span class="president-icon" title="Président du Conseil Syndical" aria-label="Président du Conseil Syndical">
									<Icon name="shield" size={12} />
								</span>
							{/if}
							{#if m.photo_url}
								<img class="avatar" src={m.photo_url} alt="{m.prenom} {m.nom}" />
							{:else}
								<div class="avatar">{m.prenom[0]}{m.nom[0]}</div>
							{/if}
							<div>
								<strong>{m.genre} {m.prenom} <span class="nom-upper">{m.nom}</span></strong>
								{#if m.etage != null}
									<div class="contact-loc">Étage {m.etage}</div>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/each}
	{:else}
		<div class="contact-grid">
			{#each data.cs.membres as m}
				<div class="contact-card card">
					{#if m.est_gestionnaire_site}
						<span class="site-manager-icon" title="Gestionnaire {_siteNom}" aria-label="Gestionnaire de {_siteNom}">
							<Icon name="building-2" size={12} />
						</span>
					{/if}
					{#if m.est_president}
						<span class="president-icon" title="Président du Conseil Syndical" aria-label="Président du Conseil Syndical">
							<Icon name="shield" size={12} />
						</span>
					{/if}
					{#if m.photo_url}
						<img class="avatar" src={m.photo_url} alt="{m.prenom} {m.nom}" />
					{:else}
						<div class="avatar">{m.prenom[0]}{m.nom[0]}</div>
					{/if}
					<div>
						<strong>{m.genre} {m.prenom} <span class="nom-upper">{m.nom}</span></strong>
						{#if m.batiment_nom || m.etage != null}
							<div class="contact-loc">{#if m.batiment_nom}Bât. {m.batiment_nom}{/if}{#if m.batiment_nom && m.etage != null} - {/if}{#if m.etage != null}Étage {m.etage}{/if}</div>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}

</section>

<section>
	<h2 class="section-title">Syndic</h2>
	{#if data.syndic.nom_syndic}
		<p class="syndic-header">
			<strong>{data.syndic.nom_syndic}</strong>
			{#if data.syndic.adresse}<span class="contact-societe">{data.syndic.adresse}</span>{/if}
		</p>
		{#if data.syndic.site_web}
			<div class="url-block">
				<QRCode data={data.syndic.site_web} size={32} />
				<div>
					<strong>Espace client</strong>
					<span class="contact-societe"><a href={data.syndic.site_web} target="_blank" rel="noopener">{data.syndic.site_web}</a></span>
				</div>
			</div>
		{/if}
	{/if}
	{#if data.syndic.membres.length === 0}
		<p style="color:var(--color-text-muted);font-size:.9rem">Aucun contact syndic enregistré.</p>
	{:else}
		<div class="contact-grid">
			{#each data.syndic.membres as m}
				<div class="contact-card card" class:card-principal={m.est_principal}>
					{#if m.est_principal}
						<span class="star-principal-badge" title="Gestionnaire principal">
							★
						</span>
					{/if}
					{#if m.photo_url}
						<img class="avatar" class:avatar-accent={m.est_principal} src={m.photo_url} alt="{m.prenom} {m.nom}" />
					{:else}
						<div class="avatar" class:avatar-accent={m.est_principal}>{m.prenom[0]}{m.nom[0]}</div>
					{/if}
					<div>
						<strong>{m.genre} {m.prenom} <span class="nom-upper">{m.nom}</span></strong>
						{#if m.fonction}<div class="contact-role">{m.fonction}</div>{/if}
						{#if m.email}
							<a href="mailto:{m.email}" class="contact-email">{m.email}</a>
						{/if}
						{#if m.telephone}
							{#each m.telephone.split(',').filter(t => t.trim()) as tel}
								<a href="tel:{tel.trim()}" class="contact-email">&#x1F4DE; {tel.trim()}</a>
							{/each}
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</section>

{/if}

<style>
	.section-title { font-size: .85rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--color-text-muted); margin-bottom: .75rem; }
	.contact-loc { font-size: .78rem; color: var(--color-text-muted); margin-top: .1rem; }
	.ag-info { font-size: .8rem; color: var(--color-text-muted); }
	.syndic-header { margin-bottom: .75rem; display: flex; flex-direction: column; gap: .15rem; }

	.batiment-section { margin-bottom: 1.5rem; }
	.batiment-label { font-size: .72rem; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; color: var(--color-primary); border-left: 3px solid var(--color-primary); padding-left: .5rem; margin-bottom: .6rem; display: flex; align-items: center; gap: .3rem; }
	.contact-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 1rem; }
	.contact-card { display: flex; align-items: flex-start; gap: 1rem; padding: 1.4rem 1rem .9rem; position: relative; }
	.card-principal { border-left: 3px solid var(--color-accent, #C9983A); }
	.site-manager-icon,
	.president-icon {
		position: absolute;
		top: -10px;
		right: 10px;
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 999px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		color: #fff;
		box-shadow: 0 1px 2px rgba(0, 0, 0, .18);
		z-index: 1;
	}
	.site-manager-icon {
		background: #0f766e;
	}
	.president-icon {
		background: #1e40af;
	}
	.star-principal-badge {
		position: absolute;
		top: -10px;
		right: 10px;
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 999px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		color: #fff;
		background: var(--color-accent, #C9983A);
		box-shadow: 0 1px 2px rgba(0, 0, 0, .18);
		font-size: .9rem;
		z-index: 1;
	}

	.avatar { width: 2.5rem; height: 2.5rem; border-radius: 50%; background: var(--color-primary); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: .95rem; flex-shrink: 0; }
	img.avatar { object-fit: cover; background: none; padding: 0; }
	.avatar.avatar-accent { background: var(--color-accent, #C9983A); }



	.nom-upper { text-transform: uppercase; }
	.contact-societe { font-size: .8rem; font-style: italic; color: var(--color-text-muted); margin: .1rem 0; display: block; }
	.contact-role { font-size: .8rem; color: var(--color-text-muted); margin: .1rem 0; }
	.contact-email { display: block; font-size: .85rem; color: var(--color-primary); text-decoration: none; margin-top: .1rem; }
	.contact-email:hover { text-decoration: underline; }

	.url-block {
		display: flex;
		align-items: center;
		gap: .75rem;
		margin-top: .75rem;
		padding: .6rem .75rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		max-width: 520px;
	}
	.url-block strong { font-size: .85rem; display: block; }
	.url-block .contact-societe { margin: 0; }
	.url-block a { word-break: break-all; }
</style>
