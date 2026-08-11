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
	let enCours: string | null = null;

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

	async function charger() {
		santeLoading = true;
		try {
			sante = await api.get('/admin/maintenance/sante');
		} catch {
			sante = null;
		} finally {
			santeLoading = false;
		}
		//  Les historiques déjà dépliés sont rechargés : après un déclenchement
		//  manuel, la ligne ouverte doit montrer le passage qu'on vient de causer.
		for (const t of Object.keys(historiques)) await chargerHistorique(t, true);
	}

	//  Chaque tâche a SA source. Le tableau unique « Journal des exécutions »
	//  mélangeait les trois tâches de `historique_maintenance` sous un titre qui
	//  n'en annonçait qu'une, et laissait les deux autres — sauvegarde et
	//  agrégation — dans des cartes séparées : trois tableaux pour un même fait,
	//  aucun ne le disant. Signalé illisible par l'utilisateur le 11/08/2026.
	//  Le détail vit désormais SOUS la ligne qui l'annonce.
	const SOURCE: Record<string, { url: string; limite: number }> = {
		backup: { url: '/admin/sauvegardes/historique', limite: 4 },
		telemetrie: { url: '/admin/telemetry/historique', limite: 4 }
	};

	function urlHistorique(tache: string): string {
		const s = SOURCE[tache];
		return s ? s.url : `/admin/maintenance/historique?tache=${encodeURIComponent(tache)}&limite=4`;
	}

	let historiques: Record<string, any[]> = {};
	let enChargement: Record<string, boolean> = {};

	async function chargerHistorique(tache: string, force = false) {
		if (historiques[tache] && !force) return;
		enChargement = { ...enChargement, [tache]: true };
		try {
			const lignes = await api.get<any[]>(urlHistorique(tache));
			//  Les tables propres à une tâche ne savent pas se limiter côté serveur :
			//  on tronque ici, à la même profondeur que les autres.
			historiques = { ...historiques, [tache]: (lignes ?? []).slice(0, 4) };
		} catch {
			historiques = { ...historiques, [tache]: [] };
		} finally {
			enChargement = { ...enChargement, [tache]: false };
		}
	}

	//  Une seule ligne ouverte à la fois — pattern des cartes expansibles du projet.
	let ouverte: string | null = null;
	function basculer(tache: string) {
		ouverte = ouverte === tache ? null : tache;
		if (ouverte) chargerHistorique(ouverte);
	}

	//  Taille DB et Détail ne sont renseignés que par la maintenance applicative.
	//  Ils ne sont PAS structurellement vides : ils l'étaient parce qu'aucun
	//  rapport de maintenance n'arrivait. La colonne apparaît donc dès qu'une
	//  ligne la renseigne, et disparaît sinon — plutôt que d'être supprimée, ce
	//  qui aurait effacé une donnée à cause d'un défaut de remontée.
	const aValeur = (lignes: any[], champ: string) =>
		lignes.some((l) => l?.[champ] !== null && l?.[champ] !== undefined && l?.[champ] !== '');

	function fmtOctets(n: number | null | undefined): string {
		if (n === null || n === undefined) return '—';
		const mo = n / (1024 * 1024);
		return mo >= 1024 ? `${(mo / 1024).toFixed(2)} Go` : `${mo.toFixed(1)} Mo`;
	}

	//  Seules ces trois tâches savent se lancer à la main : les autres n'ont pas
	//  d'équivalent in-process. Ne montrer le bouton que là où il agit.
	const LANCEMENT: Record<string, string> = {
		maintenance: '/admin/maintenance/lancer',
		backup: '/admin/sauvegardes/maintenant',
		telemetrie: '/admin/telemetry/agreger'
	};

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
	async function declencher(tache: string) {
		const url = LANCEMENT[tache];
		if (!url) return;
		enCours = tache;
		try {
			await api.post(url);
			toast('success', `${LIBELLE_TACHE[tache]} lancée en arrière-plan.`);
			//  La tâche part en arrière-plan (202) : le succès annoncé est celui de
			//  la PRISE EN COMPTE. C'est l'historique rechargé qui dira ce qui s'est
			//  réellement passé — d'où le rechargement différé.
			setTimeout(charger, 4000);
		} catch (e: any) {
			toast('error', e?.message ?? `Impossible de lancer ${LIBELLE_TACHE[tache]}`);
		} finally {
			enCours = null;
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
						<tr class="cliquable" role="button" tabindex="0"
							aria-expanded={ouverte === t.tache}
							on:click={() => basculer(t.tache)}
							on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), basculer(t.tache))}>
							<td>
								<!--  Affordance de dépliement DEVANT le libellé, pas au bout de la
								      ligne : à droite, gris et petit, il n'était pas vu — l'utilisateur
								      ignorait que les lignes s'ouvraient (11/08/2026). -->
								<span class="chevron" class:open={ouverte === t.tache} aria-hidden="true">&#x25B8;</span>
								{LIBELLE_TACHE[t.tache] ?? t.tache}
							</td>
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
						{#if ouverte === t.tache}
							{@const lignes = historiques[t.tache] ?? []}
							<tr class="detail">
								<td colspan="4">
									{#if enChargement[t.tache]}
										<p class="muted" style="margin:.5rem 0">Chargement...</p>
									{:else if lignes.length === 0}
										<p class="muted" style="margin:.5rem 0">
											Aucune exécution enregistrée pour cette tâche.
										</p>
									{:else}
										<table class="table" style="font-size:.78rem;margin:.25rem 0">
											<thead>
												<tr>
													<th>Date</th><th>Nœud</th><th>Statut</th><th>Durée</th>
													{#if aValeur(lignes, 'taille_db_octets')}<th>Taille DB</th>{/if}
													{#if aValeur(lignes, 'details')}<th>Détail</th>{/if}
												</tr>
											</thead>
											<tbody>
												{#each lignes as l}
													<tr>
														<td>{fmtDatetime(l.cree_le)}</td>
														<td>{l.noeud ? l.noeud.toUpperCase() : '—'}</td>
														<td>
															<span class="badge {l.statut === 'erreur' || l.statut === 'echouee' ? 'badge-red' : 'badge-green'}">
																{l.statut ?? '—'}
															</span>
														</td>
														<td>{l.duree_secondes != null ? `${l.duree_secondes} s` : '—'}</td>
														{#if aValeur(lignes, 'taille_db_octets')}
															<td>{fmtOctets(l.taille_db_octets)}</td>
														{/if}
														{#if aValeur(lignes, 'details')}
															<td style="font-size:.72rem;color:var(--color-text-muted)">
																{l.details ? Object.entries(l.details).map(([k, v]) => `${k}: ${v}`).join(' · ') : '—'}
															</td>
														{/if}
													</tr>
												{/each}
											</tbody>
										</table>
									{/if}
									{#if LANCEMENT[t.tache]}
										<div style="margin:.5rem 0 .25rem">
											<button class="btn btn-primary" style="font-size:.8rem;padding:.3rem .7rem"
												on:click|stopPropagation={() => declencher(t.tache)}
												disabled={enCours === t.tache}
												title={t.tache === 'maintenance'
													? "Purges et VACUUM, sur ce nœud uniquement. Ne remplace pas le script hebdomadaire, qui fait en plus l'hygiène du nœud en veille."
													: ''}>
												{enCours === t.tache ? 'En cours...' : `Lancer ${LIBELLE_TACHE[t.tache].toLowerCase()}`}
											</button>
											{#if t.tache === 'maintenance'}
												<span class="muted" style="font-size:.75rem;margin-left:.5rem">
													part applicative seulement — l'hygiène du nœud en veille reste au script hebdomadaire
												</span>
											{/if}
										</div>
									{/if}
								</td>
							</tr>
						{/if}
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

<style>
	/*  Ligne de synthèse dépliable. Le détail vit SOUS la ligne qui l'annonce :
	    c'est ce qui remplace les trois tableaux séparés que l'utilisateur a
	    jugés illisibles le 11/08/2026. */
	tr.cliquable { cursor: pointer; }
	tr.cliquable:hover { background: var(--color-bg); }
	tr.cliquable:focus-visible { outline: 2px solid var(--color-primary); outline-offset: -2px; }
	tr.detail > td { background: var(--color-bg); padding: .25rem .75rem .75rem; }
	.chevron {
		display: inline-block; transition: transform .15s;
		color: var(--color-primary); font-size: .9rem; margin-right: .4rem;
	}
	.chevron.open { transform: rotate(90deg); }
</style>
