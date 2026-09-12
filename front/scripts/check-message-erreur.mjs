#!/usr/bin/env node
/**
 *  Le message d'erreur d'un appel API vient de `messageErreur`, pas d'un ternaire
 *  recopié.
 *
 *  ## Le relevé du 12/09/2026
 *
 *  `e instanceof ApiError ? e.message : 'Erreur'` est écrit **127 fois dans 41
 *  fichiers**. Quatre-vingt-deux de ces copies retombent sur le mot « Erreur ».
 *
 *  🔴 Ce n'est pas une duplication cosmétique : c'est **la même information
 *  perdue 82 fois**. `$lib/erreurs.messageErreur` sait dire :
 *
 *    401 → « Votre session a expiré — rechargez la page pour vous reconnecter. »
 *    403 → le message du serveur, ou « Vous n'avez pas accès à cette rubrique. »
 *    réseau → « Impossible de joindre le serveur — vérifiez votre connexion. »
 *
 *  Le ternaire, lui, affiche « Erreur » dès que l'erreur n'est pas une réponse
 *  HTTP — c'est-à-dire exactement quand l'utilisateur aurait besoin qu'on lui
 *  dise que sa connexion est coupée.
 *
 *  ⚠️ Et la duplication avait déjà produit sa divergence : `messageErreur`
 *  existait **en DEUX exemplaires**, dans `$lib/erreurs` et dans `$lib/comptes`,
 *  sous le même nom et avec des comportements différents. Deux écrans
 *  importaient la moins disante.
 *
 *  ## Pourquoi un PLAFOND et non une interdiction
 *
 *  Cent vingt-trois occurrences subsistent. Les convertir d'un coup toucherait
 *  43 fichiers dans un seul lot, sans qu'aucun écran ne soit regardé : c'est le
 *  genre de changement massif que ce dépôt a appris à ne pas faire.
 *
 *  Le plafond empêche la **cent vingt-quatrième**, et il DESCEND à mesure qu'on
 *  convertit — un plafond qu'on ne baisse pas est un plafond qu'on oublie.
 *
 *  Lancer : node scripts/check-message-erreur.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';

/**  Le plafond, à baisser à chaque conversion. Il ne remonte jamais. */
//  123 → 119 le 12/09/2026 : quatre copies converties en migrant `mon-lot`
//  vers `tenter` (#928). Le contrôle a EXIGÉ cette baisse — il échoue aussi
//  quand le compte descend sous le plafond, et c'est ce qui l'empêche de
//  devenir un plafond qu'on oublie.
const PLAFOND = 119;

/**  Le ternaire recopié : `<e> instanceof ApiError ? <e>.message : …`.
 *   La rétro-référence `\1` exige la MÊME variable des deux côtés — sans elle,
 *   un test légitime sur deux erreurs distinctes serait compté à tort. */
const TERNAIRE = /(\w+) instanceof ApiError \? \1\.message/g;

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte') || e.endsWith('.ts')) acc.push(p);
	}
	return acc;
}

/**  La décision, PURE — combien de copies dans cette source ? */
export function compterCopies(source) {
	return (source.match(TERNAIRE) ?? []).length;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const r = compterCopies(src);
		if (r === attendu) console.log(`PASS  ${libelle} → ${r}`);
		else {
			console.error(`FAIL  ${libelle}  attendu=${attendu} obtenu=${r}`);
			ko = 1;
		}
	};
	t('la copie type', 1, "toast('error', e instanceof ApiError ? e.message : 'Erreur');");
	t(
		'deux copies',
		2,
		'a instanceof ApiError ? a.message : 1; b instanceof ApiError ? b.message : 2;',
	);
	t('appel conforme', 0, "toast('error', messageErreur(e));");
	//  ⚠️ DEUX variables différentes : ce n'est pas la copie, c'est un test sur
	//  une autre erreur. La rétro-référence l'exclut, et c'est le faux positif
	//  que trois contrôles de ce dépôt ont déjà rencontré.
	t('variables différentes', 0, 'e instanceof ApiError ? autre.message : 0');
	//  Le cas zéro : une source vide ne compte rien, et ne prétend rien.
	t('source vide', 0, '');
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

const tous = fichiers(RACINE);
let total = 0;
let lus = 0;
const parFichier = [];

for (const f of tous) {
	lus++;
	const n = compterCopies(readFileSync(f, 'utf8'));
	if (!n) continue;
	total += n;
	parFichier.push([
		f
			.split(sep)
			.join('/')
			.replace(/^src\//, ''),
		n,
	]);
}

//  🔴 LE CAS ZÉRO (`standards/04` §2) : si aucun fichier n'a été lu, le contrôle
//  n'a pas mesuré — il ne rend pas OK. Un `0` sur zéro fichier lu serait le
//  meilleur résultat possible, et le plus faux.
if (lus === 0) {
	console.error('\n✗ INCONNU : aucun fichier lu sous `src/`. Le contrôle ne mesure rien.\n');
	process.exit(2);
}

if (total > PLAFOND) {
	console.error(
		`\n✗ ${total} copies du ternaire, plafond ${PLAFOND} — ${total - PLAFOND} de trop :\n`,
	);
	for (const [f, n] of parFichier.sort((a, b) => b[1] - a[1]).slice(0, 10)) {
		console.error(`  ${n}x  ${f}`);
	}
	console.error(
		'\n  `messageErreur(e)` de `$lib/erreurs` dit ce que le ternaire tait : une\n' +
			'  session expirée, un serveur injoignable. Il accepte un repli contextuel\n' +
			'  en second argument : `messageErreur(e, "Impossible de charger vos lots")`.\n' +
			'  → convertir, ou baisser le plafond si une conversion a eu lieu ailleurs.\n',
	);
	process.exit(1);
}

if (total < PLAFOND) {
	console.error(
		`\n✗ ${total} copies restantes, mais le plafond est à ${PLAFOND}.\n\n` +
			`  Des conversions ont eu lieu : baisser PLAFOND à ${total}.\n` +
			"  Un plafond qu'on ne baisse pas est un plafond qu'on oublie — et il\n" +
			'  laisserait revenir en silence ce qui vient d’être retiré.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Message d'erreur : ${total} copie(s) du ternaire, plafond ${PLAFOND} tenu ` +
		`(${lus} fichier(s) lus) — dette suivie, elle ne grandit plus.`,
);
