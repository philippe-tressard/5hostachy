/**
 * La **teinte d'un périmètre** — quelle couleur porte sa pastille, et pourquoi
 * celle-là.
 *
 * ## La règle, telle qu'elle a été arbitrée (13/09/2026)
 *
 * > « La couleur des catégories de niveau *n* hérite de la catégorie de
 * >   niveau 1. »
 * > « Si plusieurs catégories de niveau 1 : mettre celle du bâtiment s'il n'y en
 * >   a qu'un, sinon celle de toute la copropriété. »
 *
 * Une pastille dit d'un coup d'œil **où ça se passe**. Tout ce qui vit sous
 * « Bât. 1 » porte la couleur du bâtiment 1 ; tout ce qui vit sous « Local
 * technique » porte la sienne, et les deux sont **différentes**. Ce qu'on ne
 * sait pas rattacher à un seul espace de tête porte la couleur de la
 * copropriété — jamais une couleur au hasard, qui laisserait croire à un
 * rattachement.
 *
 * ## Pourquoi un module à part, sans aucun import `$lib`
 *
 * La règle est une décision PURE : elle ne lit ni store, ni API, ni DOM.
 * L'isoler ici la rend éprouvable par `npm run lint:teinte`, sans navigateur et
 * sans arborescence réelle — le motif du dépôt pour toute décision qu'on ne peut
 * pas voir à l'œil (`boot-role-guard.sh`, puis `listeDepliable.ts`).
 *
 * ⚠️ Aucun import de `$lib/…` ici, et ce n'est pas un oubli : le script de
 * self-test importe ce fichier par son chemin relatif, et un alias Vite ne se
 * résout pas sous `node --experimental-strip-types`.
 */

/** Ce que la teinte a besoin de savoir d'un nœud — rien de plus. */
export interface NoeudTeinte {
	code: string;
	parent: string | null;
}

//  Couleur DÉRIVÉE du code : la table de sept clés en dur laissait en gris tout
//  périmètre créé depuis l'administration, et tout bâtiment au-delà du quatrième.
export const PALETTE_PERIMETRE = [
	'#ef4444',
	'#3b82f6',
	'#22c55e',
	'#f59e0b',
	'#f97316',
	'#8b5cf6',
	'#ec4899',
	'#0ea5e9',
	'#14b8a6',
];

/**
 * La couleur de « toute la copropriété » — le repli de ce qu'on ne sait pas
 * rattacher à UN espace de tête.
 *
 * ⚠️ Hors palette, et volontairement : c'est un gris neutre. Reprendre une
 * couleur de la palette ferait passer « non rattaché » pour « rattaché à ce
 * bâtiment-là », ce qui est exactement le défaut qu'on corrige. C'est déjà le
 * gris que porte la pastille « 🏘️ Copropriété » du périmètre par défaut.
 */
export const TEINTE_COPROPRIETE = '#6b7280';

/**  La même normalisation que l'arbre : un code se compare **sans casse ni
 *   espaces**. Sans elle, « Bat:1 » et « bat:1 » seraient deux périmètres. */
const cle = (code: string) => (code ?? '').trim().toLowerCase();

/**
 * Le premier segment d'un code — « bât. 1/ascenseur » → « bât. 1 ».
 *
 * 🔴 LE CODE PORTE LUI-MÊME LA HIÉRARCHIE, et c'est ce qui sauve l'affichage
 * quand l'arbre ne répond pas (13/09/2026). Les codes administrés s'écrivent en
 * chemin — `locaux-techniques/local-eau`, `cheminements/portillon` — parce que
 * l'écran de création compose `parent + "/" + slug`.
 *
 * ⚠️ C'est un REPLI, pas la règle : l'arbre reste la source, parce qu'un code
 * peut être plat (`aful`, `parking`) tout en ayant un parent. Mais quand il ne
 * répond pas — cache pas encore rempli, nœud supprimé cité par un contenu
 * ancien — le premier segment est infiniment mieux que rien : deux branches
 * distinctes gardent deux couleurs distinctes.
 */
const premierSegment = (code: string) => (code ?? '').split('/')[0] || code;

/**
 * Le NIVEAU d'un nœud : 0 pour une racine, 1 pour ses enfants, etc.
 *
 * 🔴 Calculé depuis la chaîne des `parent`, et **non lu dans un champ
 * `profondeur`** (13/09/2026). La première version s'y fiait, et le défaut est
 * resté visible en production : « Bât. 1 › ascenseur » et « Local technique ›
 * eau » sortaient de la même couleur alors que les deux branches sont
 * distinctes.
 *
 * ⚠️ La leçon est celle du dépôt — *vérifier le fait, pas le symptôme attendu*.
 * Le niveau est une propriété de l'ARBRE : il se déduit de ce qu'on a sous la
 * main, au lieu de dépendre d'un champ que la réponse peut ne pas porter et dont
 * l'absence **ne lève rien** — `undefined > 1` vaut `false`, donc la remontée
 * s'arrêtait aussitôt et tous les nœuds retombaient sur le condensat, avec une
 * chance sur neuf de collision à chaque paire.
 *
 * Borné par `vus` : un cycle en base ne doit pas figer l'écran.
 */
function niveau(code: string, lire: (code: string) => NoeudTeinte | undefined): number {
	let n = lire(code);
	let d = 0;
	const vus = new Set<string>();
	while (n?.parent && !vus.has(cle(n.code))) {
		vus.add(cle(n.code));
		const parent = lire(n.parent);
		if (!parent) break;
		n = parent;
		d++;
	}
	return d;
}

/**
 * Le code qui DONNE la couleur : l'ancêtre de **premier niveau** — le bâtiment,
 * ou l'espace de tête — dont le nœud dépend.
 *
 * ⚠️ On s'arrête au niveau **1**, pas 0 : la racine est « toute la résidence »,
 * et remonter jusqu'à elle donnerait une seule couleur à tout l'arbre — l'autre
 * façon de ne rien dire.
 *
 * ⚠️ Repli sur le code lui-même quand l'arbre n'est pas chargé : la pastille
 * garde une couleur stable et se corrigera au chargement, même choix que
 * `perimetreDuBatiment`.
 */
export function codeDeTeinte(
	code: string,
	lire: (code: string) => NoeudTeinte | undefined,
): string {
	let n = lire(code);
	//  🔴 L'arbre ne connaît pas ce code — cache pas encore rempli, ou périmètre
	//  supprimé cité par un contenu ancien. Le code porte alors sa propre
	//  hiérarchie : « bât. 1/ascenseur » donne « bât. 1 », et deux branches
	//  distinctes gardent deux couleurs distinctes.
	//
	//  ⚠️ Rendre le code ENTIER ici était le défaut du 13/09 : toutes les
	//  pastilles retombaient alors sur le même repli, et l'écran perdait ses
	//  couleurs par bâtiment.
	if (!n) return premierSegment(code);
	const vus = new Set<string>();
	while (niveau(n.code, lire) > 1 && n.parent && !vus.has(cle(n.code))) {
		vus.add(cle(n.code));
		const parent = lire(n.parent);
		if (!parent) break;
		n = parent;
	}
	return n.code;
}

/**
 * Les codes de **premier niveau** d'un arbre, dans son ordre.
 *
 * 🔴 Calculés depuis les `parent`, pour la même raison que `niveau` : ne dépendre
 * d'aucun champ que la réponse pourrait ne pas porter.
 *
 * ⚠️ Repli sur le niveau 0 quand AUCUN nœud n'est au niveau 1 : un arbre à
 * plusieurs racines côte à côte est légitime, et rendre une liste vide ferait
 * retomber tout le monde sur le repli — c'est-à-dire sur une seule couleur pour
 * tout l'écran.
 */
export function premierNiveauDe(
	codes: readonly string[],
	lire: (code: string) => NoeudTeinte | undefined,
): string[] {
	const parNiveau = (n: number) => codes.filter((c) => niveau(c, lire) === n);
	const un = parNiveau(1);
	return un.length ? un : parNiveau(0);
}

/**
 * Le RANG d'un code parmi les nœuds de premier niveau, ou `-1` s'il n'en est pas.
 *
 * ⚠️ Comparaison par `cle()` — sans casse ni espaces, comme l'arbre. Une
 * comparaison stricte rendrait `-1` sur une simple différence de casse, et le
 * code retomberait sur le repli sans que rien ne le dise.
 */
export function rangPremierNiveau(code: string, premierNiveau: readonly string[]): number {
	return premierNiveau.findIndex((c) => cle(c) === cle(code));
}

/**
 * La couleur d'un code, une fois la teinte choisie.
 *
 * 🔴 **Par RANG, pas par condensat.** Un condensat réparti sur neuf couleurs
 * collisionne dès le quatrième nœud (paradoxe des anniversaires : ~50 % à partir
 * de quatre). Deux espaces de premier niveau tombaient donc régulièrement sur la
 * même teinte, et la pastille disait « même endroit » de deux lieux sans rapport
 * — l'inverse exact de ce qu'elle existe pour dire.
 *
 * Le rang garantit **N couleurs distinctes pour les N premiers**. Au-delà de la
 * palette, la collision est inévitable : neuf couleurs ne peuvent pas en
 * distinguer dix.
 *
 * ⚠️ **Rang inconnu → un condensat du code de tête**, pas le gris de la
 * copropriété. La version du 13/09 rendait le gris dans ce cas, et l'écran a
 * perdu TOUTES ses couleurs par bâtiment d'un coup : quand l'arbre ne répond
 * pas, le rang est inconnu pour tout le monde, et un repli unique repeint la
 * page entière.
 *
 * Le condensat porte alors sur le **code de tête** — « bât. 1 » et non « bât.
 * 1/ascenseur » —, si bien que l'héritage tient même sans arbre. Il peut faire
 * collisionner deux têtes (une chance sur neuf), et c'est le prix d'un affichage
 * dégradé : bien moins cher qu'un écran monochrome.
 *
 * ⚠️ Le gris de la copropriété reste pour ce qui n'a **aucun** code de tête —
 * une chaîne vide. Il ne peut pas se confondre avec un bâtiment : il n'est pas
 * dans la palette.
 *
 * @param rang  L'index du code parmi les nœuds de premier niveau, ou `-1`.
 */
export function teinteDuCode(base: string, rang = -1): string {
	if (rang >= 0) return PALETTE_PERIMETRE[rang % PALETTE_PERIMETRE.length];
	const tete = premierSegment(base);
	if (!tete) return TEINTE_COPROPRIETE;
	let s = 0;
	for (let i = 0; i < tete.length; i++) s = (s * 31 + tete.charCodeAt(i)) >>> 0;
	return PALETTE_PERIMETRE[s % PALETTE_PERIMETRE.length];
}
