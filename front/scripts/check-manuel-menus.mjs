/**
 * Garde-fou : le manuel annonce les MENUS du site, et le bon public pour chacun.
 *
 * ## 🔴 Pourquoi (#651, 02/09/2026)
 *
 * Le sujet de #651 tient en une phrase : *« le manuel RECOPIE des tables que le
 * code fait évoluer, et rien ne les rapproche »*. Périmètres, plafonds de pièces
 * jointes, types acceptés, table des pages : à chaque fois, la copie a divergé.
 *
 * La section « Les écrans » a remplacé une grille de captures d'écran datées de
 * mars, illisibles à 300 px et aux boutons inertes (signalé à l'écran). Ce qui la
 * remplace porte deux informations : **quels menus existent**, et **qui peut les
 * voir**. Ce sont exactement deux tables que le code tient déjà :
 *
 *   · `front/src/lib/pages.ts` — les pages et leur route ;
 *   · `front/src/lib/components/Nav.svelte` — qui voit quelle entrée.
 *
 * En écrire une troisième en prose, c'était refaire le défaut le jour même où on
 * le corrige. D'où ce contrôle.
 *
 * ## Ce qu'il vérifie, et pourquoi il lit une STRUCTURE et non de la prose
 *
 * Chaque carte porte \`data-page\` et \`data-acces\`. Le contrôle compare :
 *
 *   1. l'ensemble des routes citées = l'ensemble des routes de \`pages.ts\` ;
 *   2. le public annoncé = ce que \`Nav.svelte\` applique.
 *
 * ## ⚠️ CE QU'IL NE PEUT PAS VÉRIFIER : L'ORDRE
 *
 * Le manuel présente les écrans dans l'ordre du menu. Mais cet ordre ne vit pas
 * dans le code : il est dans `pages_order`, une clé de `ConfigSite` que
 * l'administration réordonne. `pages.ts` n'en porte que le défaut, et la
 * production s'en écarte — c'est ce qui a été signalé le 03/09/2026, *« les
 * écrans n'est pas celui effectif des menus »*.
 *
 * Ce contrôle vérifie donc l'ENSEMBLE des routes et le PUBLIC de chacune, jamais
 * leur ordre. Le relever avant de retoucher la grille :
 *
 *     curl -s https://5hostachy.fr/api/config | grep -o '"pages_order":"[^"]*"'
 *
 * Une limite nommée vaut mieux qu'une limite tue : sans ce paragraphe, un vert
 * ici se lirait comme « le manuel est conforme au menu », ce qu'il ne dit pas.
 *
 * ⚠️ **La prose ne se lit pas comme une table** — #651 le dit lui-même, et un
 * contrôle qui crie sur du légitime finit désarmé. Les attributs sont la réponse :
 * ils rendent la table lisible par une machine sans contraindre le texte, qui
 * reste libre.
 *
 * Usage : npm run lint:manuel-menus
 */
import { readFileSync } from 'node:fs';

const RACINE = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const MANUEL = `${RACINE}../docs/manuel-utilisateur.html`;
const PAGES = `${RACINE}src/lib/pages.ts`;
const NAV = `${RACINE}src/lib/components/Nav.svelte`;

/**
 * Le public de chaque route, DÉDUIT de `Nav.svelte`.
 *
 * ⚠️ Table tenue à la main **côté attendu seulement**, et c'est assumé : traduire
 * une expression JavaScript en catégorie de public n'est pas mécanisable. Ce qui
 * l'est — et que le contrôle fait — c'est vérifier qu'aucune route n'a de règle
 * spéciale dans `Nav.svelte` sans figurer ici : une sixième restriction ajoutée
 * là-bas fait échouer ce fichier.
 */
const PUBLIC_ATTENDU = {
	'/prestataires': 'cs',
	'/espace-cs': 'cs',
	'/admin': 'admin',
	'/delegations': 'cs-ou-aidant',
	'/sondages': 'resident',
};
const PUBLIC_PAR_DEFAUT = 'tous';

const manuel = readFileSync(MANUEL, 'utf8');
const pages = readFileSync(PAGES, 'utf8');
const nav = readFileSync(NAV, 'utf8');

const erreurs = [];

// ── Les routes du site ──────────────────────────────────────────────────────
const routes = new Set([...pages.matchAll(/^\t\thref: '([^']+)',$/gm)].map((m) => m[1]));
//  🔴 CAS ZÉRO — sans routes, tout le reste serait vert sans rien lire.
if (routes.size < 10) {
	console.error(
		`✗ Cas zéro : ${routes.size} route(s) trouvée(s) dans pages.ts, 10 au minimum. ` +
			'La forme du fichier a changé — ce contrôle ne mesure plus rien.',
	);
	process.exit(1);
}

// ── Ce que le manuel annonce ────────────────────────────────────────────────
const cartes = new Map(
	[...manuel.matchAll(/data-page="([^"]+)"\s+data-acces="([^"]+)"/g)].map((m) => [m[1], m[2]]),
);
if (cartes.size === 0) {
	console.error(
		'✗ Cas zéro : aucune carte `data-page` dans le manuel. La section « Les écrans » ' +
			'a-t-elle été renommée ou retirée ? Ne pas lire ceci comme un succès.',
	);
	process.exit(1);
}

for (const route of routes) {
	if (!cartes.has(route)) {
		erreurs.push(`le menu ${route} existe dans pages.ts et le manuel ne le cite pas`);
		continue;
	}
	const attendu = PUBLIC_ATTENDU[route] ?? PUBLIC_PAR_DEFAUT;
	if (cartes.get(route) !== attendu) {
		erreurs.push(
			`le menu ${route} : le manuel annonce « ${cartes.get(route)} », ` +
				`Nav.svelte applique « ${attendu} »`,
		);
	}
}
for (const [route] of cartes) {
	//  `profil` n'a pas de route de menu (href null) et c'est légitime : on y accède
	//  par l'avatar. Il est cité parce que le lecteur le cherche.
	if (route !== 'profil' && !routes.has(route)) {
		erreurs.push(`le manuel cite ${route}, qui n'existe pas dans pages.ts`);
	}
}

// ── Une restriction ajoutée dans Nav.svelte sans être déclarée ici ──────────
//  C'est le contrôle qui empêche cette table de se périmer en silence.
for (const m of nav.matchAll(/if \(href === '([^']+)'\)/g)) {
	if (!(m[1] in PUBLIC_ATTENDU)) {
		erreurs.push(
			`Nav.svelte restreint ${m[1]}, et PUBLIC_ATTENDU l'ignore — ` +
				'le manuel annoncerait « tous » à tort',
		);
	}
}

// ── Les DEUX MAQUETTES du menu (04/09/2026) ────────────────────────────────
//  Elles montrent le même menu à deux endroits : celui de l'ordinateur, toujours
//  affiché, et celui du téléphone, replié. C'est la COMPARAISON qui fait le
//  propos — si les deux listes divergent, le lecteur ne compare plus rien, il lit
//  deux menus dont l'un est faux, sans savoir lequel.
//
//  ⚠️ On ne vérifie PAS que les maquettes citent les mêmes routes que la grille :
//  une maquette est une illustration, elle peut légitimement s'arrêter avant la
//  fin. Ce qu'on exige, c'est qu'elles soient d'accord ENTRE ELLES.
const duo = manuel.match(/<div class="maq-duo">([\s\S]*?)<\/div>\s*<p class="maq-note"/);
if (!duo) {
	erreurs.push('les deux maquettes du menu sont introuvables (`.maq-duo`)');
} else {
	const figures = duo[1].split('<figure class="maq">').slice(1);
	if (figures.length !== 2) {
		erreurs.push(`${figures.length} maquette(s) de menu au lieu de 2`);
	} else {
		const compte = (f) => (f.match(/class="maq-item/g) || []).length;
		const [bureau, mobile] = figures.map(compte);
		//  Cas zéro : deux listes vides seraient « d’accord », et ne montreraient rien.
		if (bureau < 5 || mobile < 5) {
			erreurs.push(`maquettes quasi vides (${bureau} et ${mobile} entrées) — rien à comparer`);
		} else if (bureau !== mobile) {
			erreurs.push(
				`les deux maquettes divergent : ${bureau} entrées sur ordinateur, ` +
					`${mobile} sur téléphone — c'est pourtant le même menu`,
			);
		}

		//  🔴 LE BOUTON DU TÉLÉPHONE DOIT ÊTRE DESSINÉ ET EXPLIQUÉ (04/09/2026).
		//  Il portait le caractère ☰, qui ne dit rien à qui n'a jamais fait le
		//  rapprochement — c'est-à-dire au lecteur de ce guide, qui n'est pas
		//  informaticien. Un symbole que le lecteur doit déjà connaître n'explique
		//  rien : il trie ceux qui savaient déjà.
		const tel = figures[1];
		if (!/class="maq-burger"[^>]*>\s*<svg/.test(tel)) {
			erreurs.push(
				"le bouton du menu téléphone n'est pas dessiné (un caractère ne s'imprime pas pareil, et ne s'explique pas)",
			);
		}
		//  ⚠️ L'attribut ENTIER, pas la sous-chaîne : `maq-explication-icone` la
		//  contient, et le contrôle restait vert sur une explication supprimée dont
		//  il ne subsistait que l'icône. Trouvé en éprouvant le contrôle, pas en le
		//  relisant.
		if (!tel.includes('class="maq-explication"')) {
			erreurs.push(
				'le bouton du menu téléphone est montré sans être expliqué (`.maq-explication` dans sa figure)',
			);
		}
	}
}

if (erreurs.length > 0) {
	console.error('✗ Le manuel et le code ne disent pas la même chose des menus :');
	for (const e of erreurs) console.error(`    ${e}`);
	console.error('');
	console.error("  Une table recopiée diverge, et deux listes d'accord entre elles ne");
	console.error('  prouvent rien. Corriger le manuel, ou déclarer la nouvelle règle.');
	process.exit(1);
}

console.log(
	`✓ Manuel : ${cartes.size} écran(s) annoncé(s), ${routes.size} route(s) du site — ` +
		'tous cités, et le public annoncé est celui que Nav.svelte applique.',
);
