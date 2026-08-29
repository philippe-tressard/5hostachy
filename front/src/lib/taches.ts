//  Nom de chaque tâche planifiée — SOURCE UNIQUE.
//
//  Pourquoi un module et pas une constante dans l'écran : le nom d'une tâche
//  apparaissait à trois endroits qui ne se voyaient pas les uns les autres — la
//  synthèse « Santé des tâches planifiées », la colonne Tâche du journal, et le
//  titre de la carte de détail propre à cette tâche. Ils avaient divergé : la
//  synthèse disait « Sauvegarde quotidienne » quand la carte s'appelait
//  « Système — Sauvegardes ». On ne pouvait donc pas relier une ligne de la
//  synthèse au tableau qui la détaille. Signalé par l'utilisateur le 11/08/2026.
//
//  Les cartes de détail ont disparu avec #299 — le détail vit désormais SOUS la
//  ligne qui l'annonce, donc le titre n'a plus à être reconstruit ailleurs et
//  `titreDetail()` est parti avec elles. Ce module reste la source unique pour
//  les deux emplacements restants, qui sont dans deux fichiers différents.
//
//  Les clés sont celles que rend l'API (`tache` dans `historique_maintenance`,
//  plus `backup` et `telemetrie` qui ont leur propre table).
export const LIBELLE_TACHE: Record<string, string> = {
	maintenance: 'Maintenance hebdomadaire',
	backup: 'Sauvegarde quotidienne',
	bascule: 'Bascule actif/standby',
	telemetrie: 'Agrégation télémétrie',
	health_watch: 'Surveillance du site',
	reliability: 'Contrôles de fiabilité',
	auto_deploy: 'Déploiement automatique',
	//  Seule tâche lancée à la main depuis le poste : le libellé le dit, sinon une
	//  « exécution manquante » se lirait comme une panne alors qu'il s'agit d'un oubli.
	export_hors_site: 'Copie hors site (manuelle)',
};

//  Libellé du BOUTON qui lance une tâche à la main — quand il diffère du nom de
//  la tâche. Le nom d'une tâche planifiée et le nom de l'action déclenchable ne
//  sont pas la même chose : le bouton de la maintenance annonçait « Lancer
//  maintenance hebdomadaire » alors qu'il n'exécute que la part applicative
//  in-process (purges + VACUUM, sur le nœud qui répond). Le script hebdomadaire
//  fait cela ET l'hygiène du nœud en veille, que rien dans l'interface ne
//  déclenche.
//
//  Le 11/08/2026, l'utilisateur a cliqué ce bouton en croyant relancer la tâche
//  entière — et le rapport ainsi inséré a fait passer le badge au vert, masquant
//  le symptôme qu'un contrôle en cours d'observation attendait. La nuance était
//  écrite : en petit, à côté. Le libellé est ce qu'on lit avant d'agir ; une note
//  posée à côté ne corrige pas une promesse portée par le bouton lui-même.
export const LIBELLE_ACTION: Record<string, string> = {
	maintenance: 'Lancer la purge applicative',
};

/*  ── Les STATUTS d'une tâche planifiée ───────────────────────────────────────
    Remontés de `TachesPlanifiees.svelte` le 20/08/2026 (#488).

    🔴 Ils y ont grossi de trois à cinq états, et le garde-fou de modularité a
    refusé la croissance du fichier. Trois réponses possibles — découper,
    remonter la règle d'un cran, raboter (jamais) : c'est la deuxième, parce que
    ces tables ne disent rien de PROPRE à cet écran. Ce sont des données sur les
    statuts, et les libellés de TÂCHES vivaient déjà ici pour exactement cette
    raison — les redéfinir dans un écran est ce qui les fait diverger.  */
export const LIBELLE_STATUT: Record<string, string> = {
	ok: 'À jour',
	en_cours: 'En cours',
	rapport_perdu: 'Rapport non reçu',
	manquante: 'Exécution manquante',
	erreur: 'En échec',
	aucune_execution: 'Aucun rapport reçu',
};
export const AIDE_STATUT: Record<string, string> = {
	ok: 'Un rapport est arrivé dans le délai attendu.',
	manquante: 'Aucun rapport depuis plus longtemps que la périodicité de la tâche.',
	erreur: 'Le dernier rapport signale un échec.',
	aucune_execution:
		"Aucun rapport en base pour cette tâche. Cela ne prouve pas qu'elle n'a pas " +
		'tourné : un rapport peut avoir échoué à remonter, ou avoir été purgé. ' +
		'Vérifier le journal du nœud avant de conclure.',
	en_cours: 'La tâche a signalé son démarrage et n’a pas encore rendu son compte rendu.',
	rapport_perdu:
		'La tâche a DÉMARRÉ — elle a écrit son battement de début — mais son ' +
		"compte rendu n'est jamais arrivé. Le ménage a donc bien eu lieu ; c'est " +
		'la chaîne de remontée qui est rompue. Chercher du côté du réseau, de la ' +
		'clé de maintenance ou du format de la charge utile, pas du côté de la tâche.',
};
export const CLASSE_STATUT: Record<string, string> = {
	ok: 'badge-green',
	en_cours: 'badge-green',
	rapport_perdu: 'badge-orange',
	erreur: 'badge-red',
	manquante: 'badge-red',
	aucune_execution: 'badge-red',
};
