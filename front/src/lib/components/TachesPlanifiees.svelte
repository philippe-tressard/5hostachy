<script lang="ts">
  import Icon from '$lib/components/Icon.svelte';
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
	import { LIBELLE_TACHE, LIBELLE_ACTION } from '$lib/taches';
	import ConfigSauvegarde from '$lib/components/ConfigSauvegarde.svelte';

	//  Le bouton dit ce qu'il FAIT, pas le nom de la tâche — voir LIBELLE_ACTION.
	//  Défaut : « Lancer <nom de la tâche> », qui reste juste là où le bouton
	//  déclenche bien la tâche entière (sauvegarde, agrégation).
	const libelleBouton = (t: string) =>
		LIBELLE_ACTION[t] ?? `Lancer ${LIBELLE_TACHE[t].toLowerCase()}`;

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
	const SOURCE: Record<string, string> = {
		backup: '/admin/sauvegardes/historique',
		telemetrie: '/admin/telemetry/historique'
	};

	//  Profondeur d'historique sous une ligne dépliée. UNE constante : elle était
	//  écrite trois fois — dans `SOURCE.limite`, qui n'était même pas lue, dans
	//  l'URL des tâches à source commune, et dans le `slice` des tables propres.
	//  Portée de 4 à 10 le 11/08/2026 en supprimant les deux cartes de détail qui
	//  montraient l'historique complet (#299) : les retirer sans compenser aurait
	//  réduit en silence ce qu'un administrateur peut voir.
	const PROFONDEUR = 10;

	function urlHistorique(tache: string): string {
		return (
			SOURCE[tache] ??
			`/admin/maintenance/historique?tache=${encodeURIComponent(tache)}&limite=${PROFONDEUR}`
		);
	}

	//  Ce que fait une tâche, quand sa ligne seule ne le dit pas. Repris des deux
	//  cartes supprimées avec #299 : elles faisaient double emploi pour
	//  l'historique, mais portaient ces informations-là, et rien d'autre ne les
	//  donnait. Les supprimer sans les déplacer aurait perdu la seule mention du
	//  lieu de stockage des archives.
	const AIDE_TACHE: Record<string, string> = {
		backup: 'Stockage des archives : /data/5hostachy/backups/',
		telemetrie:
			'Automatique chaque nuit à 2 h. Agrège les événements bruts en données ' +
			'journalières puis mensuelles, et purge les données expirées.'
	};

	let historiques: Record<string, any[]> = {};
	let enChargement: Record<string, boolean> = {};

	async function chargerHistorique(tache: string, force = false) {
		if (historiques[tache] && !force) return;
		enChargement = { ...enChargement, [tache]: true };
		try {
			const lignes = await api.get<any[]>(urlHistorique(tache));
			//  Les tables propres à une tâche ne savent pas se limiter côté serveur :
			//  on tronque ici, à la même profondeur que les autres.
			historiques = { ...historiques, [tache]: (lignes ?? []).slice(0, PROFONDEUR) };
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
	//  Étendu le 11/08/2026 au NŒUD et à la DURÉE : `historique_sauvegarde` et
	//  `historique_telemetrie` n'ont ni l'une ni l'autre de ces colonnes, et le
	//  tableau affichait donc quatre tirets alignés — l'utilisateur les a lus
	//  comme un historique « incomplet », ce qui est exactement ce qu'une colonne
	//  vide raconte. Une colonne qu'aucune ligne ne renseigne ne s'affiche pas.
	const aValeur = (lignes: any[], champ: string) =>
		lignes.some((l) => l?.[champ] !== null && l?.[champ] !== undefined && l?.[champ] !== '');

	function fmtOctets(n: number | null | undefined): string {
		if (n === null || n === undefined) return '—';
		const mo = n / (1024 * 1024);
		return mo >= 1024 ? `${(mo / 1024).toFixed(2)} Go` : `${mo.toFixed(1)} Mo`;
	}

	//  Colonnes propres à la sauvegarde et à l'agrégation. Elles vivaient dans les
	//  deux cartes supprimées avec #299, et la ligne dépliée ne savait pas les
	//  rendre : la taille des archives, le déclencheur, le volume agrégé et les
	//  lignes purgées avaient donc disparu de l'écran. Signalé par l'utilisateur
	//  le 11/08/2026 — la compensation portait sur la PROFONDEUR de l'historique
	//  et j'avais manqué sa LARGEUR.
	//
	//  Chacune suit la même règle que Taille DB et Détail : présente dès qu'une
	//  ligne la renseigne, absente sinon. Une tâche ne montre donc que les
	//  colonnes que sa table sait remplir.
	const CHAMPS_PURGE = ['events_purges', 'daily_purges', 'monthly_purges'];

	//  0 est une valeur, pas une absence : `aValeur` ne retient que null, undefined
	//  et la chaîne vide. Une purge qui n'a rien eu à purger doit s'afficher « 0 ».
	const aPurges = (lignes: any[]) => CHAMPS_PURGE.some((c) => aValeur(lignes, c));

	const totalPurges = (l: any): number =>
		CHAMPS_PURGE.reduce((somme, c) => somme + (Number(l?.[c]) || 0), 0);

	//  « 1 jour · 0 mois » — le pluriel suit le nombre de JOURS, comme dans la
	//  carte d'origine ; les mois gardent leur forme courte.
	const fmtAgrege = (l: any): string =>
		`${l.jours_agreges} jour${l.jours_agreges > 1 ? 's' : ''} · ${l.mois_agreges} mois`;

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

<section class="card config-section">
	<h2 class="config-section-title"><Icon name="clipboard-list" size={17} />Santé des tâches planifiées</h2>
	<p class="muted" style="font-size:.85rem">
		Synthèse : <strong>une ligne par tâche</strong>, portant la <strong>dernière
		exécution réelle</strong> — quel que soit le nœud qui l'a faite. Quand une tâche
		tourne sur les deux, chacun a sa <strong>propre sous-ligne</strong> : un nœud sain
		ne compense pas un nœud muet, et l'on voit lequel décroche sans avoir à cliquer.
		Sans ce contrôle, une absence de ligne se lirait comme « tout va bien ».
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
										title="Cette exécution est antérieure à la v2.53.0, qui a ajouté la colonne : on ne sait pas quel nœud l'a faite. Afficher le nœud qui répond aujourd'hui serait faux — le rôle alterne chaque nuit. La colonne se remplira à la prochaine exécution.">non enregistré</span>
								{:else if t.statut === 'aucune_execution'}
									—
								{:else if t.noeud === 'inconnu' || !t.noeud}
									<span title="Le nœud n'était pas enregistré avant la v2.32.0" style="font-style:italic">non enregistré</span>
								{:else}
									<!-- Le nœud de la DERNIÈRE exécution. Les autres ont leur propre
									     sous-ligne ci-dessous : plus rien n'est élu ni masqué (#331). -->
									<span title={t.noeuds?.length > 1
										? `Nœud de la dernière exécution. L'état de chaque nœud est détaillé sous cette ligne.`
										: ''}>{t.noeud.toUpperCase()}</span>
								{/if}
							</td>
							<td>
								<span class="badge {t.statut === 'ok' ? 'badge-green' : 'badge-red'}"
									title={AIDE_STATUT[t.statut] ?? ''}>
									{LIBELLE_STATUT[t.statut] ?? t.statut}
								</span>
								{#if t.noeud_en_retard}
									<!-- La dernière exécution est saine, mais un nœud décroche. L'ancien
									     écran le disait en remplaçant l'état ET la date par ceux du
									     retardataire — ce qui faisait mentir « Dernier rapport ». -->
									<span class="badge badge-orange" style="margin-left:.35rem"
										title="Ce nœud n'a pas exécuté la tâche dans le délai attendu. La dernière exécution, elle, s'est bien passée sur l'autre nœud.">
										{t.noeud_en_retard.toUpperCase()} en retard
									</span>
								{/if}
							</td>
							<td style="color:var(--color-text-muted)">{t.derniere ? fmtDatetime(t.derniere) : '—'}</td>
						</tr>
						{#if t.noeuds?.length > 1}
							<!--  UNE SOUS-LIGNE PAR NŒUD, toujours visible (#331).
							      C'est elle, et non l'état de synthèse, qui garantit désormais qu'un
							      nœud sain ne compense pas un nœud muet. Toujours visible et non
							      dépliable : ce qu'il faut voir sans cliquer ne se range pas derrière
							      un clic. Rendue seulement au-delà d'un nœud — une sous-ligne unique
							      qui répète la synthèse serait du bruit. -->
							{#each t.noeuds as n}
								<tr class="par-noeud">
									<td></td>
									<td style="color:var(--color-text-muted)">↳ {n.noeud.toUpperCase()}</td>
									<td>
										<span class="badge {n.statut === 'ok' ? 'badge-green' : 'badge-red'}"
											title={AIDE_STATUT[n.statut] ?? ''}>
											{LIBELLE_STATUT[n.statut] ?? n.statut}
										</span>
									</td>
									<td style="color:var(--color-text-muted)">{n.derniere ? fmtDatetime(n.derniere) : '—'}</td>
								</tr>
							{/each}
						{/if}
						{#if ouverte === t.tache}
							{@const lignes = historiques[t.tache] ?? []}
							<tr class="detail">
								<td colspan="4">
									{#if AIDE_TACHE[t.tache]}
										<p class="aide-tache">{AIDE_TACHE[t.tache]}</p>
									{/if}
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
													<th>Date</th>
													{#if aValeur(lignes, 'noeud')}<th>Nœud</th>{/if}
													{#if aValeur(lignes, 'declenchee_par')}<th>Déclenchement</th>{/if}
													<th>Statut</th>
													{#if aValeur(lignes, 'jours_agreges')}<th>Événements agrégés</th>{/if}
													{#if aPurges(lignes)}<th>Purges</th>{/if}
													{#if aValeur(lignes, 'duree_secondes')}<th>Durée</th>{/if}
													{#if aValeur(lignes, 'taille_octets')}<th>Taille</th>{/if}
													{#if aValeur(lignes, 'taille_db_octets')}<th>Taille DB</th>{/if}
													{#if aValeur(lignes, 'details')}<th>Détail</th>{/if}
												</tr>
											</thead>
											<tbody>
												{#each lignes as l}
													<tr>
														<td>{fmtDatetime(l.cree_le)}</td>
														{#if aValeur(lignes, 'noeud')}
															<td>{l.noeud ? l.noeud.toUpperCase() : '—'}</td>
														{/if}
														{#if aValeur(lignes, 'declenchee_par')}
															<td style="color:var(--color-text-muted)">{l.declenchee_par ?? '—'}</td>
														{/if}
														<td>
															<span class="badge {l.statut === 'erreur' || l.statut === 'echouee' ? 'badge-red' : 'badge-green'}">
																{l.statut ?? '—'}
															</span>
															<!--  Le motif de l'échec était porté par la carte supprimée avec
															      #299 : sans lui, un statut « erreur » ne dit pas pourquoi. -->
															{#if l.erreur}<span title={l.erreur} style="margin-left:.4rem;cursor:help">⚠️</span>{/if}
														</td>
														{#if aValeur(lignes, 'jours_agreges')}
															<td style="color:var(--color-text-muted)">{fmtAgrege(l)}</td>
														{/if}
														{#if aPurges(lignes)}
															<td style="color:var(--color-text-muted)">{totalPurges(l)} lignes</td>
														{/if}
														{#if aValeur(lignes, 'duree_secondes')}
															<td>{l.duree_secondes != null ? `${l.duree_secondes} s` : '—'}</td>
														{/if}
														{#if aValeur(lignes, 'taille_octets')}
															<td>{fmtOctets(l.taille_octets)}</td>
														{/if}
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
										<!--  Bouton à DROITE, comme dans les deux cartes supprimées avec #299
										      et comme partout ailleurs dans le projet : action primaire à
										      droite (`ux-patterns` §9). Collé à gauche sous le tableau, il se
										      lisait comme une cellule de plus. Signalé par l'utilisateur le
										      11/08/2026. La note de la maintenance reste à gauche : elle se lit
										      AVANT le geste qu'elle nuance, pas après. -->
										<div class="lancement">
											{#if t.tache === 'maintenance'}
												<span class="muted note-lancement">
													part applicative seulement — l'hygiène du nœud en veille reste au script hebdomadaire
												</span>
											{/if}
											<button class="btn btn-primary" style="font-size:.8rem;padding:.3rem .7rem"
												on:click|stopPropagation={() => declencher(t.tache)}
												disabled={enCours === t.tache}
												title={t.tache === 'maintenance'
													? "Purges et VACUUM, sur ce nœud uniquement. Ne remplace pas le script hebdomadaire, qui fait en plus l'hygiène du nœud en veille."
													: ''}>
												{enCours === t.tache ? 'En cours...' : libelleBouton(t.tache)}
											</button>
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

<ConfigSauvegarde />

<style>
	/*  Ligne de synthèse dépliable. Le détail vit SOUS la ligne qui l'annonce :
	    c'est ce qui remplace les trois tableaux séparés que l'utilisateur a
	    jugés illisibles le 11/08/2026. */
	tr.cliquable { cursor: pointer; }
	tr.cliquable:hover { background: var(--color-bg); }
	tr.cliquable:focus-visible { outline: 2px solid var(--color-primary); outline-offset: -2px; }
	tr.detail > td { background: var(--color-bg); padding: .25rem 0 .75rem; }
	/*  Sous-ligne par nœud : rattachée visuellement à sa tâche sans devenir une
	    ligne de plein droit, sinon on relit un tableau à double granularité —
	    exactement ce qui avait été corrigé le 11/08/2026. */
	tr.par-noeud > td { padding-top: .15rem; padding-bottom: .15rem; font-size: .95em; }
	/*  Écart assumé : plus petit et en couleur primaire — il ouvre une ligne
	    de tableau, pas une carte, et doit se voir (il était invisible avant
	    le 11/08, cf. #299). */
	.chevron { font-size: .9rem; color: var(--color-primary); margin-right: .4rem; }
	/*  Aide propre à une tâche, en tête de son détail — recueillie des deux cartes
	    supprimées avec #299. */
	.aide-tache {
		margin: .5rem 0 .25rem; padding-left: .75rem;
		font-size: .78rem; color: var(--color-text-muted);
	}
	/*  Action primaire à droite. `margin-right:auto` sur la note plutôt que
	    `space-between` : sans note, le bouton doit rester à droite quand même. */
	.lancement {
		display: flex; align-items: center; justify-content: flex-end;
		gap: .75rem; margin: .5rem 0 .25rem; padding: 0 .75rem;
	}
	.note-lancement { font-size: .75rem; margin-right: auto; }
</style>
