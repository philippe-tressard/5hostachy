<!--
  Reporting CS — **synthèse prestataires** : le tableau des prestataires actifs,
  et la fiche détaillée de celui qu'on ouvre (notations, devis, contrats).

  Extrait d'`espace-cs/+page.svelte` avec #453. Seule vue à faire un appel réseau
  de son côté : la fiche de synthèse se charge à la demande, prestataire par
  prestataire — les charger toutes d'avance n'aurait aucun sens.
-->
<script lang="ts">
	//  ⚠️ Cet écran affichait la valeur BRUTE — `chauffage_collectif` — parce que
	//  la table des libellés vivait dans `prestataires/+page.svelte` et qu'il n'y
	//  avait pas accès. Une table qui vit dans UN écran, les autres s'en passent.
	import { equipLabel } from '$lib/prestataires';
	import { prestataires as prestApi } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { fmtDate } from '$lib/date';
	import { fmtMontant, starsDisplay } from '$lib/utils';
	import { REPORT_DEVIS_LABELS, REPORT_DEVIS_BADGES, type ReportDevis, type ReportPrestataire } from '$lib/reporting';

	export let reportPrestataires: ReportPrestataire[] = [];
	export let reportDevisList: ReportDevis[] = [];

	let reportPrestSynth: any = null;
	let reportPrestSynthLoading = false;

	async function loadPrestSynthese(prestId: number) {
		reportPrestSynthLoading = true;
		try {
			reportPrestSynth = await prestApi.synthese(prestId);
		} catch { toast('error', 'Erreur chargement synthèse'); reportPrestSynth = null; }
		finally { reportPrestSynthLoading = false; }
	}
</script>

<!-- ── Synthèse prestataires ─────────────────────────────────────────── -->
<div class="kpi-row" style="margin-bottom:1rem">
	<div class="kpi-card"><div class="kpi-value">{reportPrestataires.length}</div><div class="kpi-label">Prestataires actifs</div></div>
	<div class="kpi-card"><div class="kpi-value">{reportDevisList.filter(d => d.statut === 'realise').length}</div><div class="kpi-label">Prestations réalisées</div></div>
</div>
<div class="report-table-wrap" style="margin-bottom:1.5rem">
	<table class="report-table">
		<thead>
			<tr>
				<th>Prestataire</th>
				<th>Spécialité</th>
				<th>Type</th>
				<th>Devis actifs</th>
				<th>Réalisés</th>
				<th>Actions</th>
			</tr>
		</thead>
		<tbody>
			{#each reportPrestataires as p (p.id)}
				{@const pDevis = reportDevisList.filter(d => d.prestataire_id === p.id)}
				{@const pActifs = pDevis.filter(d => d.statut === 'en_attente' || d.statut === 'accepte').length}
				{@const pRealises = pDevis.filter(d => d.statut === 'realise').length}
				<tr>
					<td><strong>{p.nom}</strong></td>
					<td>{p.specialite ?? '—'}</td>
					<td>{p.type_prestataire ?? '—'}</td>
					<td>{pActifs}</td>
					<td>{pRealises}</td>
					<td><button class="btn btn-sm btn-outline" on:click={() => loadPrestSynthese(p.id)}>Fiche synthèse</button></td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<!-- Fiche synthèse prestataire (modale inline) -->
{#if reportPrestSynthLoading}
	<p style="color:var(--color-text-muted)">Chargement synthèse…</p>
{:else if reportPrestSynth}
	<section class="report-card" style="margin-bottom:1.5rem">
		<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem">
			<h3 style="margin:0">&#x1F4C4; Fiche — {reportPrestSynth.nom}</h3>
			<button class="btn btn-sm btn-outline" on:click={() => (reportPrestSynth = null)}>✕ Fermer</button>
		</div>
		<div class="report-grid-2" style="margin-bottom:1rem">
			<div>
				<p><strong>Spécialité :</strong> {reportPrestSynth.specialite}</p>
				<p><strong>Type :</strong> {reportPrestSynth.type_prestataire}</p>
				{#if reportPrestSynth.email}<p><strong>Email :</strong> {reportPrestSynth.email}</p>{/if}
				{#if reportPrestSynth.contacts && reportPrestSynth.contacts.length > 0}
					<p><strong>Contacts :</strong></p>
					{#each reportPrestSynth.contacts as c}
						<p style="margin-left:1rem">📞 {c.telephone ?? '—'}{#if c.prenom || c.nom} — {c.prenom ?? ''} {c.nom ?? ''}{/if}{#if c.fonction} ({c.fonction}){/if}{#if c.email} · {c.email}{/if}</p>
					{/each}
				{/if}
			</div>
			<div>
				<p><strong>Contrats actifs :</strong> {reportPrestSynth.nb_contrats}</p>
				<p><strong>Devis / prestations :</strong> {reportPrestSynth.nb_devis}</p>
				<p><strong>Note moyenne :</strong> {reportPrestSynth.note_moyenne != null ? `${starsDisplay(reportPrestSynth.note_moyenne)} ${reportPrestSynth.note_moyenne}/5 (${reportPrestSynth.nb_notations} avis)` : 'Aucune notation'}</p>
				{#if reportPrestSynth.prochaines_visites && reportPrestSynth.prochaines_visites.length > 0}
					<p><strong>Prochaines visites :</strong></p>
					{#each reportPrestSynth.prochaines_visites as v}
						<p style="margin-left:1rem">📅 {fmtDate(v.date)} — {v.contrat}</p>
					{/each}
				{/if}
			</div>
		</div>
		{#if reportPrestSynth.notations && reportPrestSynth.notations.length > 0}
			<h4 style="font-size:.9rem;font-weight:600;margin:1rem 0 .5rem">Historique des notations</h4>
			<div class="report-table-wrap">
				<table class="report-table compact">
					<thead><tr><th>Date</th><th>Note</th><th>Commentaire</th><th>Par</th></tr></thead>
					<tbody>
						{#each reportPrestSynth.notations as n}
							<tr>
								<td>{fmtDate(n.cree_le)}</td>
								<td style="color:#f59e0b">{starsDisplay(n.note)} {n.note}/5</td>
								<td>{n.commentaire ?? '—'}</td>
								<td>{n.auteur_nom}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
		{#if reportPrestSynth.devis && reportPrestSynth.devis.length > 0}
			<h4 style="font-size:.9rem;font-weight:600;margin:1rem 0 .5rem">Devis & prestations</h4>
			<div class="report-table-wrap">
				<table class="report-table compact">
					<thead><tr><th>Objet</th><th>Statut</th><th>Date</th><th>Montant</th></tr></thead>
					<tbody>
						{#each reportPrestSynth.devis as d}
							<tr>
								<td>{d.titre}</td>
								<td><span class="badge {REPORT_DEVIS_BADGES[d.statut] ?? 'badge-gray'}">{REPORT_DEVIS_LABELS[d.statut] ?? d.statut}</span></td>
								<td>{d.date_prestation ? fmtDate(d.date_prestation) : '—'}</td>
								<td>{fmtMontant(d.montant_estime)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
		{#if reportPrestSynth.contrats && reportPrestSynth.contrats.length > 0}
			<h4 style="font-size:.9rem;font-weight:600;margin:1rem 0 .5rem">Contrats</h4>
			<div class="report-table-wrap">
				<table class="report-table compact">
					<thead><tr><th>Libellé</th><th>Équipement</th><th>Début</th><th>Prochaine visite</th></tr></thead>
					<tbody>
						{#each reportPrestSynth.contrats as c}
							<tr>
								<td>{c.libelle}</td>
								<td>{equipLabel(c.type_equipement)}</td>
								<td>{fmtDate(c.date_debut)}</td>
								<td>{c.prochaine_visite ? fmtDate(c.prochaine_visite) : '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>
{/if}
