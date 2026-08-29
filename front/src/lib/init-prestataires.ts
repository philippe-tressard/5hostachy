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
 * ⚠️ Elle reste **fragile**, et c'est documenté en #605 : elle repose sur une
 * chaîne d'affichage. Renommer un contrat ou son prestataire fait perdre la
 * correspondance, et changer la fréquence déplace les mois. Le remède est un
 * `contrat_id` sur l'événement — donc une migration, hors de ce lot.
 */
export function clePlanifiee(titre: string, mois: number): string {
	return `${titreBase(titre)}||${mois}`;
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
			//  La clé se calcule sur le mois EN BASE 0, comme les événements lus.
			if (clesExistantes.has(clePlanifiee(source.titre, mois - 1))) {
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
