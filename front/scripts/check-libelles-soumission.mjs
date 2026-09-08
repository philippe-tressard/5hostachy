#!/usr/bin/env node
/**
 * Garde-fou : les formulaires soumettent tous avec le MÊME verbe, et leur bouton
 * de soumission vit dans `.form-actions`.
 *
 * Relevé au 16/08/2026 (#396) — sept formulaires, six libellés différents :
 * « Publier » / « Enregistrer brouillon » (actualité), « Envoyer la demande »
 * (ticket), « Créer le sondage », « Publier l'annonce », « Soumettre » (idée),
 * « Enregistrer » (événement, prestation) — plus « Soumettre la demande » sur
 * accès & badges, que le relevé du ticket n'avait pas vu.
 *
 * Aucun n'était faux ; l'ensemble n'avait pas de logique. Arbitré par
 * l'utilisateur le 17/08/2026 : **verbe générique partout**, donc « Enregistrer ».
 *
 * Les états d'attente divergeaient de la même façon, un cran plus bas — « Envoi… »,
 * « Enregistrement… », « Création… », et même « … » tout court. Ils sont alignés
 * ici aussi : c'est le même libellé, vu pendant la seconde où il compte le plus.
 *
 * ## Pourquoi la portée a changé le 17/08/2026 (#416)
 *
 * Ce contrôle ne regardait que `src/lib/components/Formulaire*.svelte`, « les
 * formulaires de création par convention de nommage ». La convention est bonne
 * pour un formulaire NEUF ; elle ne dit rien des formulaires qui existaient
 * avant elle. `EvolForm.svelte` — le formulaire le plus réutilisé du site, servi
 * par quatre écrans — portait DEUX jeux de libellés dans la même ligne de code
 * (« Valider » / « Envoi… » en création contre « Enregistrer » /
 * « Enregistrement… » en édition) et ce contrôle n'a rien vu : il ne s'appelle
 * pas `Formulaire…`.
 *
 * **Un contrôle dont la portée est plus étroite que la règle qu'il défend laisse
 * passer exactement les cas qu'on ne pense pas à lui donner.** La portée est
 * désormais tout `src/**\/*.svelte`, et le tri se fait sur ce que le fichier
 * REND, pas sur son nom.
 *
 * ## Ce qu'est un « bouton de soumission », structurellement
 *
 * Deux marqueurs, et seulement eux — la règle §9 quinquies impose déjà le
 * second, ce qui rend la définition vérifiable au lieu d'interprétable :
 *
 *   1. `type="submit"` — sans ambiguïté ;
 *   2. un `btn-primary` À L'INTÉRIEUR d'un bloc `class="… form-actions …"`.
 *
 * Ce tri écarte les boutons d'ACTION, qui portent légitimement leur verbe métier
 * (« + Nouvelle publication », « Accepter », « Imprimer / PDF », « Voter ») : ce
 * ne sont pas des soumissions de formulaire. Un contrôle qui crie sur du
 * légitime finit désarmé — c'est la leçon de `check-pages.mjs`.
 *
 * ## Les deux contrôles
 *
 *   A. §9 quinquies     — un `Formulaire*.svelte` sans AUCUN bouton de
 *                         soumission détecté a écrit le sien hors de
 *                         `.form-actions` et sans `type="submit"` : il est donc
 *                         cadré à gauche, et invisible pour le contrôle B.
 *   B. §9 quinquies bis — chaque bouton de soumission dit « Enregistrer » au
 *                         repos et « Enregistrement… » pendant l'envoi.
 *   C. §9 quinquies ter — chaque `.form-actions` porte « Annuler » AVANT son
 *                         bouton de soumission.
 *
 * ## Pourquoi le contrôle C existe (29/08/2026)
 *
 * Norme posée le 18/08/2026 sur Tickets, constatée, puis étendue : « Annuler »
 * est **à côté** d'« Enregistrer », et l'en-tête de page ne porte plus de
 * seconde commande d'annulation. Elle a été appliquée à quatre formulaires — et
 * à aucun autre. Signalé à l'écran : sur la page Prestataires, le formulaire de
 * contrat était le SEUL des cinq à n'avoir pas d'Annuler, si bien que la seule
 * façon de renoncer était le bouton flottant de l'en-tête, à l'autre bout de
 * l'écran. Deux autres rangées y mettaient Enregistrer AVANT Annuler.
 *
 * 🔴 Trois variantes sur une seule page, et le composant `FormulaireCreation`
 * documentait encore la règle d'AVANT, celle que le 18/08 a remplacée. Une
 * consigne périmée est pire qu'absente : elle légitime la divergence.
 *
 * ⚠️ L'ORDRE compte autant que la présence. Annuler à droite du bouton primaire
 * met la commande destructrice là où le pouce se pose ; et un ordre qui change
 * d'un écran à l'autre fait cliquer au mauvais endroit par mémoire du geste.
 *
 * Pourquoi un contrôle et pas une consigne : trancher n'aligne que les écrans
 * existants. C'est le SUIVANT qui réinvente — et c'est ce qui s'est produit pour
 * les en-têtes (#363) puis pour les formulaires (#367), les deux fois trouvé par
 * un contrôle et non par la relecture.
 *
 * Usage : npm run lint:soumission   (exit 1 si violation)
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';

import { baliseFermante } from './lib-lecture-source.mjs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = join(RACINE, 'src');
const COMPOSANTS = join(SOURCE, 'lib', 'components');

/** Le libellé unique, et son état d'attente. */
const LIBELLE = 'Enregistrer';
const ATTENTE = 'Enregistrement…';

/**
 * Référence canonique : ce fichier soumet avec le verbe commun depuis #396. S'il
 * disparaît du relevé, c'est la DÉTECTION qui est cassée, pas le dépôt qui est
 * devenu conforme — et le contrôle doit le dire plutôt que conclure au vert.
 */
//  🔴 LE TÉMOIN A CHANGÉ le 07/09/2026, et ce contrôle m'a forcé à le dire.
//
//  Il pointait `FormulaireTicket`, qui écrivait son bouton à la main. Depuis
//  #822, les dix-sept formulaires du produit passent par `PiedFormulaire` : le
//  libellé n'est plus DANS chacun d'eux, il est dans le composant.
//
//  Ce contrôle a crié, et il avait raison : « son absence dit que la DÉTECTION
//  est cassée, pas que le dépôt est conforme ». C'est exactement ce qui s'était
//  passé. Le témoin est donc le composant lui-même.
const TEMOIN = 'lib/components/PiedFormulaire.svelte';

/** En dessous, le motif de lecture ne correspond plus à rien (cas zéro). */
//  ⚠️ ABAISSÉ de 20 à 8 le 07/09/2026 : dix-sept boutons de soumission ont
//  quitté leurs fichiers pour `PiedFormulaire`. Le plancher mesure ce qui RESTE
//  écrit à la main — moins il y en a, mieux c'est, et c'est le seul cas où le
//  baisser n'est pas un rabotage : la population a réellement changé.
const PLANCHER = 8;

/** Le saut de ligne, nommé : ce fichier est lu par des scripts qui le réécrivent. */
const LF = String.fromCharCode(10);

//  Les exceptions vivent à côté : elles bougent à chaque écran repris, la
//  détection presque jamais. Deux rythmes, deux fichiers (07/09/2026).
import { EXCEPTIONS } from './check-libelles-soumission.regles.mjs';

function abandonner(message) {
	//  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.
	console.error(`\n✗ ${message}\n`);
	process.exit(1);
}

// ── Lecture du balisage ──────────────────────────────────────────────────────

/**
 * Fin de la balise ouvrante commencée en `debut`. Un `>` ne ferme la balise que
 * hors chaîne et hors expression Svelte : `on:click={() => saveEdit(t)}` en
 * contient un, et le lire naïvement coupait le bouton en deux — le libellé
 * passait alors pour un attribut, et le contrôle concluait « aucun libellé
 * lisible » sur des boutons parfaitement corrects.
 */
function finBaliseOuvrante(src, debut) {
	let profondeur = 0;
	let guillemet = null;
	for (let i = debut; i < src.length; i++) {
		const c = src[i];
		if (guillemet) {
			if (c === guillemet) guillemet = null;
		} else if (c === '"' || c === "'") {
			guillemet = c;
		} else if (c === '{') {
			profondeur++;
		} else if (c === '}') {
			profondeur--;
		} else if (c === '>' && profondeur === 0) {
			return i;
		}
	}
	return -1;
}

/** Les zones `<FormulaireCreation …>` / `<CadreFormulaire …>` et leur contenu.
 *
 * 🔴 DEUX défauts corrigés le 06/09/2026, tous deux invisibles :
 *  1. le contrôle C disait « rendus dans un <FormulaireCreation> » et lisait le
 *     fichier ENTIER — il a sorti un panneau de réglages légitime dès qu'`admin`
 *     a porté les deux ; un panneau qu'on quitte n'a rien à annuler ;
 *  2. il ignorait `CadreFormulaire` : les huit formulaires factorisés le 02/09
 *     étaient sortis de son champ sans que rien ne le dise (vérifié).
 */
function zonesFormulaireCreation(src) {
	const zones = [];
	//  ⚠️ Faux vert par RÉTRÉCISSEMENT — cf. en-tête de `zonesFormulaireCreation`.
	const ouvrant = /<(FormulaireCreation|CadreFormulaire)\b[^>]*>/g;
	let m;
	while ((m = ouvrant.exec(src))) {
		//  Auto-fermant (`<FormulaireCreation … />`) : pas de contenu à examiner.
		if (m[0].endsWith('/>')) continue;
		const fermant = src.indexOf(`</${m[1]}>`, m.index);
		zones.push([m.index, fermant === -1 ? src.length : fermant]);
	}
	return zones;
}

/** Les blocs `<div class="… form-actions …">…</div>`, imbrication comprise. */
function blocsFormActions(src) {
	const zones = [];
	const debut = /<div\b[^>]*class="[^"]*\bform-actions\b[^"]*"[^>]*>/g;
	let m;
	while ((m = debut.exec(src))) {
		let profondeur = 1;
		let fin = m.index + m[0].length;
		//  Même raison : `</div>` peut être coupé par le formatage.
		const jetons = /<div\b|<\/div\s*>/g;
		jetons.lastIndex = fin;
		let j;
		while (profondeur > 0 && (j = jetons.exec(src))) {
			profondeur += j[0].startsWith('</') ? -1 : 1;
			fin = jetons.lastIndex;
		}
		zones.push([m.index, fin]);
	}
	return zones;
}

/** Les boutons de soumission d'un fichier : `[{ ligne, contenu }]`. */
function boutonsDeSoumission(src) {
	const zones = blocsFormActions(src);
	const trouves = [];
	const ouverture = /<button\b/g;
	let m;
	while ((m = ouverture.exec(src))) {
		const finOuvrante = finBaliseOuvrante(src, m.index);
		if (finOuvrante < 0) continue;
		//  ⚠️ `indexOf('</button>')` supposait la balise fermante D'UN SEUL
		//  TENANT. Prettier écrit `</button` puis `>` à la ligne quand l'ouvrante
		//  déborde, et ce contrôle annonçait alors « aucun bouton repérable » (#419).
		const fermante = baliseFermante(src, 'button', finOuvrante);
		if (!fermante) continue;
		const finContenu = fermante.debut;
		const balise = src.slice(m.index, finOuvrante + 1);
		const submit = /type=["']submit["']/.test(balise);
		const primaireDansActions =
			/class="[^"]*\bbtn-primary\b/.test(balise) &&
			zones.some(([a, z]) => m.index >= a && m.index < z);
		if (!submit && !primaireDansActions) continue;
		trouves.push({
			ligne: src.slice(0, m.index).split('\n').length,
			contenu: src.slice(finOuvrante + 1, finContenu),
		});
	}
	return trouves;
}

/**
 * Les libellés lisibles du contenu d'un bouton : le texte littéral d'une part,
 * les chaînes des expressions Svelte de l'autre.
 *
 * ⚠️ Les chaînes ne sont lues QUE dans les expressions `{…}`. Les attributs des
 * balises imbriquées (`<span class="spinner" aria-hidden="true">`) sont entre
 * guillemets eux aussi, et les lire ferait échouer le contrôle sur sa propre
 * imprécision — constaté au premier essai de #396, où il reprochait « submit »
 * à deux formulaires corrects.
 */
function libellesDuBouton(contenu) {
	let litteral = '';
	const expressions = [];
	let profondeur = 0;
	let courante = '';
	for (const c of contenu) {
		if (c === '{') {
			profondeur++;
			if (profondeur === 1) {
				courante = '';
				continue;
			}
		} else if (c === '}') {
			profondeur--;
			if (profondeur === 0) {
				expressions.push(courante);
				continue;
			}
		}
		if (profondeur > 0) courante += c;
		else litteral += c;
	}

	const libelles = [];
	const texte = litteral
		.replace(/<[^>]*>/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
	if (/[A-Za-zÀ-ÿ]/.test(texte)) libelles.push(texte);

	const chaine = /'((?:[^'\\]|\\.){2,})'|"((?:[^"\\]|\\.){2,})"|`((?:[^`\\]|\\.){2,})`/g;
	for (const expr of expressions) {
		for (const s of expr.matchAll(chaine)) {
			const t = (s[1] ?? s[2] ?? s[3]).replace(/\\(.)/g, '$1').trim();
			if (/[A-Za-zÀ-ÿ]/.test(t)) libelles.push(t);
		}
	}
	return libelles;
}

function fichiersSvelte(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiersSvelte(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

// ── Cas zéro ─────────────────────────────────────────────────────────────────
for (const [chemin, quoi] of [
	[SOURCE, 'src'],
	[COMPOSANTS, 'src/lib/components'],
]) {
	if (!existsSync(chemin)) {
		abandonner(
			`${quoi} est introuvable — l'arborescence a changé.` +
				`\n  Ce contrôle ne sait plus où regarder : il ne peut pas conclure.`,
		);
	}
}

const tous = fichiersSvelte(SOURCE);
if (tous.length === 0) abandonner("aucun fichier .svelte analysé — l'arborescence a changé.");

// ── Relevé ───────────────────────────────────────────────────────────────────
const releve = new Map(); // chemin relatif → boutons de soumission
for (const chemin of tous) {
	const rel = relative(SOURCE, chemin).split(sep).join('/');
	const boutons = boutonsDeSoumission(readFileSync(chemin, 'utf-8'));
	if (boutons.length > 0) releve.set(rel, boutons);
}

const nbBoutons = [...releve.values()].reduce((n, b) => n + b.length, 0);
if (nbBoutons < PLANCHER) {
	abandonner(
		`${nbBoutons} bouton(s) de soumission détecté(s) sur ${tous.length} fichiers,` +
			`\n  au moins ${PLANCHER} attendus. Le motif de lecture ne correspond plus au` +
			`\n  balisage — le contrôle ne mesure plus rien et conclurait au vert.`,
	);
}
if (!releve.has(TEMOIN)) {
	abandonner(
		`${TEMOIN} n'apparaît plus dans le relevé.` +
			`\n  Ce fichier soumet avec le verbe commun depuis #396 : son absence dit que la` +
			`\n  DÉTECTION est cassée, pas que le dépôt est conforme.`,
	);
}

// ── Contrôles ────────────────────────────────────────────────────────────────
const fautifs = [];
const exceptionsUtiles = new Set();

/** A. §9 quinquies — un formulaire de création sans bouton de soumission repérable. */
for (const nom of readdirSync(COMPOSANTS)) {
	if (!nom.startsWith('Formulaire') || !nom.endsWith('.svelte')) continue;
	const rel = `lib/components/${nom}`;
	if (releve.has(rel)) continue;
	//  🔴 Un appel à `PiedFormulaire` EST un bouton de soumission (#822) : le
	//  formulaire ne l'écrit plus, il le monte. Sans cette ligne, les dix-sept
	//  formulaires convertis seraient signalés « sans bouton repérable » — le
	//  contrôle reprocherait la factorisation qu'il a lui-même rendue possible.
	//  🔴 ÉLARGI le 08/09/2026 (#852) : deux formes de délégation, une seule
	//  notion — « ce formulaire ne rédige pas son pied, il en hérite ».
	//
	//    • `<PiedFormulaire>` — le pied commun, monté directement (#822) ;
	//    • `<Formulaire…>`    — un formulaire qui en ENVELOPPE un autre, et
	//      hérite donc du sien. `FormulaireEditionDocument` est le premier.
	//
	//  ⚠️ La version d'avant ne connaissait que la première et signalait la
	//  seconde « sans bouton repérable ». C'est `standards/04` §40 : la portée
	//  d'un contrôle décrit la NOTION, jamais la forme déjà rencontrée. La
	//  déclarer en exception aurait rangé une conformité parmi les dérogations.
	const source = readFileSync(join(COMPOSANTS, nom), 'utf-8');
	if (/<PiedFormulaire\b/.test(source)) continue;
	if (/<Formulaire[A-Z]\w*\b/.test(source)) continue;
	if (EXCEPTIONS[rel]) {
		exceptionsUtiles.add(rel);
		continue;
	}
	fautifs.push(
		`  ${rel}\n      aucun bouton de soumission repérable — il est écrit hors de` +
			`\n      .form-actions ET sans type="submit", donc cadré à gauche et invisible` +
			`\n      pour ce contrôle (ux-patterns §9 quinquies)`,
	);
}

/** B. §9 quinquies bis — le verbe commun, au repos comme pendant l'envoi. */
for (const [rel, boutons] of releve) {
	const ecarts = [];
	for (const { ligne, contenu } of boutons) {
		const libelles = libellesDuBouton(contenu);
		if (libelles.length === 0) {
			ecarts.push(`l. ${ligne} : aucun libellé lisible — contrôle impossible`);
			continue;
		}
		const inattendus = libelles.filter((t) => t !== LIBELLE && t !== ATTENTE);
		if (inattendus.length > 0) {
			ecarts.push(`l. ${ligne} : ${inattendus.map((t) => `« ${t} »`).join(', ')}`);
		}
	}
	if (ecarts.length === 0) continue;
	if (EXCEPTIONS[rel]) {
		exceptionsUtiles.add(rel);
		continue;
	}
	fautifs.push(
		`  ${rel}\n      ${ecarts.join('\n      ')}` +
			`\n      attendu : « ${LIBELLE} » et « ${ATTENTE} »`,
	);
}

/** C. §9 quinquies ter — « Annuler » à côté de la soumission, et AVANT elle.
 *
 * ⚠️ PORTÉE : les formulaires qui S'OUVRENT, c'est-à-dire ceux rendus dans un
 * `<FormulaireCreation>`. Un panneau de réglages affiché en permanence — SMTP,
 * WhatsApp, sauvegarde, préférences d'affichage — n'a rien à annuler : on le
 * quitte, on ne le referme pas. La première version de ce contrôle les visait
 * aussi et sortait neuf fichiers, dont six légitimes. **Un contrôle qui crie sur
 * du légitime finit désarmé** — c'est la leçon rappelée en tête de ce fichier,
 * et elle vaut pour le contrôle qu'on vient d'écrire.
 */
for (const rel of releve.keys()) {
	const src = readFileSync(join(SOURCE, rel), 'utf8');
	const zones = zonesFormulaireCreation(src);
	if (zones.length === 0) continue;
	const ecarts = [];
	for (const [debut, fin] of blocsFormActions(src)) {
		//  🔒 Seulement les rangées DANS un formulaire qui s'ouvre (cf. plus haut).
		if (!zones.some(([d, f]) => debut >= d && debut < f)) continue;
		const bloc = src.slice(debut, fin);
		const ligne = src.slice(0, debut).split(LF).length;
		const posSoumission = bloc.indexOf('btn-primary');
		//  Une rangée sans bouton primaire n'est pas une rangée de soumission
		//  (barre d'outils, actions d'une carte) : rien à exiger d'elle.
		if (posSoumission === -1) continue;
		const posAnnuler = bloc.indexOf('>Annuler<');
		if (posAnnuler === -1) {
			ecarts.push(`l. ${ligne} : pas de bouton « Annuler » à côté d'« Enregistrer »`);
		} else if (posAnnuler > posSoumission) {
			ecarts.push(`l. ${ligne} : « Annuler » est APRÈS « Enregistrer » — il vient avant`);
		}
	}
	if (ecarts.length === 0) continue;
	if (EXCEPTIONS[rel]) {
		exceptionsUtiles.add(rel);
		continue;
	}
	fautifs.push('  ' + rel + LF + '      ' + ecarts.join(LF + '      '));
}

if (fautifs.length > 0) {
	console.error(
		`\n✗ ${fautifs.length} fichier(s) ne soumettent pas avec le verbe commun :\n\n` +
			fautifs.join('\n') +
			`\n\n  Règle arbitrée le 17/08/2026 (#396) : verbe GÉNÉRIQUE partout.` +
			`\n  Sept formulaires portaient six libellés différents — aucun faux, l'ensemble` +
			`\n  sans logique. Le verbe métier (« Publier », « Soumettre », « Créer le… »)` +
			`\n  se décide une fois pour toutes, pas écran par écran.` +
			`\n\n  Une exception réelle se déclare dans EXCEPTIONS, avec sa raison.\n`,
	);
	process.exit(1);
}

const inutiles = Object.keys(EXCEPTIONS).filter((rel) => !exceptionsUtiles.has(rel));
if (inutiles.length > 0) {
	console.error(
		`\n✗ ${inutiles.length} exception(s) ne servent plus :\n\n` +
			inutiles.map((f) => `  ${f} — « ${EXCEPTIONS[f]} »`).join('\n') +
			`\n\n  Le fichier a disparu, n'a plus de bouton de soumission, ou est devenu` +
			`\n  conforme. Retirer l'exception : reconduite « au cas où », elle protège un` +
			`\n  écran qui n'en a plus besoin et masque la prochaine vraie divergence.\n`,
	);
	process.exit(1);
}

console.log(
	`✓ ${nbBoutons} bouton(s) de soumission dans ${releve.size} fichier(s) disent tous ` +
		`« ${LIBELLE} » / « ${ATTENTE} » (${Object.keys(EXCEPTIONS).length} exceptions nommées).`,
);
