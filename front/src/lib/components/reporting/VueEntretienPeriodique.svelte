<!--
  Reporting CS — **entretien périodique** : chaque visite de l'année civile, et
  si elle a eu lieu (arbitré le 10/10/2026).

  Ces visites — une affaire Entretien sous contrat ou à récurrence, une par
  passage prévu — ont quitté la relance syndic : le passage d'un prestataire ne se
  relance pas auprès du syndic, il se constate ici. L'état de chaque visite est
  CALCULÉ au serveur (`utils/entretien_periodique`) ; cette vue ne fait que le
  nommer.

  Autonome comme la relance : elle charge ses données et rend compte à la barre
  d'outils du parent (`chargement`, `estVide`, `recharger`).
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { messageErreur } from '$lib/erreurs';
	import { tickets as ticketsApi, type EtatVisite, type VisitePeriodique } from '$lib/api';
	import { fmtDate } from '$lib/date';
	import { lienTicket } from '$lib/tickets';
	import EtatListe from '$lib/components/EtatListe.svelte';

	/** Le nom de chaque état, et sa teinte. L'ordre est celui des compteurs. */
	const ETATS: Record<EtatVisite, { libelle: string; badge: string }> = {
		realisee: { libelle: '✅ Réalisée', badge: 'badge-green' },
		non_realisee: { libelle: '⚠️ Non réalisée', badge: 'badge-red' },
		a_venir: { libelle: '⏳ À venir', badge: 'badge-blue' },
		a_planifier: { libelle: '📅 À planifier', badge: 'badge-orange' },
		annulee: { libelle: 'Annulée', badge: 'badge-gray' },
	};
	/** Les compteurs : « Annulée » n'en a pas, elle ne dit rien d'un entretien fait. */
	const COMPTEURS: { etat: EtatVisite; libelle: string }[] = [
		{ etat: 'realisee', libelle: 'Réalisées' },
		{ etat: 'non_realisee', libelle: 'Non réalisées' },
		{ etat: 'a_venir', libelle: 'À venir' },
		{ etat: 'a_planifier', libelle: 'À planifier' },
	];

	let visites: VisitePeriodique[] = [];
	let exercice = new Date().getFullYear();
	let enCours = false;
	let charge = false;
	let erreur = '';

	/** Lu par la barre d'outils du parent — ne pas écrire depuis l'extérieur. */
	export let chargement = false;
	/** Idem : « rien à imprimer » se décide ici. */
	export let estVide = true;
	$: chargement = enCours;
	$: estVide = visites.length === 0;

	$: nombre = (etat: EtatVisite) => visites.filter((v) => v.etat === etat).length;

	async function charger(force = false) {
		if (charge && !force) return;
		enCours = true;
		erreur = '';
		try {
			const r = await ticketsApi.entretiensPeriodiques();
			[exercice, visites] = [r.exercice, r.visites];
			charge = true;
		} catch (e) {
			erreur = messageErreur(e, 'Chargement impossible');
		} finally {
			enCours = false;
		}
	}

	/** Rechargement demandé par la barre d'outils du parent. */
	export function recharger() {
		charger(true);
	}

	onMount(() => charger());
</script>

{#if enCours || erreur || visites.length === 0}
	<EtatListe
		chargement={enCours}
		{erreur}
		vide={visites.length === 0}
		titreErreur="Impossible d’afficher l’entretien périodique"
		titreVide="Aucune visite d’entretien périodique en {exercice}"
		messageVide="Une visite est une affaire Entretien sous contrat ou à récurrence : « ⚙️ Init. prestataires » les pose pour l'année."
	/>
{:else}
	<section class="report-card">
		<h3>🧰 Entretien périodique — {exercice}</h3>
		<p class="report-intro">
			{visites.length} visite(s) prévue(s) cette année. Une visite est réalisée quand son affaire est
			résolue ; elle est non réalisée quand sa date est passée sans l'être.
		</p>

		<div class="kpi-row compteurs">
			{#each COMPTEURS as c (c.etat)}
				<div class="kpi-card" class:kpi-alert={c.etat === 'non_realisee' && nombre(c.etat) > 0}>
					<div class="kpi-value">{nombre(c.etat)}</div>
					<div class="kpi-label">{c.libelle}</div>
				</div>
			{/each}
		</div>

		<div class="report-table-wrap">
			<table class="report-table compact">
				<thead>
					<tr><th>Date prévue</th><th>Affaire</th><th>Prestataire</th><th>État</th></tr>
				</thead>
				<tbody>
					{#each visites as v (v.id)}
						<tr>
							<td class="date">{fmtDate(v.debut)}</td>
							<td>
								<a href={lienTicket(v.id)} class="affaire">
									<span class="numero">{v.numero}</span>
									{v.titre}
								</a>
							</td>
							<td>
								{v.prestataire_nom ?? '—'}
								{#if v.contrat_libelle}<span class="contrat">{v.contrat_libelle}</span>{/if}
							</td>
							<td>
								<span class="badge {ETATS[v.etat].badge}">{ETATS[v.etat].libelle}</span>
								{#if v.etat === 'realisee' && v.ferme_le}
									<span class="contrat">le {fmtDate(v.ferme_le)}</span>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
{/if}

<style>
	.compteurs {
		margin-bottom: 1rem;
	}
	.date {
		white-space: nowrap;
	}
	.affaire {
		color: inherit;
		text-decoration: none;
	}
	.numero {
		font-weight: 700;
		color: var(--color-primary);
		margin-right: 0.35rem;
		white-space: nowrap;
	}
	.contrat {
		display: block;
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	@media (hover: hover) and (pointer: fine) {
		.affaire:hover {
			color: var(--color-primary);
		}
	}
</style>
