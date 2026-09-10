import { perimetreLabel, perimetreLabelUn } from './libelles';

/**
 * Périmètres — le rendu, sans table.
 *
 * ## Ce que ce module remplace
 *
 * `lib/utils.ts` portait `PERIMETRE_LABELS`, une table de libellés écrite en dur
 * et arrêtée à `bat:4`, quand l'API allait jusqu'à `bat:9` : un cinquième bâtiment
 * s'affichait « Bât. 5 » côté serveur et **`bat:5` brut** à l'écran. Trois copies
 * s'étaient installées autour (#316), toutes correctes, toutes divergentes à terme.
 *
 * L'arborescence vit désormais en base et s'édite depuis l'administration. Ce
 * module n'en garde qu'un **cache d'affichage**, rempli par
 * `stores/perimetres.ts` au démarrage.
 *
 * ## Pourquoi un module à part, sans aucun import
 *
 * `perimetreLabel()` est appelée dans une quinzaine de gabarits, en plein milieu
 * du rendu : elle doit rester **synchrone**. La rendre asynchrone aurait imposé de
 * réécrire chacun de ces appels. Elle lit donc une carte de module, et le store
 * s'occupe de la remplir — c'est le store qui connaît l'API, pas l'inverse.
 *
 * N'importer rien ici est délibéré : `lib/utils.ts` réexporte `perimetreLabel`, et
 * une dépendance vers `$lib/api` créerait un cycle avec les modules qui importent
 * `utils`.
 */

/** Un nœud de l'arborescence, tel que `GET /perimetres` le rend. */
export interface Perimetre {
	id: number;
	code: string;
	parent: string | null;
	libelle: string;
	libelle_court: string;
	description: string;
	icone: string | null;
	batiment_id: number | null;
	profondeur: number;
	ordre: number;
	actif: boolean;
	portee_globale: boolean;
	concerne_tous: boolean;
	selectionnable: boolean;
	/**  Cet espace est-il PRIVATIF — un logement, une cave, une place attribuée —
	 *   par opposition aux parties communes ? Administré depuis Admin →
	 *   Patrimoine, jamais deviné d'après le libellé : chaque copropriété nomme
	 *   ses espaces comme elle veut (31/08/2026).
	 *
	 *   ⚠️ **Purement visuel pour l'instant.** La pastille se distingue, rien
	 *   d'autre ne change — ni qui voit, ni qui est notifié. */
	privatif: boolean;
	utilise: boolean;
}

export const PREFIXE_BATIMENT = 'bat:';

//  Exportée pour `libelles.ts` seul : le paquet la partage, le dépôt ne la
//  voit pas — `index.ts` ne la réexporte pas.
export let carte: Record<string, Perimetre> = {};
let ordreCodes: string[] = [];
let codeDefaut: string | null = null;

export const cle = (code: string) => (code ?? '').trim().toLowerCase();

/**
 * Remplit le cache d'affichage. Appelé par `stores/perimetres.ts`, nulle part ailleurs.
 */
export function definirPerimetres(liste: Perimetre[]): void {
	carte = Object.fromEntries(liste.map((n) => [cle(n.code), n]));
	ordreCodes = liste.map((n) => n.code);
	//  Le périmètre « tout le monde » est une DONNÉE, pas la chaîne « résidence »
	//  écrite dans le code : une autre copropriété peut l'avoir renommé ou supprimé.
	//  C'est la racine à portée globale la plus prioritaire, comme côté serveur
	//  (`api/app/utils/perimetres.py`, `code_par_defaut`).
	const racines = liste.filter((n) => n.parent === null && n.portee_globale && n.actif);
	codeDefaut = racines.length ? racines[0].code : null;
}

/** L'arborescence connue, dans l'ordre d'affichage rendu par l'API. */
export function tousLesPerimetres(): Perimetre[] {
	return ordreCodes.map((c) => carte[cle(c)]).filter(Boolean);
}

export function noeudPerimetre(code: string): Perimetre | undefined {
	return carte[cle(code)];
}

/**
 * Le code du périmètre qui représente un bâtiment donné.
 *
 * Six endroits du front construisaient `` `bat:${batiment_id}` `` à la main —
 * la convention de nommage du seed recopiée en dur, alors que l'administration
 * peut créer un bâtiment sous n'importe quel code. On interroge l'arbre.
 *
 * Retombe sur la convention si l'arborescence n'est pas encore chargée : c'est un
 * affichage, et le libellé se corrigera au chargement.
 */
export function perimetreDuBatiment(batimentId: number | null | undefined): string {
	if (batimentId === null || batimentId === undefined) return perimetreParDefaut() ?? '';
	const trouve = tousLesPerimetres().find((n) => n.batiment_id === batimentId && n.actif);
	return trouve ? trouve.code : `${PREFIXE_BATIMENT}${batimentId}`;
}

/** Le code qui désigne « toute la copropriété », ou `null` sur un arbre vide. */
export function perimetreParDefaut(): string | null {
	return codeDefaut;
}

/**
 * La sélection initiale d'un formulaire — « toute la copropriété ».
 *
 * Les pages écrivaient `['résidence']` en dur, une trentaine de fois. Sur une
 * copropriété qui renomme ou supprime ce nœud, chacune de ces occurrences aurait
 * produit un périmètre inexistant, sans erreur visible : le formulaire se serait
 * ouvert sur une pastille morte. Liste vide sur un arbre vide, ce que le serveur
 * traite déjà comme « concerne tout le monde ».
 */
export function perimetreDefautListe(): string[] {
	return codeDefaut ? [codeDefaut] : [];
}

/**
 * Cette sélection désigne-t-elle toute la copropriété ?
 *
 * Remplace les comparaisons `=== 'résidence'` semées dans les pages, qui
 * cesseraient d'être vraies dès qu'une copropriété renomme ou supprime ce nœud.
 * Une liste vide vaut « tout le monde », comme côté serveur.
 */
export function estPerimetreParDefaut(items: string[] | string | null | undefined): boolean {
	const liste = normaliser(items);
	if (liste.length === 0) return true;
	return liste.length === 1 && codeDefaut !== null && cle(liste[0]) === cle(codeDefaut);
}

export function normaliser(items: string[] | string | null | undefined): string[] {
	const liste = typeof items === 'string' ? items.split(',') : (items ?? []);
	return liste.map((i) => (i ?? '').trim()).filter(Boolean);
}

/**
 * L'un de ces périmètres concerne-t-il tous les résidents ?
 *
 * Miroir de `a_portee_globale` côté serveur. L'héritage est déjà résolu par l'API,
 * qui rend `concerne_tous` pour chaque nœud — inutile de remonter l'arbre ici.
 *
 * Remplace la liste `['résidence','parking','cave','aful']` que le tableau de bord
 * portait en dur, troisième copie d'une même énumération.
 */
export function concerneTous(items: string[] | string | null | undefined): boolean {
	return normaliser(items).some((c) => carte[cle(c)]?.concerne_tous === true);
}

/**
 * Les bâtiments réellement visés — celui du nœud, ou du plus proche ancêtre qui en
 * porte un. C'est ce qui fait que « Bât. 2 › Hall d'entrée » concerne le bâtiment 2
 * sans que le hall ait à le répéter.
 *
 * Miroir de `batiments_cibles` côté serveur. La remontée est bornée par `vus` : une
 * boucle dans l'arbre ne doit pas figer l'interface.
 */
export function batimentsCibles(items: string[] | string | null | undefined): number[] {
	const cibles = new Set<number>();
	for (const code of normaliser(items)) {
		let courant = carte[cle(code)];
		const vus = new Set<string>();
		while (courant && !vus.has(cle(courant.code))) {
			if (courant.batiment_id !== null) {
				cibles.add(courant.batiment_id);
				break;
			}
			vus.add(cle(courant.code));
			courant = courant.parent ? carte[cle(courant.parent)] : undefined!;
		}
	}
	return [...cibles];
}

/**
 * Icônes proposées pour un périmètre, dans l'écran d'administration.
 *
 * Volontairement **courte et thématique** : un choix de cinquante icônes ne se
 * parcourt pas, il se subit. Chacune doit dire quelque chose d'un lieu de
 * copropriété — et toutes existent dans `Icon.svelte`, sans quoi la pastille
 * s'afficherait avec le point d'interrogation du repli.
 */
/**
 * Les périmètres de PREMIER NIVEAU — ceux qui font une rangée de pastilles.
 *
 * Un nœud de premier niveau est soit une **racine sélectionnable**, soit
 * l'**enfant d'un regroupement racine** : « Bâtiments » n'est pas une cible, on
 * choisit un bâtiment. Cela remonte les bâtiments dans la première rangée, là où
 * on les cherche, *sans inventer de niveau dans les données*.
 *
 * 🔴 Cette règle vivait dans `PerimetrePicker.svelte` jusqu'au 10/09/2026, où le
 * carnet d'entretien a eu besoin de la même rangée **pour filtrer**. Un filtre
 * qui l'aurait recalculée à sa façon aurait divergé au premier périmètre créé en
 * administration — et c'est justement ce que ce filtre doit savoir faire : suivre
 * l'arborescence sans qu'on y touche.
 *
 * @param exclure — le code à ne pas rendre. Le sélecteur écarte le périmètre
 *   PAR DÉFAUT (il est déjà la valeur initiale) ; un filtre l'écarte aussi, mais
 *   le remplace par sa propre pastille « tout ». Deux usages, une règle.
 */
export function perimetresNiveau1(liste: Perimetre[], exclure?: string | null): Perimetre[] {
	const actifs = liste.filter((n) => n.actif);
	const parCode = new Map(actifs.map((n) => [n.code, n]));
	const estGroupeRacine = (n: Perimetre | undefined): boolean =>
		!!n && n.parent === null && !n.selectionnable;
	return actifs.filter(
		(n) =>
			n.selectionnable &&
			n.code !== exclure &&
			(n.parent === null || estGroupeRacine(parCode.get(n.parent!))),
	);
}

/**
 * Le périmètre dont HÉRITE une nouvelle entrée d'historique.
 *
 * 🔴 Signalé à l'écran le 31/08/2026 :
 *
 * > *« quand on fait un commentaire sur un Ticket, par défaut le périmètre du
 * > dernier commentaire (ou du ticket original si 1er commentaire) n'est pas
 * > conservé »*
 *
 * Le formulaire proposait « Copropriété entière » sur un ticket situé « Bât. 1 ›
 * Escaliers ». Il ne mentait pas sur ce qui allait s'écrire — le serveur ne
 * touche à rien quand le champ est vide — mais il **montrait un choix par défaut
 * qui n'était pas celui qui s'appliquerait**, ce qui revient au même pour qui
 * lit l'écran.
 *
 * ⚠️ L'héritage remonte les entrées, il ne prend pas seulement le ticket : une
 * entrée a pu resserrer le périmètre — « on a trouvé d'où vient la fuite » — et
 * c'est ce resserrement, le plus récent, qui vaut ensuite. Prendre le ticket
 * ferait revenir en arrière à chaque commentaire.
 *
 * ⚠️ Une entrée qui ne dit RIEN du périmètre ne compte pas : elle n'a rien
 * précisé, donc elle n'a rien changé. C'est le sens de la valeur vide, et c'est
 * ce qui permet à un courriel d'afficher « 🔹 … » sur une entrée pour dire
 * qu'elle a précisé quelque chose.
 *
 * @param perimetreObjet le périmètre de l'objet porteur (ticket, événement…)
 * @param entrees        l'historique, dans l'ordre CHRONOLOGIQUE
 */
export function perimetreHerite(
	perimetreObjet: string[] | null | undefined,
	entrees: { perimetre_cible?: string[] | null }[] = [],
): string[] {
	for (let i = entrees.length - 1; i >= 0; i--) {
		const precise = entrees[i]?.perimetre_cible;
		if (precise && precise.length) return [...precise];
	}
	return [...(perimetreObjet ?? [])];
}

/**
 * Deux périmètres désignent-ils la même chose ? **L'ORDRE ne compte pas.**
 *
 * Le sélecteur mémorise l'ordre des clics ; deux mêmes zones cochées dans un
 * autre ordre sont le même périmètre. C'est déjà la règle de `perimetreLabel`,
 * qui trie avant de rendre — la comparer autrement ferait diverger l'affichage
 * et la décision.
 *
 * ⚠️ Employé pour n'envoyer `perimetre_cible` que s'il DIFFÈRE de l'hérité : une
 * comparaison sensible à l'ordre ferait déclarer un resserrement à chaque
 * commentaire où l'on aurait décoché puis recoché la même zone.
 */
export function memePerimetre(a: string[], b: string[]): boolean {
	return a.length === b.length && [...a].sort().join('|') === [...b].sort().join('|');
}

/**
 * Le périmètre d'une nouvelle entrée d'historique : ce qu'elle déclare, et le
 * libellé de ce dont elle part.
 *
 * ## Pourquoi une fonction et pas trois `$:` dans le formulaire
 *
 * Les deux valeurs se répondent, et la subtile est `declare` : elle vaut
 * `undefined` tant qu'on n'a pas touché à l'hérité. C'est ce **vide** qui permet
 * au courriel de n'afficher « 🔹 … » que sur les entrées qui ont précisé quelque
 * chose — une entrée qui redit le périmètre du ticket n'apprend rien.
 *
 * Elles vivaient dans `EvolForm`, qui sert quatre écrans et qui a franchi le
 * plafond de modularité le 31/08/2026. Le contrôle désignait un **placement** :
 * ces trois lignes parlent de périmètre, pas de formulaire, et leur place est
 * ici — à côté de `perimetreHerite`, dont elles sont les seules clientes.
 */
export function perimetreEntree(
	perimetreCourant: string[],
	entrees: { perimetre_cible?: string[] | null }[],
	choisi: string[],
	sectionActive: boolean,
): { declare: string[] | undefined; libelleActuel: string } {
	const depart = perimetreHerite(perimetreCourant, entrees);
	return {
		declare: sectionActive && choisi.length && !memePerimetre(choisi, depart) ? choisi : undefined,
		libelleActuel: depart.length
			? perimetreLabel(depart)
			: perimetreLabelUn(perimetreParDefaut() ?? ''),
	};
}
