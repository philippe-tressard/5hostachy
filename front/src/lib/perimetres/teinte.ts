/**
 * La **teinte d'un périmètre** — quelle couleur porte sa pastille, et pourquoi
 * celle-là.
 *
 * ## Pourquoi un module à part, sans aucun import `$lib`
 *
 * La règle ci-dessous est une décision PURE : elle ne lit ni store, ni API, ni
 * DOM. L'isoler ici la rend éprouvable par `npm run lint:teinte --selftest`,
 * sans navigateur et sans arborescence réelle — le motif du dépôt pour toute
 * décision qu'on ne peut pas voir à l'œil (`boot-role-guard.sh`, puis
 * `listeDepliable.ts`).
 *
 * ⚠️ Aucun import de `$lib/…` ici, et ce n'est pas un oubli : le script de
 * self-test importe ce fichier par son chemin relatif, et un alias Vite ne se
 * résout pas sous `node --experimental-strip-types`.
 */

/** Ce que la teinte a besoin de savoir d'un nœud — rien de plus. */
export interface NoeudTeinte {
	code: string;
	parent: string | null;
	profondeur: number;
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
 * Le code qui DONNE la couleur : l'ancêtre de **premier niveau** (profondeur 1),
 * c'est-à-dire le bâtiment — ou l'espace de tête — dont le nœud dépend.
 *
 * 🔴 Signalé à l'écran le 12/09/2026 : sur le kanban, « Bât. 1 » était bleu clair
 * et « Ascenseur », qui est DANS le bâtiment 1, sortait rose. La couleur était
 * dérivée du code entier, donc deux nœuds d'une même branche tombaient sur deux
 * teintes sans rapport — et la pastille, qui doit dire d'un coup d'œil « ça se
 * passe au bâtiment 1 », disait le contraire.
 *
 * ⚠️ On s'arrête à la profondeur **1**, pas 0 : la racine est « toute la
 * résidence », et remonter jusqu'à elle donnerait une seule couleur à tout
 * l'arbre — l'autre façon de ne rien dire.
 *
 * ⚠️ Repli sur le code lui-même quand l'arbre n'est pas encore chargé : la
 * pastille garde une couleur stable et se corrigera au chargement, même choix
 * que `perimetreDuBatiment`.
 *
 * La remontée est bornée par `vus` : un cycle en base ne doit pas figer l'écran.
 *
 * @param lire  De quoi retrouver un nœud par son code — `noeudPerimetre` en
 *              service, une table en self-test.
 */
export function codeDeTeinte(
	code: string,
	lire: (code: string) => NoeudTeinte | undefined,
): string {
	let n = lire(code);
	if (!n) return code;
	const vus = new Set<string>();
	while (n.profondeur > 1 && n.parent && !vus.has(n.code)) {
		vus.add(n.code);
		const parent = lire(n.parent);
		if (!parent) break;
		n = parent;
	}
	return n.code;
}

/** La couleur d'un code, une fois la teinte choisie. */
export function teinteDuCode(base: string): string {
	let s = 0;
	for (let i = 0; i < base.length; i++) s = (s * 31 + base.charCodeAt(i)) >>> 0;
	return PALETTE_PERIMETRE[s % PALETTE_PERIMETRE.length];
}
