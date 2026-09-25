#!/usr/bin/env node
/**
 *  Les capitales d'un libellé de champ ne débordent pas sur ce qu'il enveloppe.
 *
 *  ## Pourquoi ce contrôle (#1315, 25/09/2026)
 *
 *  `champs.css` met les libellés de champ en capitales (standard du 22/09). Un
 *  `<label class="field">` qui ENVELOPPE son champ transmet ces capitales à
 *  tout son contenu : la phrase d'aide (`.aide`, 51 emplois), le texte d'une
 *  case à cocher, un bouton. Signalé à l'écran : « tout l'admin est en
 *  majuscules ». Seuls `input`, `select` et `textarea` en étaient exemptés.
 *
 *  ## Ce qu'il mesure
 *
 *  Chaque enfant d'un `label.field` est soit du LIBELLÉ (texte nu, `<span>`
 *  sans classe qui porte le texte et son étoile, `EtoileRequis`, `.sr-only`,
 *  `<strong>`/`<em>` d'insistance dans le libellé), soit REMIS EN CASSE par la
 *  règle de `champs.css` — dont la liste est LUE dans la feuille, jamais
 *  recopiée ici. Un enfant d'une troisième sorte fait échouer : il hériterait
 *  des capitales sans que personne l'ait décidé.
 *
 *  Lancer : node scripts/check-casse-libelles.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';
const FEUILLE = 'src/styles/champs.css';

/** Ce qui EST du libellé, donc garde ses capitales. */
const LIBELLE = new Set(['span', 'EtoileRequis', 'span.sr-only', 'strong', 'em', 'option']);

/** La liste `:is(...)` de la règle `label.field :is(...) { text-transform: none }`. */
export function remisEnCasse(css) {
	const m = css.match(/label\.field\s+:is\(([^)]*)\)\s*\{[^}]*text-transform:\s*none/);
	return m ? new Set(m[1].split(',').map((s) => s.trim())) : null;
}

/** Les enfants (balise ou balise.classe) des `label.field` d'une source, PUR. */
export function enfants(source) {
	const acc = [];
	//  `<\/label\s*>` : Prettier coupe la balise fermante (`</label\n>`) ; le
	//  premier jet de ce motif attendait `</label>` et lisait au-delà du libellé.
	for (const m of source.matchAll(/<label\s+class="field[^"]*"[^>]*>([\s\S]*?)<\/label\s*>/g))
		for (const t of m[1].matchAll(/<([A-Za-z][\w-]*)([^>]*)>/g)) {
			const cls = (t[2].match(/class="([^"]*)"/) ?? [])[1] ?? '';
			acc.push({ balise: t[1], classe: cls.split(/\s+/)[0] ?? '' });
		}
	return acc;
}

/** La RACINE que rend un composant — sa première balise après le script. */
export function racine(source) {
	const gabarit = source.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<!--[\s\S]*?-->/g, '');
	const t = gabarit.match(/<([a-z][\w-]*)([^>]*)>/);
	if (!t) return null;
	const cls = (t[2].match(/class="([^"]*)"/) ?? [])[1] ?? '';
	return { balise: t[1], classe: cls.split(/\s+/)[0] ?? '' };
}

/** L'enfant est-il du libellé, ou remis en casse ? Un composant se juge sur
 *  ce qu'il REND (`lireRacine`), jamais sur son nom. */
export function couvert({ balise, classe }, remis, lireRacine = () => null) {
	const cle = classe ? `${balise}.${classe}` : balise;
	if (LIBELLE.has(cle) || (!classe && LIBELLE.has(balise))) return true;
	if (/^[A-Z]/.test(balise)) {
		const r = lireRacine(balise);
		return r !== null && couvert(r, remis);
	}
	return remis.has(balise) || (classe !== '' && remis.has(`.${classe}`));
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const remis = remisEnCasse(
		'label.field :is(input, select, div, .aide, .case) { text-transform: none; }',
	);
	const t = (libelle, attendu, enfant) => {
		const r = couvert(enfant, remis);
		if (r === attendu) console.log(`PASS  ${libelle}`);
		else {
			console.error(`FAIL  ${libelle}  attendu=${attendu} obtenu=${r}`);
			ko = 1;
		}
	};
	t('aide remise en casse', true, { balise: 'span', classe: 'aide' });
	t('case remise en casse', true, { balise: 'span', classe: 'case' });
	t('texte du libellé (span nu)', true, { balise: 'span', classe: '' });
	t('étoile', true, { balise: 'EtoileRequis', classe: '' });
	t('champ', true, { balise: 'input', classe: '' });
	//  🔴 L'état d'avant #1315 : la règle n'exemptait que les champs.
	const avant = remisEnCasse('label.field :is(input, select, textarea) { text-transform: none; }');
	if (couvert({ balise: 'span', classe: 'aide' }, avant)) {
		console.error("FAIL  l'aide hors de la liste d'avant devait être refusée");
		ko = 1;
	} else console.log("PASS  l'aide est refusée par la règle d'avant");
	t('un span classé inconnu est refusé', false, { balise: 'span', classe: 'mystere' });
	t('un composant inconnu est refusé', false, { balise: 'Machin', classe: '' });
	const aide = () => racine('<script>x</script> <span class="aide">a</span>');
	if (!couvert({ balise: 'AideSource', classe: '' }, remis, aide)) {
		console.error('FAIL  un composant qui rend un .aide doit être couvert');
		ko = 1;
	} else console.log('PASS  un composant se juge sur ce qu’il rend');
	if (
		enfants('<label class="field">Nom <span class="aide">x</span></label>')[0]?.classe !== 'aide'
	) {
		console.error('FAIL  relevé des enfants');
		ko = 1;
	} else console.log('PASS  relevé des enfants');
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

const feuille = readFileSync(FEUILLE, 'utf8');
const remis = remisEnCasse(feuille);
//  Un libellé qui EST une case (`class="field case"`) : son texte est une valeur,
//  et la feuille doit le remettre en casse (#1324 — « ENVOYER LE DOCUMENT… »).
export const CASE_LIBELLE = /label\.field\.case\s*\{[^}]*text-transform:\s*none/;
if (!remis) {
	console.error(
		`\n✗ INCONNU : la règle \`label.field :is(…) { text-transform: none }\` a disparu de ${FEUILLE}.\n`,
	);
	process.exit(2);
}
function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}
function lireRacine(nom) {
	try {
		return racine(readFileSync(join(RACINE, 'lib', 'components', `${nom}.svelte`), 'utf8'));
	} catch {
		return null;
	}
}
const fautes = new Set();
let vus = 0;
for (const f of fichiers(RACINE))
	for (const enfant of enfants(readFileSync(f, 'utf8'))) {
		vus++;
		if (!couvert(enfant, remis, lireRacine))
			fautes.add(
				`${f.split(sep).join('/')}  <${enfant.balise}${enfant.classe ? ` class="${enfant.classe}"` : ''}>`,
			);
	}
const casesLibelles = fichiers(RACINE).filter((f) =>
	/<label\s+class="(?=[^"]*\bfield\b)(?=[^"]*\bcase\b)[^"]*"/.test(readFileSync(f, 'utf8')),
);
if (casesLibelles.length && !CASE_LIBELLE.test(feuille)) {
	console.error(
		`\n✗ ${casesLibelles.length} fichier(s) ont un <label class="field case">, et champs.css ` +
			'ne remet pas `label.field.case` en casse : son texte serait en capitales (#1324).\n',
	);
	for (const f of casesLibelles) console.error(`  ${f.split(sep).join('/')}`);
	process.exit(1);
}
if (vus === 0) {
	console.error('\n✗ INCONNU : aucun enfant de `label.field` relevé — la forme a changé.\n');
	process.exit(2);
}
if (fautes.size) {
	console.error(
		`\n✗ ${fautes.size} enfant(s) de label.field hériteraient des capitales du libellé :\n`,
	);
	for (const f of fautes) console.error(`  ${f}`);
	console.error(
		'\n  → l’ajouter à `label.field :is(…)` dans champs.css s’il n’est pas du libellé,\n' +
			'    ou à `LIBELLE` ici s’il l’est (#1315).\n',
	);
	process.exit(1);
}
console.log(`✓ Casse : ${vus} enfant(s) de label.field, tous du libellé ou remis en casse.`);
