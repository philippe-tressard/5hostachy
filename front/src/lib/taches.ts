//  Nom de chaque tâche planifiée — SOURCE UNIQUE.
//
//  Pourquoi un module et pas une constante dans l'écran : le nom d'une tâche
//  apparaît à trois endroits qui ne se voient pas les uns les autres — la
//  synthèse « Santé des tâches planifiées », la colonne Tâche du journal, et le
//  titre de la carte de détail propre à cette tâche. Ils avaient divergé : la
//  synthèse disait « Sauvegarde quotidienne » quand la carte s'appelait
//  « Système — Sauvegardes », et « Agrégation télémétrie » quand la carte
//  s'appelait « Historique des agrégations ». On ne pouvait donc pas relier une
//  ligne de la synthèse au tableau qui la détaille. Signalé par l'utilisateur le
//  11/08/2026.
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
	export_hors_site: 'Copie hors site (manuelle)'
};

//  Titre d'une carte qui détaille UNE tâche. Passer par cette fonction plutôt que
//  d'écrire le titre à la main est ce qui garantit que le détail porte le même nom
//  que la ligne de synthèse qui y renvoie.
export function titreDetail(tache: string): string {
	return `${LIBELLE_TACHE[tache] ?? tache} — historique`;
}
