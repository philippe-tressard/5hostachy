#!/usr/bin/env node
/**
 * Le manuel dit-il, PAR PROFIL, ce que le code réserve ? (24/09/2026)
 *
 * `check-manuel-menus` vérifie qui voit une ENTRÉE du menu. Il laissait passer
 * « Tout le monde » sur Résidence, alors que son carnet d'entretien est fermé
 * aux locataires — signalé à l'écran par l'utilisateur : « les locataires n'ont
 * pas accès à tout ». Ce contrôle-ci descend d'un cran, et vérifie trois tables
 * que le manuel recopie forcément, faute de pouvoir les lire :
 *
 * 1. **Les onglets réservés** (`reserve:` dans `pages.ts`) : la carte de la page
 *    porte `data-onglet="<id>" data-reserve="<valeur>"`. Une réserve que le
 *    manuel annonce sans que `pages.ts` la porte doit être DÉCLARÉE ci-dessous,
 *    avec la ligne du code qui l'applique — et échoue si cette ligne disparaît.
 * 2. **Les treize sections d'une affaire, vues du résident** : la table du
 *    chapitre « Ouvrir une affaire » suit `SECTIONS_ORDRE`, dit « conseil » là
 *    où la déclaration `TICKET` éteint la section pour un résident, et ne dit
 *    « obligatoire » que d'une section `requis`.
 * 3. **Les catégories qu'un résident choisit** : celles de `CATEGORIES_TICKET`
 *    sans `reserveCS`, ni plus ni moins.
 *
 * Il lit des ATTRIBUTS, jamais la prose (même raison que `check-manuel-menus`).
 */
import { existsSync, readFileSync } from 'node:fs';

const RACINE = new URL('../', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const lire = (chemin) => readFileSync(`${RACINE}${chemin}`, 'utf8');

const manuel = lire('../docs/manuel-utilisateur.html');
const pages = lire('src/lib/pages.ts');
const types = lire('src/lib/entites/types.ts');
const ticket = lire('src/lib/entites/ticket.ts');
const categories = lire('src/lib/tickets-categories.ts');

const erreurs = [];

/** Les réserves que le manuel annonce et que `pages.ts` ne porte pas : la page
 *  les applique elle-même. Chacune nomme la ligne qui le prouve. */
const RESERVES_ECRITES_DANS_LA_PAGE = {
	'/mon-lot#location': {
		reserve: 'bailleur',
		fichier: 'src/routes/(app)/mon-lot/+page.svelte',
		preuve: "masques={peutGererLocation ? [] : ['location']}",
	},
};

// ── 1. Les onglets réservés ─────────────────────────────────────────────────
const cartes = new Map(
	[
		...manuel.matchAll(
			/<div class="ecran-card" data-page="([^"]+)"[\s\S]*?(?=<div class="ecran-card"|<\/section>)/g,
		),
	].map((m) => [m[1], m[0]]),
);
if (cartes.size < 5) {
	console.error(
		`✗ Cas zéro : ${cartes.size} carte(s) d'écran lue(s) dans le manuel — le motif a dérivé.`,
	);
	process.exit(1);
}

const attendues = new Map();
for (const bloc of pages.split(/^\t\{$/m)) {
	const href = bloc.match(/^\t\thref: '([^']+)',$/m)?.[1];
	if (!href) continue;
	for (const onglet of bloc.split(/^\t\t\t\{$/m)) {
		const id = onglet.match(/^\t\t\t\tid: '([^']+)',$/m)?.[1];
		const reserve = onglet.match(/^\t\t\t\treserve: '([^']+)',$/m)?.[1];
		if (id && reserve) attendues.set(`${href}#${id}`, reserve);
	}
}
if (attendues.size === 0) {
	console.error('✗ Cas zéro : aucun onglet réservé lu dans pages.ts — le motif a dérivé.');
	process.exit(1);
}

for (const [cle, reserve] of attendues) {
	const [href, id] = cle.split('#');
	const carte = cartes.get(href) ?? '';
	if (!carte.includes(`data-onglet="${id}" data-reserve="${reserve}"`)) {
		erreurs.push(
			`${cle} est réservé « ${reserve} » dans pages.ts ; la carte ${href} du manuel ne le dit pas`,
		);
	}
}
for (const [href, carte] of cartes) {
	for (const m of carte.matchAll(/data-onglet="([^"]+)" data-reserve="([^"]+)"/g)) {
		const cle = `${href}#${m[1]}`;
		if (attendues.get(cle) === m[2]) continue;
		const declaree = RESERVES_ECRITES_DANS_LA_PAGE[cle];
		if (!declaree || declaree.reserve !== m[2]) {
			erreurs.push(`le manuel annonce ${cle} réservé « ${m[2]} », et rien ne le déclare`);
		} else if (
			!existsSync(`${RACINE}${declaree.fichier}`) ||
			!lire(declaree.fichier).includes(declaree.preuve)
		) {
			erreurs.push(
				`${cle} : la preuve déclarée a disparu de ${declaree.fichier} — la réserve a-t-elle changé ?`,
			);
		}
	}
}

// ── 2. Les treize sections, vues du résident ────────────────────────────────
const ordre = [
	...types.match(/SECTIONS_ORDRE[^=]*=\s*\[([\s\S]*?)\];/)[1].matchAll(/'(\w+)'/g),
].map((m) => m[1]);
const declarations = new Map();
for (const bloc of ticket.split(/^\t\t\{$/m)) {
	const id = bloc.match(/^\t\t\tid: '(\w+)',$/m)?.[1];
	if (!id) continue;
	declarations.set(id, {
		requis: /^\t\t\trequis: true,$/m.test(bloc),
		conseil: /inactivePour: \{[^}]*?^\t\t\t\tresident:/ms.test(bloc),
	});
}
const lignes = [...manuel.matchAll(/data-section-affaire="(\w+)" data-resident="([\w-]+)"/g)].map(
	(m) => [m[1], m[2]],
);
if (ordre.length < 10 || declarations.size < 10) {
	console.error(
		`✗ Cas zéro : ${ordre.length} section(s) dans l'ordre, ${declarations.size} déclarée(s) — le motif a dérivé.`,
	);
	process.exit(1);
}
if (lignes.map(([id]) => id).join(',') !== ordre.join(',')) {
	erreurs.push(`la table des sections du manuel ne suit pas SECTIONS_ORDRE (${ordre.join(', ')})`);
}
for (const [id, pourLeResident] of lignes) {
	const d = declarations.get(id);
	if (!d) continue;
	if (d.conseil && pourLeResident !== 'conseil') {
		erreurs.push(
			`section ${id} : éteinte pour un résident dans TICKET, le manuel dit « ${pourLeResident} »`,
		);
	}
	if (pourLeResident === 'obligatoire' && !d.requis) {
		erreurs.push(`section ${id} : le manuel la dit obligatoire, TICKET ne la déclare pas requise`);
	}
}

// ── 3. Les catégories d'un résident ─────────────────────────────────────────
const tableCat = categories.slice(categories.indexOf('export const CATEGORIES_TICKET'));
const ouvertes = tableCat
	.slice(0, tableCat.indexOf('\n];'))
	.split(/\n\t\{/)
	.slice(1)
	.filter((b) => !/reserveCS: true/.test(b))
	.map((b) => b.match(/value: '(\w+)'/)?.[1])
	.filter(Boolean);
const annoncees = [...manuel.matchAll(/data-categorie="(\w+)"/g)].map((m) => m[1]);
if (ouvertes.length < 5) {
	console.error(
		`✗ Cas zéro : ${ouvertes.length} catégorie(s) ouverte(s) lue(s) — le motif a dérivé.`,
	);
	process.exit(1);
}
if ([...annoncees].sort().join(',') !== [...ouvertes].sort().join(',')) {
	erreurs.push(
		`catégories d'un résident : le manuel en annonce [${annoncees}], le code [${ouvertes}]`,
	);
}

if (erreurs.length > 0) {
	console.error(
		'✗ Le manuel et le code ne disent pas la même chose de ce que voit chaque profil :',
	);
	for (const e of erreurs) console.error(`    ${e}`);
	process.exit(1);
}
console.log(
	`✓ Manuel par profil : ${attendues.size} onglet(s) réservé(s), ${lignes.length} section(s), ` +
		`${ouvertes.length} catégorie(s) — conformes au code.`,
);
