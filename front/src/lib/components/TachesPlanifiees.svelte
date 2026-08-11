<script lang="ts">
	//  Extrait de `admin/+page.svelte` (2577 lignes) le 11/08/2026, au fil de
	//  l'eau : y ajouter la colonne « Tâche » aurait fait grossir un fichier déjà
	//  cinq fois au-dessus du plafond de modularité.
	//
	//  Les deux tableaux vivent ensemble parce qu'ils décrivent le MÊME fait sous
	//  deux angles — ce qui aurait dû arriver, et ce qui est arrivé. Les séparer
	//  est précisément ce qui a rendu l'écran illisible : « Maintenance
	//  hebdomadaire : jamais exécutée » au-dessus d'un tableau qui semblait
	//  montrer des maintenances quotidiennes réussies.
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { fmtDatetime } from '$lib/date';
	import { toast } from '$lib/components/Toast.svelte';
	import { LIBELLE_TACHE } from '$lib/taches';

	let sante: { taches: any[]; anomalies_recentes: any[] } | null = null;
	let santeLoading = true;
	let executions: any[] = [];
	let executionsLoading = true;
	let enCours = false;

	//  Le tableau des exécutions filtrait sur RIEN : il affichait toutes les
	//  tâches de `historique_maintenance` — bascules et copies hors site
	//  comprises — sous un titre qui annonce des maintenances, et sans colonne
	//  pour les distinguer. D'où des lignes « 02:00 » quotidiennes en face d'une
	//  tâche hebdomadaire déclarée jamais exécutée, et des colonnes Taille DB et
	//  Détail vides : une bascule n'a ni l'une ni l'autre à déclarer.
	//  Signalé par l'utilisateur le 11/08/2026, par aucun contrôle.
	//
	//  Les libellés eux-mêmes vivent dans `$lib/taches.ts` : ils servent AUSSI aux
	//  titres des cartes de détail, qui sont dans un autre fichier. Les redéfinir
	//  ici est précisément ce qui les avait fait diverger.

	//  « Jamais exécutée » affirmait plus que ce que le contrôle mesure : il
	//  observe l'absence de RAPPORT en base, pas l'absence d'exécution. Les deux
	//  ont été confondus le 09/08/2026, la maintenance ayant tourné le matin même
	//  sans que sa ligne survive à la rétention. Le libellé dit désormais ce qui
	//  est mesuré (`standards/04-fiabilite-des-controles.md` §14).
	const LIBELLE_STATUT: Record<string, string> = {
		ok: 'À jour',
		manquante: 'Exécution manquante',
		erreur: 'En échec',
		aucune_execution: 'Aucun rapport reçu'
	};

	const AIDE_STATUT: Record<string, string> = {
		ok: 'Un rapport est arrivé dans le délai attendu.',
		manquante: "Aucun rapport depuis plus longtemps que la périodicité de la tâche.",
		erreur: 'Le dernier rapport signale un échec.',
		aucune_execution:
			"Aucun rapport en base pour cette tâche. Cela ne prouve pas qu'elle n'a pas " +
			'tourné : un rapport peut avoir échoué à remonter, ou avoir été purgé. ' +
			'Vérifier le journal du nœud avant de conclure.'
	};

	// « hygiene_locale » ne veut rien dire pour un lecteur : c'est le ménage que le
	// nœud passif fait sans toucher à l'application ni à la base.
	const LIBELLE_PORTEE: Record<string, string> = {
		applicative: 'Maintenance applicative',
		hygiene_locale: 'Hygiène locale (nœud en veille)'
	};

	async function charger() {
		santeLoading = true;
		executionsLoading = true;
		try {
			sante = await api.get('/admin/maintenance/sante');
		} catch {
			sante = null;
		} finally {
			santeLoading = false;
		}
		try {
			executions = await api.get<any[]>('/admin/maintenance/historique');
		} catch {
			executions = [];
		} finally {
			executionsLoading = false;
		}
	}

	//  ⚠️ Ce bouton ne lance PAS `maintenance.sh`. Il appelle
	//  `POST /admin/maintenance/lancer` → `run_maintenance`, exécuté DANS le
	//  process de l'API : purges applicatives + VACUUM, sur le seul nœud qui
	//  répond. Le script hebdomadaire fait cela ET l'hygiène locale du standby
	//  (images Docker, cache de build, rotation des journaux) — que rien ici ne
	//  déclenche. Deux choses différentes : le libellé et l'aide le disent
	//  désormais, faute de quoi un clic ici laisse croire que l'hebdomadaire a
	//  été rattrapée.
	//
	//  Le retour à l'utilisateur avait été perdu en extrayant ce composant : ni
	//  succès ni erreur n'étaient signalés, et un clic sans effet visible se lit
	//  comme un bouton mort. La tâche part en arrière-plan (202), donc le succès
	//  annoncé est celui de la PRISE EN COMPTE, pas du ménage — le tableau, lui,
	//  dira ce qui s'est réellement passé.
	export async function declencher() {
		enCours = true;
		try {
			await api.post('/admin/maintenance/lancer');
			toast('success', 'Maintenance applicative lancée en arrière-plan.');
			setTimeout(charger, 4000);
		} catch (e: any) {
			toast('error', e?.message ?? "Impossible de lancer la maintenance");
		} finally {
			enCours = false;
		}
	}

	onMount(charger);
</script>

<section class="config-section">
	<h2 class="config-section-title">&#x1F4CB; Santé des tâches planifiées</h2>
	<p class="muted" style="font-size:.85rem">
		Synthèse : <strong>une ligne par tâche</strong>, quel que soit le nombre de nœuds
		qui l'exécutent. Quand une tâche tourne sur les deux, l'état affiché est celui du
		nœud le <strong>moins</strong> à jour — un nœud sain ne compense pas un nœud muet.
		Les tableaux qui suivent en donnent le détail. Sans ce contrôle, une absence de
		ligne se lirait comme « tout va bien ».
	</p>
	{#if santeLoading}
		<p class="muted">Chargement...</p>
	{:else if !sante || sante.taches.length === 0}
		<div class="empty-state">
			<h3>Aucune donnée</h3>
			<p>Aucune exécution n'a encore été enregistrée.</p>
		</div>
	{:else}
		<div class="card" style="overflow:auto;margin-top:1rem">
			<table class="table" style="font-size:.82rem">
				<thead><tr><th>Tâche</th><th>Nœud</th><th>État</th><th>Dernier rapport</th></tr></thead>
				<tbody>
					{#each sante.taches as t}
						<tr>
							<td>{LIBELLE_TACHE[t.tache] ?? t.tache}</td>
							<td style="color:var(--color-text-muted)">
								{#if !t.noeud_enregistre}
									<span style="font-style:italic"
										title="Cette tâche s'exécute sur le nœud actif, mais son historique ne conserve pas lequel. Afficher le nœud qui répond aujourd'hui serait faux : le rôle alterne chaque nuit.">non enregistré</span>
								{:else if t.statut === 'aucune_execution'}
									—
								{:else if t.noeud === 'inconnu' || !t.noeud}
									<span title="Le nœud n'était pas enregistré avant la v2.32.0" style="font-style:italic">non enregistré</span>
								{:else if t.noeuds?.length > 1 && t.statut === 'ok'}
									<!-- Les deux nœuds sont à jour : les nommer plutôt que d'en élire un,
									     sinon la ligne laisse croire que l'autre n'a rien fait. -->
									{t.noeuds.map((n: any) => n.noeud.toUpperCase()).join(' · ')}
								{:else}
									<span title={t.noeuds?.length > 1
										? `État porté par ${t.noeud.toUpperCase()}, le moins à jour des ${t.noeuds.length} nœuds.`
										: ''}>{t.noeud.toUpperCase()}</span>
								{/if}
							</td>
							<td>
								<span class="badge {t.statut === 'ok' ? 'badge-green' : 'badge-red'}"
									title={AIDE_STATUT[t.statut] ?? ''}>
									{LIBELLE_STATUT[t.statut] ?? t.statut}
								</span>
							</td>
							<td style="color:var(--color-text-muted)">{t.derniere ? fmtDatetime(t.derniere) : '—'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		{#if sante.anomalies_recentes.length > 0}
			<p class="muted" style="margin-top:.75rem;font-size:.85rem">
				<strong>{sante.anomalies_recentes.length}</strong> exécution(s) en échec récemment.
			</p>
		{/if}
	{/if}
</section>

<hr style="border:none;border-top:1px solid var(--color-border);margin:1.5rem 0" />

<section class="config-section">
	<!-- Pas « Maintenances programmées » : ce tableau contient aussi les bascules
	     et les copies hors site. Le nommer d'après une seule de ses tâches est
	     exactement le défaut corrigé en v2.49.0 — on lisait des bascules sous un
	     titre annonçant des maintenances. « Journal » dit sa nature (le détail,
	     chronologique) là où la synthèse est au-dessus. -->
	<h2 class="config-section-title">&#x1F527; Journal des exécutions — toutes tâches</h2>
	<div class="backup-header">
		<p class="muted" style="font-size:.85rem">
			Toutes les tâches planifiées des deux nœuds, pas seulement la maintenance —
			la colonne <strong>Tâche</strong> les distingue. Taille DB et Détail ne sont
			renseignés que par la maintenance applicative. Le bouton exécute cette part
			applicative (purges, VACUUM) sur ce nœud : il ne remplace pas le script
			hebdomadaire, qui fait en plus l'hygiène du nœud en veille.
		</p>
		<button class="btn btn-primary" on:click={declencher} disabled={enCours}
			title="Purges et VACUUM, sur ce nœud uniquement. Ne remplace pas le script hebdomadaire, qui fait en plus l'hygiène du nœud en veille : images Docker, cache de build, rotation des journaux.">
			{enCours ? 'En cours...' : 'Lancer la maintenance applicative'}
		</button>
	</div>
	{#if executionsLoading}
		<p class="muted">Chargement...</p>
	{:else if executions.length === 0}
		<div class="empty-state">
			<h3>Aucune exécution enregistrée</h3>
			<p>Aucune tâche n'a encore transmis de rapport, ou <code>MAINTENANCE_KEY</code> n'est pas configuré dans le <code>.env</code>.</p>
		</div>
	{:else}
		<div class="card" style="overflow:auto;max-height:420px;margin-top:1rem">
			<table class="table" style="font-size:.82rem">
				<thead class="sticky-head"><tr><th>Date</th><th>Tâche</th><th>Nœud</th><th>Portée</th><th>Statut</th><th>Taille DB</th><th>Durée</th><th>Détail</th></tr></thead>
				<tbody>
					{#each executions as m}
						<tr>
							<td style="font-size:.85rem">{fmtDatetime(m.cree_le)}</td>
							<td>{LIBELLE_TACHE[m.tache] ?? m.tache ?? '—'}</td>
							<td style="color:var(--color-text-muted)">
								{#if m.noeud}{m.noeud.toUpperCase()}{:else}<span title="Le nœud n'était pas enregistré avant la v2.32.0" style="font-style:italic">non enregistré</span>{/if}
							</td>
							<td style="color:var(--color-text-muted);font-size:.8rem">{LIBELLE_PORTEE[m.portee] ?? m.portee ?? '—'}</td>
							<td>
								<span class="badge {m.statut === 'succes' ? 'badge-green' : 'badge-red'}">{m.statut}</span>
								{#if m.erreur}<span title={m.erreur} style="margin-left:.4rem;cursor:help">⚠️</span>{/if}
							</td>
							<td style="color:var(--color-text-muted);font-size:.85rem">{m.taille_db_octets ? (m.taille_db_octets / 1024 / 1024).toFixed(1) + ' Mo' : '—'}</td>
							<td style="color:var(--color-text-muted);font-size:.85rem">{m.duree_secondes != null ? m.duree_secondes + ' s' : '—'}</td>
							<td style="color:var(--color-text-muted);font-size:.78rem">
								{#if m.details}
									{m.details.lignes_rotees ? m.details.lignes_rotees + ' lignes rotées' : ''}
									{m.details.cache_plafond ? ' · cache : ' + m.details.cache_plafond : ''}
									{m.details.tokens ? ' · ' + m.details.tokens + ' jetons' : ''}
								{:else}—{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p class="muted" style="margin-top:.6rem;font-size:.8rem">
			Les exécutions antérieures à la <strong>v2.32.0</strong> n'enregistraient pas le nœud :
			elles s'affichent « non enregistré ». Le nœud en veille transmettra son premier
			rapport après la prochaine bascule nocturne.
		</p>
	{/if}
</section>
