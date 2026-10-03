<!--
  L'onglet **Télémétrie** de l'administration : qui utilise quoi, et quand.

  POURQUOI CE COMPOSANT (19/08/2026). Les sept écrans d'administration qui
  vivaient sur leur propre route sont devenus des onglets — pour qu'on n'en sorte
  plus, donc sans bouton « ← Retour ». Leur aiguillage ajoutait 53 lignes à
  `admin/+page.svelte`, déjà à 1 786, et le garde-fou de modularité (rang 1) l'a
  refusé. Troisième extraction du même patron, après `OngletWhatsApp` et `OngletSmtp`.

  ## Quatre vues, cinq sections, un filtre (03/10/2026)

  - **Vues** : Jour · Mois (30 j) · Année (12 derniers mois) · Total (par année,
    10 ans). « Année (10 ans) » est devenue Total ; Année lit douze mois.
  - **Sections pliables**, un seul dépliée à la fois — l'accordéon natif des
    `<details>` (`$lib/accordeon`, posé par le layout) replie les autres et
    ramène le haut de la section ouverte à l'écran. L'état vit ICI
    (`sectionOuverte`), comme dans `OngletIA` : il survit au changement de vue,
    qui recharge tout. À l'arrivée : **Fréquentation** (graphe, top pages,
    utilisateurs actifs). Une section VIDE ne se déplie pas (`PanneauTelemetrie`).
  - **« Qui vient » suit la vue** : aujourd'hui, 30 jours, 12 mois ; en Total,
    personne ne sait plus qui est venu, la section est vide.
  - **Filtre « avec / sans gestionnaire du site »** : proposé par le serveur
    seulement s'il changerait quelque chose (`filtre_gestionnaire.propose`) ;
    « avec » à l'ouverture. Les erreurs et les durées, sans compte, ne bougent pas.
-->
<script lang="ts">
	import { admin as adminApi } from '$lib/api';
	import type { FiltreGestionnaire, PorteeTelemetrie, TableauTelemetrie } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { fmtDate } from '$lib/date';
	import Icon from '$lib/components/Icon.svelte';
	import PanneauTelemetrie from '$lib/components/PanneauTelemetrie.svelte';
	import FrequentationTelemetrie from '$lib/components/FrequentationTelemetrie.svelte';
	import ErreursNavigateur from '$lib/components/ErreursNavigateur.svelte';
	import DureesAffichage from '$lib/components/DureesAffichage.svelte';
	import QuiVient from '$lib/components/QuiVient.svelte';
	import Pastille from '$lib/components/Pastille.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';

	let telemetryData: TableauTelemetrie | null = null;
	let telemetryLoading = true;
	/**  🔴 Non vide = on n'a PAS pu regarder (#816).
	 *
	 *   Le `catch` de cette fonction faisait `telemetryData = null` : une session
	 *   expirée, un 500 ou une coupure réseau produisaient EXACTEMENT l'écran
	 *   d'une résidence que personne ne consulte — « Les données apparaîtront
	 *   après les premières visites ». C'est le `.catch(() => [])` de #519 mot
	 *   pour mot, sur le seul écran qui sert à savoir si le site est lu. */
	let telemetryErreur = '';
	let tlScope: PorteeTelemetrie = 'jour';
	let filtre: FiltreGestionnaire = 'avec';

	const VUES: { code: PorteeTelemetrie; libelle: string }[] = [
		{ code: 'jour', libelle: 'Jour' },
		{ code: 'mois', libelle: 'Mois (30 j)' },
		{ code: 'annee', libelle: 'Année (12 mois)' },
		{ code: 'total', libelle: 'Total (10 ans)' },
	];
	/** Ce que couvrent les panneaux tirés du détail (erreurs, durées) : le jour
	 *  même, sinon leurs 30 jours de conservation — l'année n'en a pas plus. */
	$: periodeDetail = tlScope === 'jour' ? 'aujourd’hui' : '30 derniers jours';
	$: libelleVues =
		tlScope === 'jour'
			? "Pages vues aujourd'hui"
			: tlScope === 'mois'
				? 'Pages vues (30 j)'
				: tlScope === 'annee'
					? 'Pages vues (12 mois)'
					: 'Pages vues (total)';

	//  L'ACCORDÉON : une section dépliée à la fois, l'état tenu ici (cf. OngletIA).
	//  « frequentation » à l'arrivée : c'est ce qu'on vient lire le plus souvent.
	type Section = 'indicateurs' | 'frequentation' | 'erreurs' | 'qui-vient' | 'durees';
	let sectionOuverte: Section | null = 'frequentation';
	function basculerSection(code: Section, ouvert: boolean) {
		if (ouvert) sectionOuverte = code;
		else if (sectionOuverte === code) sectionOuverte = null;
	}

	export async function loadTelemetry() {
		telemetryLoading = true;
		telemetryErreur = '';
		try {
			telemetryData = await adminApi.telemetryDashboard(tlScope, filtre);
			//  Le serveur peut avoir appliqué « avec » à un « sans » qui ne
			//  changerait rien : les pastilles disent ce qui est APPLIQUÉ.
			filtre = telemetryData.filtre_gestionnaire.applique;
		} catch (e: any) {
			//  La donnée précédente est écartée : l'afficher sous un onglet dont
			//  la portée vient de changer la ferait passer pour la nouvelle.
			telemetryData = null;
			telemetryErreur = messageErreur(e, 'Statistiques indisponibles pour le moment.');
		} finally {
			telemetryLoading = false;
		}
	}

	function switchTlScope(s: PorteeTelemetrie) {
		tlScope = s;
		loadTelemetry();
	}

	function switchFiltre(f: FiltreGestionnaire) {
		filtre = f;
		loadTelemetry();
	}

	//  Les indicateurs chiffrés rendus : la section est vide quand il n'y a rien à
	//  compter — zéro vue, c'est « personne n'est venu », pas un indicateur.
	$: indicateursVides = !telemetryData || (telemetryData.kpi.vues ?? 0) === 0;

	//  L'onglet ne se rend que lorsqu'il est choisi : charger au montage suffit, et
	//  évite à la page d'avoir à déclencher l'appel depuis son bouton.
	loadTelemetry();
</script>

<section class="card config-section">
	<h2 class="config-section-title">
		<Icon name="bar-chart-3" size={17} />Télémétrie — Utilisation de l'application
	</h2>
	<p class="aide">Statistiques d'utilisation : qui utilise quoi et quand.</p>

	<!-- Sélecteur de vue : Jour / Mois / Année / Total -->
	<div class="tl-scope-switch">
		{#each VUES as v (v.code)}
			<Pastille active={tlScope === v.code} on:click={() => switchTlScope(v.code)}
				>{v.libelle}</Pastille
			>
		{/each}
	</div>

	<!--  Le filtre, seulement si le serveur dit qu'il changerait quelque chose :
	      un gestionnaire désigné, qui a des vues sur la vue consultée, et d'autres
	      que lui aussi. -->
	{#if telemetryData?.filtre_gestionnaire.propose}
		<div class="tl-scope-switch tl-filtre">
			<Pastille petite active={filtre === 'avec'} on:click={() => switchFiltre('avec')}
				>Avec le gestionnaire du site</Pastille
			>
			<Pastille petite active={filtre === 'sans'} on:click={() => switchFiltre('sans')}
				>Sans le gestionnaire du site</Pastille
			>
		</div>
		{#if filtre === 'sans'}
			<p class="aide">
				Les vues du gestionnaire du site sont écartées des indicateurs, du graphe, des pages, des
				utilisateurs et de « Qui vient ». Les erreurs et les durées d’affichage, sans compte, ne
				changent pas.
				{#if telemetryData.filtre_gestionnaire.non_distingue_jusqu_au}
					Jusqu’au {fmtDate(telemetryData.filtre_gestionnaire.non_distingue_jusqu_au)}, les agrégats
					ne distinguaient pas le gestionnaire : ses vues y restent comptées.
				{/if}
			</p>
		{/if}
	{/if}

	<EtatListe
		chargement={telemetryLoading}
		erreur={telemetryErreur}
		vide={!telemetryData}
		messageChargement="Chargement des statistiques…"
		titreErreur="Impossible d’afficher les statistiques"
		titreVide="Aucune donnée de télémétrie"
		messageVide="Les données apparaîtront après les premières visites."
	>
		{#if telemetryData}
			{@const kpi = telemetryData.kpi}
			<PanneauTelemetrie
				titre="📊 Indicateurs"
				ouvert={sectionOuverte === 'indicateurs'}
				vide={indicateursVides}
				videLibelle="aucune vue sur la période"
				on:basculer={(e) => basculerSection('indicateurs', e.detail)}
			>
				<div class="tl-kpi-row">
					<div class="tl-kpi">
						<div class="tl-kpi-value">{kpi.vues ?? 0}</div>
						<div class="tl-kpi-label">{libelleVues}</div>
					</div>
					{#if kpi.utilisateurs != null}
						<div class="tl-kpi">
							<div class="tl-kpi-value">{kpi.utilisateurs}</div>
							<div class="tl-kpi-label">
								{tlScope === 'jour'
									? "Utilisateurs actifs aujourd'hui"
									: 'Utilisateurs uniques (pic)'}
							</div>
						</div>
					{/if}
					<div class="tl-kpi">
						<div class="tl-kpi-value">{kpi.pages ?? 0}</div>
						<div class="tl-kpi-label">Pages distinctes visitées</div>
					</div>
					{#if kpi.heure_pointe}
						<div class="tl-kpi">
							<div class="tl-kpi-value">{kpi.heure_pointe}</div>
							<div class="tl-kpi-label">🔺 Heure de pointe</div>
						</div>
					{/if}
					{#if kpi.moy_vues_utilisateur != null}
						<div class="tl-kpi">
							<div class="tl-kpi-value">{kpi.moy_vues_utilisateur}</div>
							<div class="tl-kpi-label">Moy. vues / utilisateur</div>
						</div>
					{/if}
					{#if kpi.moy_vues_jour != null}
						<div class="tl-kpi">
							<div class="tl-kpi-value">{kpi.moy_vues_jour}</div>
							<div class="tl-kpi-label">Moy. vues / jour</div>
						</div>
					{/if}
					{#if kpi.moy_utilisateurs_jour != null}
						<div class="tl-kpi">
							<div class="tl-kpi-value">{kpi.moy_utilisateurs_jour}</div>
							<div class="tl-kpi-label">Moy. utilisateurs / jour</div>
						</div>
					{/if}
					{#if kpi.mois_actifs != null}
						<div class="tl-kpi">
							<div class="tl-kpi-value">{kpi.mois_actifs}</div>
							<div class="tl-kpi-label">Mois avec activité</div>
						</div>
					{/if}
					{#if kpi.moy_vues_mois != null}
						<div class="tl-kpi">
							<div class="tl-kpi-value">{kpi.moy_vues_mois}</div>
							<div class="tl-kpi-label">Moy. vues / mois</div>
						</div>
					{/if}
					{#if kpi.annees_actives != null}
						<div class="tl-kpi">
							<div class="tl-kpi-value">{kpi.annees_actives}</div>
							<div class="tl-kpi-label">Années avec activité</div>
						</div>
					{/if}
					{#if kpi.moy_vues_an != null}
						<div class="tl-kpi">
							<div class="tl-kpi-value">{kpi.moy_vues_an}</div>
							<div class="tl-kpi-label">Moy. vues / an</div>
						</div>
					{/if}
				</div>

				<!-- Jour le plus actif (vue Mois) · Records (vues Année et Total) -->
				{#if kpi.jour_pointe || kpi.record_jour || kpi.record_mois}
					<div class="tl-kpi-row tl-kpi-row-suite">
						{#if kpi.jour_pointe}
							<div class="tl-kpi">
								<div class="tl-kpi-value">
									{kpi.jour_pointe.uniques}
									<span class="tl-kpi-unite">utilisateurs</span>
								</div>
								<div class="tl-kpi-label">
									🏆 Jour le plus actif — {fmtDate(kpi.jour_pointe.jour)}
								</div>
							</div>
						{/if}
						{#if kpi.record_jour}
							<div class="tl-kpi">
								<div class="tl-kpi-value">
									{kpi.record_jour.uniques}
									<span class="tl-kpi-unite">utilisateurs</span>
								</div>
								<div class="tl-kpi-label">🏆 Record jour — {fmtDate(kpi.record_jour.jour)}</div>
							</div>
						{/if}
						{#if kpi.record_mois}
							<div class="tl-kpi">
								<div class="tl-kpi-value">
									{kpi.record_mois.uniques}
									<span class="tl-kpi-unite">utilisateurs</span>
								</div>
								<div class="tl-kpi-label">🏆 Record mois — {kpi.record_mois.mois}</div>
							</div>
						{/if}
					</div>
				{/if}
			</PanneauTelemetrie>

			<FrequentationTelemetrie
				donnees={telemetryData}
				ouvert={sectionOuverte === 'frequentation'}
				on:basculer={(e) => basculerSection('frequentation', e.detail)}
			/>
			<ErreursNavigateur
				erreurs={telemetryData.erreurs}
				periode={periodeDetail}
				ouvert={sectionOuverte === 'erreurs'}
				on:basculer={(e) => basculerSection('erreurs', e.detail)}
			/>
			<QuiVient
				adoption={telemetryData.adoption}
				ouvert={sectionOuverte === 'qui-vient'}
				on:basculer={(e) => basculerSection('qui-vient', e.detail)}
			/>
			<DureesAffichage
				durees={telemetryData.performance}
				periode={periodeDetail}
				ouvert={sectionOuverte === 'durees'}
				on:basculer={(e) => basculerSection('durees', e.detail)}
			/>
		{/if}
	</EtatListe>
</section>

<style>
	/*  Les règles des indicateurs voyagent avec leur balisage (v2.95.0 : le
	    panneau est parti NU en production quand elles étaient restées dans la
	    page — `npm run lint:classes-nues` est né de là). Le graphe et les siennes
	    sont dans `FrequentationTelemetrie`. */
	.tl-scope-switch {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin: 0.75rem 0 0;
	}
	.tl-filtre {
		margin-top: 0.5rem;
	}
	.tl-kpi-row {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(160px, 100%), 1fr));
		gap: 1rem;
		margin: 0 1rem 1rem;
	}
	.tl-kpi-row-suite {
		margin-top: 0;
	}
	.tl-kpi {
		background: var(--color-surface);
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
	.tl-kpi-unite {
		font-size: var(--fs-sm);
		font-weight: 400;
	}
	.tl-kpi-label {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin-top: 0.3rem;
	}
</style>
