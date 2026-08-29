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
const TEMOIN = 'lib/components/FormulaireTicket.svelte';

/** En dessous, le motif de lecture ne correspond plus à rien (cas zéro). */
const PLANCHER = 20;

/** Le saut de ligne, nommé : ce fichier est lu par des scripts qui le réécrivent. */
const LF = String.fromCharCode(10);

/**
 * Fichiers dispensés, avec leur raison.
 *
 * Une tolérance sans raison devient un dépotoir : chacune est nommée, et le
 * contrôle échoue si l'une cesse de servir — c'est-à-dire dès que le fichier
 * qu'elle protège devient conforme (règle posée en #374, reprise de
 * `check-pages.mjs`). Une exception qui dort laisserait repasser une vraie
 * divergence dans ce fichier sans que personne l'ait décidé.
 */
const EXCEPTIONS = {
	//  ── Hors périmètre par la RÈGLE elle-même (§9 quinquies bis) ────────────
	//  Ce ne sont pas des créations d'objet, et leur verbe métier est le bon.
	'lib/components/FormulaireCreation.svelte':
		"c'est le cadre (titre + boîte), pas un formulaire — chaque écran écrit son " +
		'propre bouton dans son <form>',
	'lib/components/ChangementMotDePasse.svelte':
		'changement de mot de passe — hors périmètre explicite de la règle',
	'routes/auth/connexion/+page.svelte': "écran d'authentification — « Se connecter »",
	'routes/auth/inscription/+page.svelte': "écran d'authentification — « Créer mon compte »",
	'routes/auth/mot-de-passe-oublie/+page.svelte':
		"écran d'authentification — « Envoyer le lien » ne crée aucun objet",
	'routes/auth/verifier-email/+page.svelte':
		"écran d'authentification — « Renvoyer » relance un e-mail déjà parti",
	//  🔴 Arbitré à l'écran le 18/08/2026 : « Créer et envoyer au CS me semble
	//  bizarre : ça doit être plutôt Générer une affiche ». Cet écran ne crée pas un
	//  objet qu'on retrouvera dans une liste — il FABRIQUE un document à imprimer,
	//  et depuis le même jour il n'envoie plus rien. Même famille que les imports,
	//  déjà hors périmètre de la règle.
	'lib/components/FormulaireAnnonceHall.svelte':
		'affiche de hall — « Générer une affiche » : on produit un document, on ne ' +
		"crée pas un objet (et l'écran n'envoie plus d'e-mail depuis le 18/08/2026)",
	//  Relance syndic : ce n'est pas un formulaire de création mais une ACTION de
	//  masse sur une sélection, et son libellé porte le compte — « Envoyer la
	//  relance (3 tickets) ». Le remplacer par « Enregistrer » ferait disparaître
	//  ce que le bouton va réellement faire, et à combien de tickets.
	//  Repéré par ce contrôle en extrayant le reporting (#453) : la rangée est
	//  passée à `.form-actions`, ce qui l'a rendue visible ici.
	'lib/components/reporting/VueRelanceSyndic.svelte':
		'envoi groupé de relances — « Envoyer la relance (N tickets) » agit sur une ' +
		'sélection existante, il ne crée aucun objet',

	//  ── RESTE À TRAITER — révélé par l'élargissement de portée (#416) ───────
	//  Ces écarts sont réels et connus. Ils ne sont PAS corrigés dans #416, dont
	//  le périmètre est `EvolForm` : les corriger au passage aurait mélangé deux
	//  lots dans le même diff. Chaque ligne dit ce qu'on lit à l'écran ; l'entrée
	//  disparaît d'elle-même quand l'écran est repris, sinon ce contrôle échoue
	//  en réclamant sa suppression.
	'routes/(app)/profil/+page.svelte':
		'« Envoyer la demande » / « Envoi… » (l. ~451) et « Je suis un nouvel arrivant » ' +
		'/ « Envoi… » (l. ~526)',
	'routes/(app)/sondages/[id]/+page.svelte': 'attente « Sauvegarde… » (l. ~328)',
	//  ⚠️ L'exception de `tickets/[id]` disait « c'est une seconde écriture
	//  d'`EvolForm`, à fusionner avant d'aligner le verbe ». La fusion a eu lieu le
	//  17/08/2026 (#431) : le formulaire de réponse écrit à la main a disparu, le
	//  geste n'a plus qu'un libellé, et le contrôle a REFUSÉ la tolérance dès
	//  qu'elle est devenue inutile.
};

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
	if (!src.includes('<FormulaireCreation')) continue;
	const ecarts = [];
	for (const [debut, fin] of blocsFormActions(src)) {
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
