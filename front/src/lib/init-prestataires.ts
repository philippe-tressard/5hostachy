/**
 * Pré-remplissage du kanban à partir des prestataires — la DÉCISION, isolée.
 *
 * Extrait de `calendrier/+page.svelte` le 28/08/2026 (#605), pour trois raisons
 * qui vont ensemble :
 *
 *   1. **Deux boucles quasi identiques** y construisaient les mêmes événements à
 *      partir de deux sources — les contrats d'entretien et les événements de
 *      maintenance existants. Elles avaient déjà divergé : l'une calculait le
 *      périmètre du bâtiment, l'autre posait `perimetre: ev.perimetre ?? ''`,
 *      c'est-à-dire **une chaîne vide** quand la source n'en portait pas. Une
 *      seule fonction, deux appels : la divergence n'a plus où se loger.
 *   2. **Rien ne l'éprouvait.** `annualFreq` et `spreadMonth` sont des fonctions
 *      pures dont une erreur produit des cartes au mauvais mois — ce qui ne se
 *      voit qu'en regardant le kanban, donc jamais.
 *   3. La page est à 848 lignes, au-dessus du seuil de modularité : la règle est
 *      « on découpe QUAND on y touche ».
 *
 * « Pur » veut dire ici : aucun appel réseau, aucune lecture de store, aucun
 * effet. L'appelant résout le périmètre (qui dépend de données chargées) et
 * passe une source déjà normalisée. Éprouvé par
 * `node --experimental-strip-types scripts/check-init-prestataires.mjs --selftest`.
 */

/**
 * Au-delà, on ne pré-remplit pas : une maintenance mensuelle ferait douze cartes
 * dans une colonne qui en compte déjà.
 *
 * ⚠️ Ce plafond était **muet** jusqu'au 28/08/2026 : une source trop fréquente
 * disparaissait sans être comptée ni nommée, et le message final annonçait
 * « aucune source éligible » — ce qui se lit comme « il n'y a rien », alors que
 * la vérité est « il y a quelque chose, et je l'ai écarté ». `planifier` les
 * rend désormais dans `horsPlafond`.
 */
export const OCCURRENCES_MAX_AN = 4;

/** Une source de pré-remplissage, déjà normalisée par l'appelant. */
export interface SourceRecurrente {
	/** Le libellé SANS numéro d'occurrence — il est ajouté ici. */
	titre: string;
	frequence_type: string | null;
	frequence_valeur: number | null;
	prestataire_id: number | null;
	/**  Le contrat d'où vient cette visite, quand il y en a un (#605, point 2).
	 *   `null` pour une source qui est un événement de maintenance saisi à la main. */
	contrat_id: number | null;
	/** Déjà résolu par l'appelant : le calcul dépend de données chargées. */
	perimetre: string;
	description: string | null;
}

export interface EvenementPlanifie {
	titre: string;
	type: 'maintenance_recurrente';
	perimetre: string;
	batiment_id: null;
	statut_kanban: 'fournisseur';
	prestataire_id: number | null;
	/** La source, quand la visite vient d'un contrat — la clé anti-doublon (#605). */
	contrat_id: number | null;
	debut: string;
	description: string | null;
	affichable: false;
}

export interface Plan {
	aCreer: EvenementPlanifie[];
	/** Combien existaient déjà — ce qui n'est PAS une erreur, mais se dit. */
	ignores: number;
	/** Les sources écartées faute de tenir sous le plafond, avec leur fréquence. */
	horsPlafond: { titre: string; parAn: number }[];
	/** Les sources sans fréquence exploitable : elles ne se pré-remplissent pas. */
	sansFrequence: number;
}

/**
 * Le nombre de passages par an, ou `0` si la fréquence n'est pas exploitable.
 *
 * ⚠️ Le cas zéro est explicite : une valeur nulle ou négative donnerait
 * `12 / 0 = Infinity`, qui passe le test « > 0 » et ne serait écarté que par
 * hasard, au plafond. Un garde qui tient par accident tient jusqu'au jour où le
 * plafond bouge.
 */
export function frequenceAnnuelle(type: string | null, valeur: number | null): number {
	if (!type || !valeur || valeur <= 0) return 0;
	if (type === 'fois_par_an') return valeur;
	if (type === 'mois') return Math.floor(12 / valeur);
	if (type === 'semaines') return Math.floor(52 / valeur);
	return 0;
}

/** Le mois (1-12) de la `index`-ième occurrence sur `total` dans l'année. */
export function moisOccurrence(total: number, index: number): number {
	if (total <= 0) return 1;
	return 1 + index * Math.floor(12 / total);
}

/**
 * Le titre d'une occurrence — numéroté **à partir de deux**.
 *
 * Une visite annuelle unique ne porte pas de « (1/1) » : un numéro qui ne
 * distingue rien ajoute du bruit à toutes les cartes pour n'en séparer aucune.
 * À partir de deux, quatre cartes « Otis — Ascenseur A » devenaient
 * indiscernables dans la colonne, sauf à ouvrir chacune pour lire sa date.
 */
export function titreOccurrence(base: string, index: number, total: number): string {
	return total >= 2 ? `${base} (${index + 1}/${total})` : base;
}

/**
 * Le titre débarrassé de son numéro d'occurrence.
 *
 * 🔴 C'est ce qui rend le numéro rétro-compatible, et ce n'est pas un détail :
 * la détection des doublons rapproche les candidats des événements DÉJÀ créés,
 * par leur titre. Sans cette normalisation, l'arrivée du numéro aurait fait
 * échouer toutes les correspondances d'un coup — et le premier clic après la
 * mise en production aurait **recréé l'intégralité de l'exercice en double**.
 *
 * ⚠️ Un libellé de contrat qui se terminerait vraiment par « (1/2) » verrait son
 * suffixe retiré ici. La conséquence est bornée : deux titres partageraient une
 * clé de doublon. C'est assumé — l'inverse (ne rien normaliser) casse un cas
 * certain pour protéger un cas improbable.
 */
export function titreBase(titre: string): string {
	return titre.replace(/\s*\(\d+\/\d+\)\s*$/, '');
}

/**
 * La clé qui dit « cette occurrence existe déjà » : titre de base + mois.
 *
 * ⚠️ Elle est **fragile**, et c'est pourquoi `cleSource` existe depuis le
 * 01/09/2026 : elle repose sur une chaîne d'affichage, que renommer un contrat ou
 * son prestataire fait perdre.
 *
 * Elle ne disparaît pas pour autant — c'est le **repli** qui reconnaît les visites
 * créées avant cette date, qui ne portent aucun `contrat_id`. Le retirer ferait
 * recréer l'intégralité de l'exercice au premier clic.
 */
export function clePlanifiee(titre: string, mois: number): string {
	return `${titreBase(titre)}||${mois}`;
}

/**
 * La clé qui dit « cette occurrence existe déjà », par sa SOURCE (#605, point 2).
 *
 * 🔴 Une chaîne d'affichage n'est pas une identité. `clePlanifiee` rapproche sur
 * le titre littéral et le mois, et les deux se dérobent :
 *
 * - renommer un contrat — ou renommer le prestataire, qui compose le titre —
 *   fait perdre la correspondance, et le clic suivant **recrée tout l'exercice
 *   en double** ;
 * - passer la fréquence de 2 à 3 par an déplace les visites : les anciennes ne
 *   correspondent plus, et l'on obtient 3 nouvelles **en plus** des 2 existantes.
 *
 * L'index d'occurrence remplace le mois pour cette seconde raison : de 2 à 3 par
 * an, les index 0 et 1 correspondent toujours, et seul le 2 est créé. Les deux
 * premières visites restent aux mois de l'ancienne répartition — imparfait, et
 * franchement meilleur que cinq cartes.
 */
export function cleSource(contratId: number, index: number): string {
	return `contrat:${contratId}#${index}`;
}

/** Une visite déjà posée, telle que l'API la rend — seuls ces champs comptent. */
export interface VisiteExistante {
	titre: string;
	debut: string;
	type?: string;
	archivee?: boolean;
	contrat_id?: number | null;
}

/**
 * Les clés des visites DÉJÀ posées pour un exercice — les deux formes.
 *
 * 🔴 Elle vivait dans l'écran, où rien ne l'éprouvait : c'est pourtant elle qui
 * décide si le clic recrée ou non l'exercice entier. Le contrôle de modularité
 * a refusé de la laisser grossir dans une page de 1 114 lignes, et il désignait
 * le bon endroit — cette fonction parle de clés, comme ses deux voisines.
 *
 * ⚠️ **Deux clés par visite**, et la rétro-compatibilité l'impose : celles créées
 * avant le 01/09/2026 ne portent aucun `contrat_id`. Ne rapprocher que par la
 * source ferait recréer tout l'exercice au premier clic.
 *
 * L'index d'occurrence se déduit du **rang** de la visite parmi celles du même
 * contrat, triées par date — l'ordre dans lequel `planifier` les fabrique.
 */
export function clesDesEvenements(evenements: VisiteExistante[], exercice: number): Set<string> {
	const retenus = evenements.filter(
		(ev) =>
			ev.type === 'maintenance_recurrente' &&
			!ev.archivee &&
			new Date(ev.debut).getFullYear() === exercice,
	);
	return new Set(
		retenus.flatMap((ev) => {
			const parTitre = clePlanifiee(ev.titre, new Date(ev.debut).getMonth());
			if (!ev.contrat_id) return [parTitre];
			const fratrie = retenus
				.filter((o) => o.contrat_id === ev.contrat_id)
				.sort((a, b) => a.debut.localeCompare(b.debut));
			return [parTitre, cleSource(ev.contrat_id, fratrie.indexOf(ev))];
		}),
	);
}

/**
 * Le plan de pré-remplissage : ce qui serait créé, ce qui existe, ce qui est
 * écarté et pourquoi. **Ne crée rien** — c'est l'appelant qui écrit.
 *
 * @param sources      les sources normalisées, contrats et événements confondus
 * @param clesExistantes les clés (`clePlanifiee`) déjà présentes pour l'exercice
 * @param exercice     l'année visée
 */
export function planifier(
	sources: SourceRecurrente[],
	clesExistantes: Set<string>,
	exercice: number,
): Plan {
	const plan: Plan = { aCreer: [], ignores: 0, horsPlafond: [], sansFrequence: 0 };

	for (const source of sources) {
		const parAn = frequenceAnnuelle(source.frequence_type, source.frequence_valeur);
		if (parAn <= 0) {
			plan.sansFrequence++;
			continue;
		}
		if (parAn > OCCURRENCES_MAX_AN) {
			plan.horsPlafond.push({ titre: source.titre, parAn });
			continue;
		}
		for (let i = 0; i < parAn; i++) {
			const mois = moisOccurrence(parAn, i);
			//  🔴 DEUX clés, et c'est la rétro-compatibilité qui l'impose. Les
			//  visites créées avant le 01/09/2026 n'ont pas de `contrat_id` : ne
			//  rapprocher que par la source ferait recréer l'intégralité de
			//  l'exercice au premier clic — le défaut même qu'on corrige, en pire.
			//
			//  ⚠️ Le repli par titre disparaîtra tout seul : un exercice
			//  entièrement pré-rempli après cette date n'a plus que des visites
			//  portant leur contrat. Le retirer AVANT serait le retirer trop tôt.
			//
			//  La clé de titre se calcule sur le mois EN BASE 0, comme les
			//  événements lus.
			const dejaLa =
				(source.contrat_id !== null && clesExistantes.has(cleSource(source.contrat_id, i))) ||
				clesExistantes.has(clePlanifiee(source.titre, mois - 1));
			if (dejaLa) {
				plan.ignores++;
				continue;
			}
			plan.aCreer.push({
				titre: titreOccurrence(source.titre, i, parAn),
				type: 'maintenance_recurrente',
				perimetre: source.perimetre,
				batiment_id: null,
				statut_kanban: 'fournisseur',
				prestataire_id: source.prestataire_id || null,
				contrat_id: source.contrat_id,
				debut: `${exercice}-${String(mois).padStart(2, '0')}-15T09:00`,
				description: source.description || null,
				affichable: false,
			});
		}
	}
	return plan;
}

/**
 * Le message qui rend compte du plan — y compris de ce qui a été ÉCARTÉ.
 *
 * Il vit ici et non dans la page parce que c'est la contrepartie du plafond :
 * une décision qui écarte silencieusement se lit comme une absence de matière.
 */
export function resumePlan(plan: Plan, exercice: number): string {
	const parts: string[] = [];
	if (plan.ignores > 0) parts.push(`${plan.ignores} existant(s) ignoré(s)`);
	if (plan.horsPlafond.length > 0) {
		const detail = plan.horsPlafond.map((h) => `${h.titre} (${h.parAn}/an)`).join(', ');
		parts.push(
			`${plan.horsPlafond.length} écarté(s) au-delà de ${OCCURRENCES_MAX_AN}/an : ${detail}`,
		);
	}
	if (plan.sansFrequence > 0) parts.push(`${plan.sansFrequence} sans fréquence exploitable`);

	if (plan.aCreer.length === 0) {
		return parts.length === 0
			? `Aucune source de maintenance récurrente pour ${exercice}.`
			: `Rien à créer pour ${exercice} — ${parts.join(' · ')}.`;
	}
	const entete = `Créer ${plan.aCreer.length} événement(s) prestataire pour ${exercice} ?`;
	return parts.length === 0 ? entete : `${entete}\n(${parts.join('\n')})`;
}
