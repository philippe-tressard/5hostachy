<!--
  L'onglet **Télémétrie** de l'administration : qui utilise quoi, et quand.

  POURQUOI CE COMPOSANT (19/08/2026). Les sept écrans d'administration qui
  vivaient sur leur propre route sont devenus des onglets — pour qu'on n'en sorte
  plus, donc sans bouton « ← Retour ». Leur aiguillage ajoutait 53 lignes à
  `admin/+page.svelte`, déjà à 1 786, et le garde-fou de modularité (rang 1) l'a
  refusé.

  🔴 **La réponse est de découper, pas de tasser** — c'est tout l'objet de #453.
  La télémétrie est le plus gros panneau restant de la page et le plus autonome :
  un appel réseau, trois variables, aucun état partagé avec le reste de l'écran.

  Troisième extraction du même patron, après `OngletWhatsApp` et `OngletSmtp`.
-->
<script lang="ts">
	import { api } from '$lib/api';
	import Icon from '$lib/components/Icon.svelte';
	import TopPages from '$lib/components/TopPages.svelte';
	import Pastille from '$lib/components/Pastille.svelte';
	import { fmtDatetimeShort as fmt } from '$lib/date';

	let telemetryData: any = null;
	let telemetryLoading = true;
	let tlScope: 'jour' | 'mois' | 'annee' = 'jour';

	export async function loadTelemetry() {
		telemetryLoading = true;
		try {
			telemetryData = await api.get<any>(`/telemetry/dashboard?scope=${tlScope}`);
		} catch {
			telemetryData = null;
		} finally {
			telemetryLoading = false;
		}
	}

	function switchTlScope(s: 'jour' | 'mois' | 'annee') {
		tlScope = s;
		loadTelemetry();
	}

	//  L'onglet ne se rend que lorsqu'il est choisi : charger au montage suffit, et
	//  évite à la page d'avoir à déclencher l'appel depuis son bouton.
	loadTelemetry();
</script>

<section class="card config-section">
	<h2 class="config-section-title">
		<Icon name="bar-chart-3" size={17} />Télémétrie — Utilisation de l'application
	</h2>
	<p class="muted" style="font-size:.85rem">
		Statistiques d'utilisation : qui utilise quoi et quand.
	</p>

	<!-- Sélecteur Jour / Mois / Année -->
	<div class="tl-scope-switch" style="margin:.75rem 0 1rem">
		<Pastille active={tlScope === 'jour'} on:click={() => switchTlScope('jour')}>Jour</Pastille>
		<Pastille active={tlScope === 'mois'} on:click={() => switchTlScope('mois')}
			>Mois (30 j)</Pastille
		>
		<Pastille active={tlScope === 'annee'} on:click={() => switchTlScope('annee')}
			>Année (10 ans)</Pastille
		>
	</div>

	{#if telemetryLoading}
		<p class="muted">Chargement des statistiques...</p>
	{:else if !telemetryData}
		<div class="empty-state">
			<h3>Aucune donnée de télémétrie</h3>
			<p>Les données apparaîtront après les premières visites.</p>
		</div>
	{:else}
		<!-- KPI universels -->
		<div class="tl-kpi-row">
			<div class="tl-kpi">
				<div class="tl-kpi-value">{telemetryData.kpi.vues ?? 0}</div>
				<div class="tl-kpi-label">
					{tlScope === 'jour'
						? "Pages vues aujourd'hui"
						: tlScope === 'mois'
							? 'Pages vues (30j)'
							: 'Pages vues (total)'}
				</div>
			</div>
			{#if telemetryData.kpi.utilisateurs != null}
				<div class="tl-kpi">
					<div class="tl-kpi-value">{telemetryData.kpi.utilisateurs}</div>
					<div class="tl-kpi-label">
						{tlScope === 'jour' ? "Utilisateurs actifs aujourd'hui" : 'Utilisateurs uniques (pic)'}
					</div>
				</div>
			{/if}
			<div class="tl-kpi">
				<div class="tl-kpi-value">{telemetryData.kpi.pages ?? 0}</div>
				<div class="tl-kpi-label">Pages distinctes visitées</div>
			</div>
			{#if telemetryData.kpi.heure_pointe}
				<div class="tl-kpi">
					<div class="tl-kpi-value">{telemetryData.kpi.heure_pointe}</div>
					<div class="tl-kpi-label">🔺 Heure de pointe</div>
				</div>
			{/if}
			{#if telemetryData.kpi.moy_vues_utilisateur != null}
				<div class="tl-kpi">
					<div class="tl-kpi-value">{telemetryData.kpi.moy_vues_utilisateur}</div>
					<div class="tl-kpi-label">Moy. vues / utilisateur</div>
				</div>
			{/if}
			{#if telemetryData.kpi.moy_vues_jour != null}
				<div class="tl-kpi">
					<div class="tl-kpi-value">{telemetryData.kpi.moy_vues_jour}</div>
					<div class="tl-kpi-label">Moy. vues / jour</div>
				</div>
			{/if}
			{#if telemetryData.kpi.moy_utilisateurs_jour != null}
				<div class="tl-kpi">
					<div class="tl-kpi-value">{telemetryData.kpi.moy_utilisateurs_jour}</div>
					<div class="tl-kpi-label">Moy. utilisateurs / jour</div>
				</div>
			{/if}
			{#if telemetryData.kpi.mois_actifs != null}
				<div class="tl-kpi">
					<div class="tl-kpi-value">{telemetryData.kpi.mois_actifs}</div>
					<div class="tl-kpi-label">Mois avec activité</div>
				</div>
			{/if}
			{#if telemetryData.kpi.moy_vues_mois != null}
				<div class="tl-kpi">
					<div class="tl-kpi-value">{telemetryData.kpi.moy_vues_mois}</div>
					<div class="tl-kpi-label">Moy. vues / mois</div>
				</div>
			{/if}
		</div>

		<!-- Jour le plus actif (scope mois) -->
		{#if tlScope === 'mois' && telemetryData.kpi.jour_pointe}
			<div class="tl-kpi-row" style="margin-top:.75rem">
				<div class="tl-kpi">
					<div class="tl-kpi-value">
						{telemetryData.kpi.jour_pointe.uniques}
						<span style="font-size:.6em;font-weight:400">utilisateurs</span>
					</div>
					<div class="tl-kpi-label">
						🏆 Jour le plus actif — {telemetryData.kpi.jour_pointe.jour}
					</div>
				</div>
			</div>
		{/if}

		<!-- Records (scope annee) -->
		{#if tlScope === 'annee' && (telemetryData.kpi.record_jour || telemetryData.kpi.record_mois)}
			<div class="tl-kpi-row" style="margin-top:.75rem">
				{#if telemetryData.kpi.record_jour}
					<div class="tl-kpi">
						<div class="tl-kpi-value">
							{telemetryData.kpi.record_jour.uniques}
							<span style="font-size:.6em;font-weight:400">utilisateurs</span>
						</div>
						<div class="tl-kpi-label">🏆 Record jour — {telemetryData.kpi.record_jour.jour}</div>
					</div>
				{/if}
				{#if telemetryData.kpi.record_mois}
					<div class="tl-kpi">
						<div class="tl-kpi-value">
							{telemetryData.kpi.record_mois.uniques}
							<span style="font-size:.6em;font-weight:400">utilisateurs</span>
						</div>
						<div class="tl-kpi-label">🏆 Record mois — {telemetryData.kpi.record_mois.mois}</div>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Graphe (barres CSS) — adaptatif au scope -->
		{#if telemetryData.chart.length > 0}
			{@const maxVal = Math.max(...telemetryData.chart.map((x: { total: number }) => x.total), 1)}
			{@const yTicks = (() => {
				const step =
					Math.ceil(
						maxVal /
							4 /
							(maxVal < 10 ? 1 : maxVal < 50 ? 5 : maxVal < 200 ? 10 : maxVal < 1000 ? 50 : 100),
					) * (maxVal < 10 ? 1 : maxVal < 50 ? 5 : maxVal < 200 ? 10 : maxVal < 1000 ? 50 : 100);
				return [4, 3, 2, 1, 0].map((i) => i * step);
			})()}
			<div class="card" style="margin-top:1.25rem">
				<h3 class="tl-section-title">📈 {telemetryData.chart_label}</h3>
				<div class="tl-chart-wrap">
					<div class="tl-y-axis">
						{#each yTicks as tick}
							<div class="tl-y-tick" style="bottom:{(tick / (yTicks[0] || 1)) * 100}%">{tick}</div>
						{/each}
					</div>
					<div class="tl-chart-inner">
						{#each yTicks as tick}
							<div
								class="tl-y-gridline"
								style="bottom:{(tick / (yTicks[0] || 1)) * 120 + 18}px"
							></div>
						{/each}
						<div class="tl-chart">
							{#each telemetryData.chart as d}
								<div
									class="tl-bar-col {tlScope === 'annee' ? 'tl-bar-col-month' : ''}"
									title="{d.label} — {d.total} vues{d.uniques != null
										? `, ${d.uniques} uniques`
										: ''}"
								>
									<div
										class="tl-bar {tlScope === 'annee' ? 'tl-bar-month' : ''}"
										style="height:{Math.max(4, (d.total / maxVal) * 100)}%"
									></div>
									<div class="tl-bar-label">{d.label}</div>
								</div>
							{/each}
						</div>
					</div>
				</div>
			</div>
		{/if}

		<!-- Top pages — tableau et total extraits en composant (#total des vues) -->
		<TopPages
			pages={telemetryData.top_pages}
			vuesNonAttribuees={telemetryData.kpi?.vues_non_attribuees ?? 0}
		/>

		<!-- Utilisateurs les plus actifs (scope jour et mois) -->
		{#if telemetryData.top_users && telemetryData.top_users.length > 0}
			<div class="card" style="margin-top:1.25rem">
				<h3 class="tl-section-title">👥 Utilisateurs les plus actifs</h3>
				<table class="table">
					<thead
						><tr
							><th>Utilisateur</th><th>Type</th><th>Bâtiment</th><th style="text-align:right"
								>Vues</th
							><th style="text-align:right">Pages diff.</th><th style="text-align:right"
								>Dernière connexion</th
							></tr
						></thead
					>
					<tbody>
						{#each telemetryData.top_users as u}
							<tr>
								<td style="font-size:.85rem">{u.nom}</td>
								<td style="font-size:.8rem;color:var(--color-text-muted)">{u.statut ?? '—'}</td>
								<td style="font-size:.8rem;color:var(--color-text-muted)"
									>{u.batiment_id ? `Bât. ${u.batiment_id}` : '—'}</td
								>
								<td style="text-align:right;font-weight:600">{u.total}</td>
								<td style="text-align:right;color:var(--color-text-muted)">{u.pages}</td>
								<td style="text-align:right;font-size:.82rem;color:var(--color-text-muted)"
									>{u.derniere_connexion ? fmt(u.derniere_connexion) : '—'}</td
								>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}
</section>

<style>
	/*  🔴 CES RÈGLES SONT RESTÉES DANS `admin/+page.svelte` À L'EXTRACTION, et le
	    panneau est parti NU en production (v2.95.0) : les KPI empilés en texte
	    brut, le graphe en colonne de chiffres. Signalé à l'écran, capture à
	    l'appui, le 19/08/2026.

	    Svelte scope ses styles au FICHIER. Déplacer du balisage sans ses règles
	    est la régression que ce dépôt cite dans une dizaine de commentaires
	    depuis la v2.67.11 — et `svelte-check` n'a signalé qu'UN sélecteur orphelin
	    sur dix-sept : il ne protège pas de ce défaut.

	    D'où `npm run lint:classes-nues`, écrit le même jour. La règle était
	    partout ; il manquait le contrôle qui échoue. */
	.tl-scope-switch {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.tl-kpi-row {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(160px, 100%), 1fr));
		gap: 1rem;
		margin-top: 1.25rem;
	}
	.tl-kpi {
		background: var(--color-surface, #fff);
		border: 1px solid var(--color-border);
		border-radius: var(--radius, 8px);
		padding: 1.25rem 1rem;
		text-align: center;
	}
	.tl-kpi-value {
		font-size: 2rem;
		font-weight: 700;
		color: var(--color-primary);
		line-height: 1.1;
	}
	.tl-kpi-label {
		font-size: 0.82rem;
		color: var(--color-text-muted);
		margin-top: 0.3rem;
	}
	.tl-section-title {
		font-size: 0.95rem;
		font-weight: 600;
		margin: 0 0 0.75rem;
		padding: 0.75rem 1rem 0;
	}
	.tl-chart-wrap {
		display: flex;
		gap: 0;
		position: relative;
		margin-top: 0.5rem;
	}
	.tl-y-axis {
		position: relative;
		width: 32px;
		flex-shrink: 0;
		height: 130px;
		margin-bottom: 18px;
	}
	.tl-y-tick {
		position: absolute;
		right: 4px;
		font-size: 0.6rem;
		color: var(--color-text-muted);
		transform: translateY(50%);
		line-height: 1;
		text-align: right;
	}
	.tl-chart-inner {
		position: relative;
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
	}
	.tl-chart-inner .tl-y-gridline {
		position: absolute;
		left: 0;
		right: 0;
		height: 1px;
		background: var(--color-border);
		opacity: 0.5;
		pointer-events: none;
		z-index: 0;
	}
	.tl-chart {
		display: flex;
		align-items: flex-end;
		gap: 2px;
		height: 120px;
		padding: 0 0.25rem 0.5rem 0;
		overflow-x: auto;
		position: relative;
		z-index: 1;
		flex: 1;
	}
	.tl-bar-col {
		display: flex;
		flex-direction: column;
		align-items: center;
		flex: 1;
		min-width: 16px;
		height: 100%;
		justify-content: flex-end;
	}
	.tl-bar {
		background: var(--color-primary);
		border-radius: 3px 3px 0 0;
		width: 100%;
		min-height: 4px;
		transition: height 0.3s;
	}
	.tl-bar-month {
		background: var(--color-primary-light, #93c5fd);
	}
	.tl-bar-label {
		font-size: 0.6rem;
		color: var(--color-text-muted);
		margin-top: 2px;
		white-space: nowrap;
	}
	.tl-bar-col-month {
		min-width: 32px;
	}
</style>
