#!/usr/bin/env node
/**
 * Garde-fou : les formulaires de création soumettent tous avec le MÊME verbe.
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
 * Pourquoi un contrôle et pas une consigne : trancher n'aligne que les écrans
 * existants. C'est le SUIVANT qui réinvente — et c'est ce qui s'est produit pour
 * les en-têtes (#363) puis pour les formulaires (#367), les deux fois trouvé par
 * un contrôle et non par la relecture.
 *
 * Périmètre : `src/lib/components/Formulaire*.svelte`, les formulaires de création
 * par convention de nommage. Un nouveau formulaire suit cette convention, donc ce
 * contrôle le voit sans qu'on ait à l'inscrire quelque part.
 *
 * Hors périmètre volontairement : les écrans d'authentification (« Se connecter »,
 * « Créer mon compte »), les imports (« Importer ») et le changement de mot de
 * passe. Ce ne sont pas des créations d'objet, et leur verbe métier est le bon.
 *
 * Usage : npm run lint:soumission   (exit 1 si violation)
 */
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const COMPOSANTS = join(RACINE, 'src', 'lib', 'components');

/** Le libellé unique, et son état d'attente. */
const LIBELLE = 'Enregistrer';
const ATTENTE = 'Enregistrement…';

/**
 * Formulaires dispensés, avec leur raison.
 *
 * Une tolérance sans raison devient un dépotoir : chacune est nommée, et le
 * contrôle échoue si l'une cesse de servir (règle posée en #374).
 */
const EXCEPTIONS = {
	//  Enveloppe (titre + cadre) : elle ne porte aucun bouton de soumission,
	//  chaque écran écrit le sien dans son `<form>`.
	'FormulaireCreation.svelte': "c'est le cadre, pas un formulaire — aucun bouton de soumission",
};

function abandonner(message) {
	//  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.
	console.error(`\n✗ ${message}\n`);
	process.exit(1);
}

if (!existsSync(COMPOSANTS)) {
	abandonner(
		`${relative(RACINE, COMPOSANTS)} est introuvable — l'arborescence a changé.` +
			`\n  Ce contrôle ne sait plus où regarder : il ne peut pas conclure.`,
	);
}

const formulaires = readdirSync(COMPOSANTS).filter(
	(f) => f.startsWith('Formulaire') && f.endsWith('.svelte'),
);

//  ── Cas zéro ────────────────────────────────────────────────────────────────
//  Sans lui, un renommage de la convention viderait la liste et le contrôle
//  annoncerait « tout est conforme » sur zéro fichier analysé.
if (formulaires.length < 2) {
	abandonner(
		`${formulaires.length} composant(s) « Formulaire*.svelte » trouvé(s) — la convention` +
			`\n  de nommage a changé. Le contrôle porterait sur rien et conclurait au vert :` +
			`\n  mettre à jour son périmètre.`,
	);
}

const fautifs = [];
const exceptionsUtiles = new Set();

for (const nom of formulaires) {
	if (EXCEPTIONS[nom]) {
		exceptionsUtiles.add(nom);
		continue;
	}
	const src = readFileSync(join(COMPOSANTS, nom), 'utf-8');

	//  Le bouton primaire vit dans `.form-actions` (ux-patterns §9 quinquies).
	const bloc = src.match(/<div class="form-actions">([\s\S]*?)<\/div>/);
	if (!bloc) {
		fautifs.push(
			`  ${nom}\n      aucun bloc .form-actions — le bouton de soumission est écrit hors` +
				`\n      du conteneur commun, donc cadré à gauche (ux-patterns §9 quinquies)`,
		);
		continue;
	}

	//  Le CONTENU des boutons, jamais leurs attributs : `type="submit"` et
	//  `class="btn btn-primary"` sont des chaînes entre guillemets eux aussi, et
	//  les lire ferait échouer le contrôle sur sa propre imprécision (constaté au
	//  premier essai — il reprochait « submit » à deux formulaires corrects).
	const contenus = [...bloc[1].matchAll(/<button\b[^>]*>([\s\S]*?)<\/button>/g)].map((m) => m[1]);
	if (contenus.length === 0) {
		fautifs.push(`  ${nom}\n      bloc .form-actions sans <button> — contrôle impossible`);
		continue;
	}
	const libelles = contenus
		.flatMap((c) => [...c.matchAll(/'([^']{2,})'|"([^"]{2,})"/g)].map((m) => m[1] ?? m[2]))
		.filter((t) => /[A-Za-zÀ-ÿ]/.test(t));

	if (libelles.length === 0) {
		fautifs.push(`  ${nom}\n      bloc .form-actions sans libellé lisible — contrôle impossible`);
		continue;
	}

	const inattendus = libelles.filter((t) => t !== LIBELLE && t !== ATTENTE);
	if (inattendus.length > 0) {
		fautifs.push(
			`  ${nom}\n      ${inattendus.map((t) => `« ${t} »`).join(', ')}` +
				`\n      attendu : « ${LIBELLE} » et « ${ATTENTE} »`,
		);
	}
}

if (fautifs.length > 0) {
	console.error(
		`\n✗ ${fautifs.length} formulaire(s) de création ne soumettent pas avec le verbe commun :\n\n` +
			fautifs.join('\n') +
			`\n\n  Règle arbitrée le 17/08/2026 (#396) : verbe GÉNÉRIQUE partout.` +
			`\n  Sept formulaires portaient six libellés différents — aucun faux, l'ensemble` +
			`\n  sans logique. Le verbe métier (« Publier », « Soumettre », « Créer le… »)` +
			`\n  se décide une fois pour toutes, pas écran par écran.` +
			`\n\n  Une exception réelle se déclare dans EXCEPTIONS, avec sa raison.\n`,
	);
	process.exit(1);
}

const inutiles = Object.keys(EXCEPTIONS).filter((f) => !exceptionsUtiles.has(f));
if (inutiles.length > 0) {
	console.error(
		`\n✗ ${inutiles.length} exception(s) ne servent plus :\n\n` +
			inutiles.map((f) => `  ${f} — « ${EXCEPTIONS[f]} »`).join('\n') +
			`\n\n  Le fichier a disparu ou a été renommé. Retirer l'exception : reconduite` +
			`\n  « au cas où », elle protège un écran qui n'existe plus et masque son` +
			`\n  remplaçant.\n`,
	);
	process.exit(1);
}

console.log(
	`✓ ${formulaires.length - exceptionsUtiles.size} formulaire(s) de création soumettent tous ` +
		`avec « ${LIBELLE} » / « ${ATTENTE} ».`,
);
