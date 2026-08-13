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
	utilise: boolean;
}

const PREFIXE_BATIMENT = 'bat:';

let carte: Record<string, Perimetre> = {};
let ordreCodes: string[] = [];
let codeDefaut: string | null = null;

const cle = (code: string) => (code ?? '').trim().toLowerCase();

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

function normaliser(items: string[] | string | null | undefined): string[] {
	const liste = typeof items === 'string' ? items.split(',') : (items ?? []);
	return liste.map((i) => (i ?? '').trim()).filter(Boolean);
}

/** Libellé d'un périmètre isolé. Ne rend jamais un code brut à l'écran. */
export function perimetreLabelUn(code: string): string {
	const n = carte[cle(code)];
	if (n) return n.libelle;
	//  Repli d'affichage, identique à celui du serveur : un contenu peut citer un
	//  nœud supprimé depuis, et l'arborescence peut n'être pas encore chargée.
	//  Ce n'est PAS une source de vérité — la convention `bat:N` est posée par le
	//  seed, l'arbre reste seul juge.
	if (code && cle(code).startsWith(PREFIXE_BATIMENT)) {
		return `Bât. ${code.slice(PREFIXE_BATIMENT.length)}`;
	}
	return code;
}

/**
 * Périmètres → libellé affichable. Séparateur ` · ` (espace point-médian espace).
 * Ex : ['bat:1','parking'] → 'Bât. 1 · Parking'
 *
 * Accepte les DEUX formes que porte réellement le produit : le tableau
 * `perimetre_cible` (publications, tickets) et la chaîne `perimetre` des
 * événements. Le calendrier réimplémentait la fonction pour cette seule raison,
 * avec une table recopiée à l'identique — une correction faite ici ne l'atteignait
 * pas (#316).
 *
 * Le `trim()` n'est pas cosmétique : sur `'bat:1, parking'`, une clé avec espace
 * de tête ne correspond à rien et ressortirait brute à l'écran.
 */
export function perimetreLabel(items: string[] | string | null | undefined): string {
	return normaliser(items).map(perimetreLabelUn).join(' · ');
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
export const ICONES_PERIMETRE: { nom: string; libelle: string }[] = [
	{ nom: 'building-2', libelle: 'Bâtiment' },
	{ nom: 'home', libelle: 'Copropriété' },
	{ nom: 'door-closed', libelle: 'Hall, porte' },
	{ nom: 'stairs', libelle: 'Escalier' },
	{ nom: 'layers', libelle: 'Paliers, étages' },
	{ nom: 'arrow-up-down', libelle: 'Ascenseur' },
	{ nom: 'box', libelle: 'Cave, stockage' },
	{ nom: 'car', libelle: 'Parking' },
	{ nom: 'square-parking', libelle: 'Parking public' },
	{ nom: 'trees', libelle: 'Espaces verts' },
	{ nom: 'sprout', libelle: 'Jardin' },
	{ nom: 'footprints', libelle: 'Cheminement' },
	{ nom: 'lightbulb', libelle: 'Éclairage' },
	{ nom: 'zap', libelle: 'Électricité' },
	{ nom: 'droplet', libelle: 'Eau' },
	{ nom: 'flame', libelle: 'Chauffage' },
	{ nom: 'warehouse', libelle: 'Local technique' },
	{ nom: 'wrench', libelle: 'Entretien' },
	{ nom: 'settings', libelle: 'Divers technique' },
];
