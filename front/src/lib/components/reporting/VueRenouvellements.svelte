<!--
  Reporting CS — **renouvellement des contrats et audits réglementaires** : la
  frise des échéances de l'année, et les diagnostics rangés par année.

  Extrait d'`espace-cs/+page.svelte` avec #453. Les calculs de date (fin de
  contrat, préavis, prochaine échéance d'un diagnostic) vivent dans
  `$lib/reporting.ts` : ils sont purs, donc lisibles et testables sans écran.

  ⚠️ Les règles `.frise-*` et `.audit-year-*` ne servent qu'ici et voyagent donc
  avec ce balisage, variantes d'impression comprises. C'est la panne des pastilles
  nues (v2.67.11) qu'on évite, et que `npm run lint:classes-nues` refuse depuis.
-->
<script lang="ts">
	//  ⚠️ Cet écran affichait la valeur BRUTE — `chauffage_collectif` — parce que
	//  la table des libellés vivait dans `prestataires/+page.svelte` et qu'il n'y
	//  avait pas accès. Une table qui vit dans UN écran, les autres s'en passent.
	import { equipLabel } from '$lib/prestataires';
	import { fmtDate } from '$lib/date';
	import { starsDisplay } from '$lib/utils';
	import {
		anneeCourante, PREAVIS_MOIS, MOIS_LABELS,
		contratDateFin, contratDatePreavis, contratUrgence, diagNextDate, diagUrgence,
		type ReportContrat, type ReportPrestataire, type DiagType
	} from '$lib/reporting';

	export let reportContrats: ReportContrat[] = [];
	export let reportPrestataires: ReportPrestataire[] = [];
	export let reportDiagTypes: DiagType[] = [];
	/** Note moyenne et nombre d'avis par prestataire, calculés une fois en amont. */
	export let reportNoteMoyParPrest: Map<number, { moy: number; nb: number }> = new Map();

	//  Relue à chaque recalcul et non figée à l'import : un onglet laissé ouvert la
	//  nuit du réveillon annoncerait sinon les échéances de l'année passée.
	$: ANNEE_COURANTE = anneeCourante();

	/* ── Reactives renouvellements ───────────────────────────────────── */
	$: contratsAvecFin = reportContrats
		.map(c => {
			const result = contratDateFin(c);
			const fin = result?.date ?? null;
			const reconduit = result?.reconduit ?? false;
			const preavis = fin ? contratDatePreavis(fin) : null;
			const urgence: 'preavis' | 'annee' | 'futur' | 'inconnu' = fin ? contratUrgence(fin) : 'inconnu';
			const prest = reportPrestataires.find(p => p.id === c.prestataire_id);
			const noteInfo = reportNoteMoyParPrest.get(c.prestataire_id) ?? null;
			return { ...c, dateFin: fin as Date | null, datePreavis: preavis, urgence, reconduit, prestataireNom: prest?.nom ?? `#${c.prestataire_id}`, noteMoy: noteInfo?.moy ?? null as number | null, nbNotations: noteInfo?.nb ?? 0 };
		})
		.sort((a, b) => {
			// Tri prioritaire : pire note en premier (null = pas de note = en dernier)
			const noteA = a.noteMoy ?? 6;
			const noteB = b.noteMoy ?? 6;
			if (noteA !== noteB) return noteA - noteB;
			// Puis par date de fin
			if (!a.dateFin && !b.dateFin) return 0;
			if (!a.dateFin) return 1;
			if (!b.dateFin) return -1;
			return a.dateFin.getTime() - b.dateFin.getTime();
		});

	$: contratsAnneeCourante = contratsAvecFin.filter(c => {
		if (!c.dateFin) return false;
		// Inclure si la fin OU le préavis tombe dans l'année courante
		if (c.dateFin.getFullYear() === ANNEE_COURANTE) return true;
		if (c.datePreavis && c.datePreavis.getFullYear() === ANNEE_COURANTE) return true;
		return false;
	});

	$: contratsFuturs = contratsAvecFin.filter(c => c.dateFin && c.urgence === 'futur' && !contratsAnneeCourante.includes(c));
	$: contratsInconnus = contratsAvecFin.filter(c => c.urgence === 'inconnu');

	$: diagsAvecNext = reportDiagTypes
		.filter(dt => !dt.non_applicable)
		.map(dt => {
			const isPermanent = dt.frequence ? dt.frequence.toLowerCase().includes('permanent') : false;
			const next = isPermanent ? null : diagNextDate(dt);
			const urgence: 'depasse' | 'annee' | 'futur' | 'inconnu' = next ? diagUrgence(next) : 'inconnu';
			const lastRapport = dt.rapports.find(r => r.date_rapport);
			return { ...dt, nextDate: next as Date | null, urgence, lastRapportDate: lastRapport?.date_rapport ?? null, isPermanent };
		})
		.sort((a, b) => {
			if (!a.nextDate && !b.nextDate) return 0;
			if (!a.nextDate) return 1;
			if (!b.nextDate) return -1;
			return a.nextDate.getTime() - b.nextDate.getTime();
		});

	$: diagsAvecEcheance = diagsAvecNext.filter(d => d.nextDate !== null);
	$: diagsSansEcheance = diagsAvecNext.filter(d => d.nextDate === null && !d.isPermanent);
	$: diagsPermanents = diagsAvecNext.filter(d => d.isPermanent);

	$: diagsParAnnee = (() => {
		const map = new Map<number, typeof diagsAvecEcheance>();
		for (const d of diagsAvecEcheance) {
			const y = d.nextDate!.getFullYear();
			if (y < ANNEE_COURANTE || y > ANNEE_COURANTE + 10) continue;
			if (!map.has(y)) map.set(y, []);
			map.get(y)!.push(d);
		}
		return [...map.entries()].sort((a, b) => a[0] - b[0]);
	})();

	$: renKpiContrats = contratsAnneeCourante.length;
	$: renKpiPreavis = contratsAvecFin.filter(c => c.urgence === 'preavis' || c.urgence === 'inconnu').length;
	$: renKpiDiags = diagsAvecNext.filter(d => d.urgence === 'depasse' || d.urgence === 'annee' || d.urgence === 'inconnu').length;
</script>

<!-- ── Renouvellement contrats & audits ──────────────────────────── -->
<div class="kpi-row" style="margin-bottom:1rem">
	<div class="kpi-card" class:kpi-alert={renKpiPreavis > 0}>
		<div class="kpi-value">{renKpiPreavis}</div>
		<div class="kpi-label">Contrats en préavis</div>
	</div>
	<div class="kpi-card">
		<div class="kpi-value">{renKpiContrats}</div>
		<div class="kpi-label">Échéances contrats en {ANNEE_COURANTE}</div>
	</div>
	<div class="kpi-card" class:kpi-alert={renKpiDiags > 0}>
		<div class="kpi-value">{renKpiDiags}</div>
		<div class="kpi-label">Audits à (re)planifier</div>
	</div>
</div>

<!-- Section 1 : Frise contrats -->
<section class="report-card" style="margin-bottom:1.5rem">
	<h3>📋 Contrats prestataires — échéances {ANNEE_COURANTE}</h3>
	<p class="report-intro">Contrats dont la fin ou le préavis tombe en {ANNEE_COURANTE}. La zone hachurée indique la période de préavis ({PREAVIS_MOIS} mois).</p>

	{#if contratsAnneeCourante.length === 0}
		<div class="empty-state"><h3>Aucune échéance de contrat en {ANNEE_COURANTE}</h3></div>
	{:else}
		<div class="frise-container">
			<div class="frise-months">
				{#each MOIS_LABELS as m}<div class="frise-month-label">{m}</div>{/each}
			</div>
			{#each contratsAnneeCourante.filter((x): x is typeof x & { dateFin: Date } => !!x.dateFin) as c (c.id)}
				{@const finDansAnnee = c.dateFin.getFullYear() === ANNEE_COURANTE}
				{@const moisFin = finDansAnnee ? c.dateFin.getMonth() : 11.9}
				{@const moisPreavis = c.datePreavis && c.datePreavis.getFullYear() < ANNEE_COURANTE ? 0 : (c.datePreavis?.getMonth() ?? 0)}
				{@const barStart = Math.max(0, moisPreavis)}
				{@const barEnd = moisFin}
				{@const preavisWidth = ((barEnd - barStart) / 12) * 100}
				{@const finPos = finDansAnnee ? ((moisFin + 0.5) / 12) * 100 : 99}
				{@const friseStyle = c.reconduit ? 'reconduit' : c.urgence}
				<div class="frise-row-v2">
					<div class="frise-row-header">
						<div class="frise-row-title">
							<strong>{c.libelle}</strong>
							<span class="text-muted-sm">{c.prestataireNom}</span>
							<span class="text-muted-sm">· {equipLabel(c.type_equipement)}</span>
							{#if c.numero_contrat}<span class="text-muted-sm">· N° {c.numero_contrat}</span>{/if}
							{#if c.noteMoy != null}
								<span class="frise-stars" class:frise-stars-bad={c.noteMoy < 3} class:frise-stars-ok={c.noteMoy >= 3 && c.noteMoy < 4} class:frise-stars-good={c.noteMoy >= 4} title="{c.noteMoy}/5 ({c.nbNotations} avis)">{starsDisplay(c.noteMoy)} {c.noteMoy}</span>
							{/if}
						</div>
						<div class="frise-row-badges">
							{#if c.urgence === 'preavis'}<span class="badge badge-orange">Préavis en cours</span>
							{:else}<span class="badge badge-blue">Actif</span>
							{/if}
							{#if c.reconduit}<span class="badge badge-purple">♻ Reconduit</span>{/if}
							<span class="frise-row-dates">
								{fmtDate(c.date_debut)} → {fmtDate(c.dateFin.toISOString())}
								{#if c.datePreavis}· préavis dès {fmtDate(c.datePreavis.toISOString())}{/if}
							</span>
						</div>
					</div>
					<div class="frise-bar-track">
						{#if preavisWidth > 0}
							<div class="frise-preavis-zone frise-urgence-{friseStyle}" style="left:{(barStart/12)*100}%;width:{preavisWidth}%"></div>
						{/if}
						{#if finDansAnnee}
							<div class="frise-marker frise-marker-{friseStyle}" style="left:{finPos}%" title="Fin : {fmtDate(c.dateFin.toISOString())}">
								<span class="frise-marker-label">{c.dateFin.getDate()}/{c.dateFin.getMonth()+1}</span>
							</div>
						{:else}
							<div class="frise-marker frise-marker-{friseStyle}" style="left:98%;opacity:.7" title="Fin : {fmtDate(c.dateFin.toISOString())} ({c.dateFin.getFullYear()})">
								<span class="frise-marker-label">→ {c.dateFin.getFullYear()}</span>
							</div>
						{/if}
					</div>
				</div>
			{/each}
			<div class="frise-legend">
				<span><span class="frise-legend-dot" style="background:#dc2626"></span> Préavis en cours</span>
				<span><span class="frise-legend-dot" style="background:#f59e0b"></span> Expire cette année</span>
				<span><span class="frise-legend-dot" style="background:#8b5cf6"></span> Reconduit tacitement</span>
				<span class="frise-legend-hatch">▧ Zone de préavis</span>
				<span style="font-size:.75rem;color:var(--color-text-muted)">→ Fin en {ANNEE_COURANTE + 1}</span>
			</div>
		</div>
	{/if}

	<!-- Contrats futurs (hors exercice courant) -->
	{#if contratsFuturs.length > 0}
		<div style="margin-top:1.2rem">
			<h4 style="font-size:.9rem;font-weight:600;margin:0 0 .5rem;color:var(--color-text-muted)">📅 Échéances futures ({contratsFuturs.length})</h4>
			<div class="frise-compact-list">
				{#each contratsFuturs as c (c.id)}
					<div class="frise-compact-item">
						<div class="frise-compact-info">
							<strong>{c.libelle}</strong>
							<span class="text-muted-sm">{c.prestataireNom} · {equipLabel(c.type_equipement)}</span>
						</div>
						<div class="frise-compact-meta">
							{#if c.noteMoy != null}<span class="frise-stars" class:frise-stars-bad={c.noteMoy < 3} class:frise-stars-ok={c.noteMoy >= 3 && c.noteMoy < 4} class:frise-stars-good={c.noteMoy >= 4}>{starsDisplay(c.noteMoy)} {c.noteMoy}</span>{/if}
							<span>Fin : {c.dateFin ? fmtDate(c.dateFin.toISOString()) : 'N/A'}</span>
							<span>Préavis : {c.datePreavis ? fmtDate(c.datePreavis.toISOString()) : 'N/A'}</span>
							{#if c.reconduit}<span class="badge badge-purple">♻ Reconduit</span>{/if}
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Contrats sans dates -->
	{#if contratsInconnus.length > 0}
		<div style="margin-top:1.2rem">
			<h4 style="font-size:.9rem;font-weight:600;margin:0 0 .5rem;color:var(--color-text-muted)">⚠️ Dates manquantes ({contratsInconnus.length})</h4>
			<div class="frise-compact-list">
				{#each contratsInconnus as c (c.id)}
					<div class="frise-compact-item">
						<div class="frise-compact-info">
							<strong>{c.libelle}</strong>
							<span class="text-muted-sm">{c.prestataireNom} · {equipLabel(c.type_equipement)}{#if c.numero_contrat} · N° {c.numero_contrat}{/if}</span>
						</div>
						<div class="frise-compact-meta">
							{#if c.noteMoy != null}<span class="frise-stars" class:frise-stars-bad={c.noteMoy < 3} class:frise-stars-ok={c.noteMoy >= 3 && c.noteMoy < 4} class:frise-stars-good={c.noteMoy >= 4}>{starsDisplay(c.noteMoy)} {c.noteMoy}</span>{/if}
							<span>Début : {c.date_debut ? fmtDate(c.date_debut) : 'N/A'}</span>
							<span class="badge badge-gray">Durée non renseignée</span>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</section>

<!-- Section 2 : Diagnostics et Contrôles Réglementaires -->
<section class="report-card">
	<h3>🔍 Diagnostics et Contrôles Réglementaires — {ANNEE_COURANTE}–{ANNEE_COURANTE + 10}</h3>
	<p class="report-intro">Échéances issues de Résidence / Diagnostics et Contrôles Réglementaires, calculées depuis le dernier rapport + fréquence légale.</p>

	{#if diagsAvecNext.length === 0}
		<div class="empty-state"><h3>Aucun diagnostic applicable</h3><p>Tous les diagnostics sont non applicables.</p></div>
	{:else}
		<!-- Grille par année -->
		{#each diagsParAnnee as [annee, diags]}
			<div class="audit-year-group" class:audit-year-current={annee === ANNEE_COURANTE}>
				<h4 class="audit-year-title">
					{annee}
					<span class="badge {annee === ANNEE_COURANTE ? 'badge-orange' : 'badge-blue'}">{diags.length} audit{diags.length > 1 ? 's' : ''}</span>
				</h4>
				<div class="report-table-wrap">
					<table class="report-table compact">
						<thead>
							<tr><th>Diagnostic</th><th>Code</th><th>Fréquence</th><th>Dernier rapport</th><th>Prochaine échéance</th><th>Statut</th></tr>
						</thead>
						<tbody>
							{#each diags as d (d.id)}
								<tr>
									<td><strong>{d.nom}</strong></td>
									<td>{d.code}</td>
									<td>{d.frequence ?? 'N/A'}</td>
									<td>{d.lastRapportDate ? fmtDate(d.lastRapportDate) : 'N/A'}</td>
									<td>{d.nextDate ? fmtDate(d.nextDate.toISOString()) : 'N/A'}</td>
									<td>
										{#if d.urgence === 'depasse'}<span class="badge badge-red">Dépassé</span>
										{:else if d.urgence === 'annee'}<span class="badge badge-orange">À faire en {ANNEE_COURANTE}</span>
										{:else}<span class="badge badge-blue">{annee}</span>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/each}

		<!-- Diagnostics permanents -->
		{#if diagsPermanents.length > 0}
			<div class="audit-year-group" style="margin-top:1rem">
				<h4 class="audit-year-title">
					Permanent
					<span class="badge badge-blue">{diagsPermanents.length}</span>
				</h4>
				<p class="report-intro">Diagnostics à validité permanente (sauf si révision nécessaire).</p>
				<div class="report-table-wrap">
					<table class="report-table compact">
						<thead>
							<tr><th>Diagnostic</th><th>Code</th><th>Fréquence</th><th>Dernier rapport</th><th>Statut</th></tr>
						</thead>
						<tbody>
							{#each diagsPermanents as d (d.id)}
								<tr>
									<td><strong>{d.nom}</strong></td>
									<td>{d.code}</td>
									<td>{d.frequence ?? 'N/A'}</td>
									<td>{d.lastRapportDate ? fmtDate(d.lastRapportDate) : 'N/A'}</td>
									<td><span class="badge badge-green">✓ Permanent</span></td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		<!-- Diagnostics sans échéance calculable -->
		{#if diagsSansEcheance.length > 0}
			<div class="audit-year-group" style="margin-top:1rem">
				<h4 class="audit-year-title">
					Sans échéance calculable
					<span class="badge badge-gray">{diagsSansEcheance.length}</span>
				</h4>
				<p class="report-intro">Diagnostics sans rapport initial ou sans fréquence définie.</p>
				<div class="report-table-wrap">
					<table class="report-table compact">
						<thead>
							<tr><th>Diagnostic</th><th>Code</th><th>Fréquence</th><th>Dernier rapport</th><th>Statut</th></tr>
						</thead>
						<tbody>
							{#each diagsSansEcheance as d (d.id)}
								<tr>
									<td><strong>{d.nom}</strong></td>
									<td>{d.code}</td>
									<td>{d.frequence ?? 'N/A'}</td>
									<td>{d.lastRapportDate ? fmtDate(d.lastRapportDate) : 'N/A'}</td>
									<td>
										{#if d.rapports.length === 0}<span class="badge badge-gray">Aucun rapport</span>
										{:else}<span class="badge badge-gray">À planifier</span>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	{/if}
</section>

<style>
	/* ── Renouvellements : frise contrats ─────────────────────────── */
	.frise-container { margin-top: .5rem; }
	.frise-months {
		display: grid; grid-template-columns: repeat(12, 1fr);
		font-size: .7rem; color: var(--color-text-muted); text-transform: uppercase;
		letter-spacing: .03em; margin-bottom: .35rem; text-align: center;
		border-bottom: 1px solid var(--color-border); padding-bottom: .3rem;
	}
	.frise-row-v2 {
		padding: .5rem 0 1.2rem;
		border-bottom: 1px solid color-mix(in srgb, var(--color-border) 50%, transparent);
	}
	.frise-row-header {
		display: flex; justify-content: space-between; align-items: baseline;
		flex-wrap: wrap; gap: .15rem .8rem; margin-bottom: .3rem;
	}
	.frise-row-title {
		display: flex; align-items: baseline; gap: .4rem; font-size: .82rem;
		min-width: 0; flex-wrap: wrap;
	}
	.frise-row-badges {
		display: flex; align-items: center; gap: .4rem; flex-wrap: wrap;
	}
	.frise-row-dates {
		font-size: .72rem; color: var(--color-text-muted); white-space: nowrap;
	}
	.frise-bar-track {
		position: relative; height: 28px;
		background: repeating-linear-gradient(
			90deg,
			transparent, transparent calc(100% / 12 - 1px),
			var(--color-border) calc(100% / 12 - 1px), var(--color-border) calc(100% / 12)
		);
		border-radius: 4px;
	}

	/* Compact list for future/unknown contracts */
	.frise-compact-list { display: flex; flex-direction: column; gap: .4rem; }
	.frise-compact-item {
		display: flex; justify-content: space-between; align-items: center;
		gap: .5rem; padding: .4rem .6rem; border-radius: 6px; font-size: .82rem;
		background: color-mix(in srgb, var(--color-bg-card) 90%, var(--color-border));
		flex-wrap: wrap;
	}
	.frise-compact-info { display: flex; align-items: baseline; gap: .4rem; min-width: 0; flex-wrap: wrap; }
	.frise-compact-meta { display: flex; align-items: center; gap: .6rem; font-size: .75rem; color: var(--color-text-muted); flex-wrap: wrap; }

	/* Stars rating display */
	.frise-stars {
		font-size: .78rem; white-space: nowrap; letter-spacing: -.02em;
	}
	.frise-stars-bad { color: #dc2626; }
	.frise-stars-ok { color: #f59e0b; }
	.frise-stars-good { color: #16a34a; }
	.frise-preavis-zone {
		position: absolute; top: 2px; bottom: 2px; border-radius: 3px; opacity: .35;
		background: repeating-linear-gradient(
			-45deg, transparent, transparent 4px, currentColor 4px, currentColor 6px
		);
	}
	.frise-preavis-zone.frise-urgence-expire,
	.frise-preavis-zone.frise-urgence-preavis { color: #dc2626; }
	.frise-preavis-zone.frise-urgence-annee { color: #f59e0b; }
	.frise-preavis-zone.frise-urgence-futur { color: #3b82f6; }
	.frise-preavis-zone.frise-urgence-reconduit { color: #8b5cf6; }

	.frise-marker {
		position: absolute; top: 0; bottom: 0; width: 3px; transform: translateX(-50%);
		border-radius: 2px;
	}
	.frise-marker-expire, .frise-marker-preavis { background: #dc2626; }
	.frise-marker-annee { background: #f59e0b; }
	.frise-marker-futur { background: #3b82f6; }
	.frise-marker-reconduit { background: #8b5cf6; }

	.frise-marker-label {
		position: absolute; bottom: -16px; left: 50%; transform: translateX(-50%);
		font-size: .65rem; color: var(--color-text-muted); white-space: nowrap;
	}
	.frise-legend {
		display: flex; gap: 1.2rem; font-size: .78rem; color: var(--color-text-muted);
		margin-top: 1.2rem; flex-wrap: wrap;
	}
	.frise-legend span { display: flex; align-items: center; gap: .35rem; }
	.frise-legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 2px; }
	.frise-legend-hatch { font-style: italic; }

	/* ── Renouvellements : audits par année ───────────────────────── */
	.audit-year-group { margin-bottom: 1.2rem; }
	.audit-year-group:last-child { margin-bottom: 0; }
	.audit-year-title {
		font-size: .95rem; font-weight: 700; margin: 0 0 .5rem;
		display: flex; align-items: center; gap: .5rem;
	}
	.audit-year-current { border-left: 3px solid #f59e0b; padding-left: .75rem; }

	@media (max-width: 700px) {
		.frise-row-header { flex-direction: column; }
		.frise-bar-track { min-height: 24px; }
		.frise-months { font-size: .6rem; }
		.frise-compact-item { flex-direction: column; align-items: flex-start; }
	}

	@media print {
		.frise-container { break-inside: auto; }
		.frise-row-v2 { break-inside: avoid; }
		.audit-year-group { break-inside: auto; }
		.audit-year-title { break-after: avoid; }
		.report-table { break-inside: auto; }
		.report-table tr { break-inside: avoid; }
	}
</style>
