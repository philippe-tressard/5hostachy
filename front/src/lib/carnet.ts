//  Le carnet d'entretien, filtré par ANNÉE — la règle, une fois (24/09/2026).
//
//  Demandé à l'écran : « un filtre par exercice : à voir ce que la législation
//  indique sur la temporalité et s'y conformer ». Le décret n° 2001-477
//  (art. 4, version en vigueur au 01/01/2017) date les travaux par leur « année
//  de réalisation », et ne prévoit NI durée de conservation, NI périodicité, NI
//  archivage : le carnet est CUMULATIF, un acquéreur le lit en entier. D'où :
//  l'année civile, « Toutes » par défaut, et rien ne disparaît avec le temps.
//
//  ⚠️ Les CONTRATS restent présents quelle que soit l'année : le décret veut
//  ceux EN VIGUEUR (art. 3 et 4) — un contrat signé en 2019 vaut en 2026.
//  🔒 `npm run lint:carnet-annee` exécute ces deux fonctions.

interface EntreeDatee {
	date: string;
	origine: string;
}

/** Les années des faits datés du carnet, de la plus récente à la plus ancienne. */
export function anneesDuCarnet(entrees: readonly EntreeDatee[]): string[] {
	const annees = new Set(
		entrees.filter((e) => e.origine !== 'contrat').map((e) => e.date.slice(0, 4)),
	);
	return [...annees].sort().reverse();
}

/** Les entrées d'une année — `''` : toutes. Les contrats en cours restent. */
export function entreesDeLAnnee<T extends EntreeDatee>(entrees: readonly T[], annee: string): T[] {
	return entrees.filter((e) => !annee || e.origine === 'contrat' || e.date.startsWith(annee));
}
