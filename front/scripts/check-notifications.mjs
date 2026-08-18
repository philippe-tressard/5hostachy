/**
 * Garde-fou : les canaux de notification ne se redessinent pas à la main.
 *
 * POURQUOI. Les trois cases « groupe WhatsApp / syndic / conseil syndical »
 * étaient écrites à la main dans SIX formulaires. Elles avaient divergé
 * exactement comme le prévoit `standards/02-factorisation.md` §2 : deux tracés
 * SVG WhatsApp différents, trois libellés, deux icônes d'e-mail — et un écran
 * où le canal WhatsApp manquait purement et simplement (création d'un ticket).
 * Personne ne l'a vu pendant des mois, parce qu'un écran qui n'affiche PAS une
 * option ressemble à un écran normal.
 *
 * Regrouper dans `CanauxNotification.svelte` ne suffit pas : rien n'empêche le
 * prochain formulaire de recopier trois `<input type="checkbox">`. Ce contrôle
 * échoue en CI si c'est le cas.
 *
 * DEUX RÈGLES :
 *   1. `bind:checked` sur une variable de canal (`partager_whatsapp`,
 *      `envoyer_syndic`, `envoyer_cs`, et leurs équivalents camelCase) n'est
 *      permis que dans `CanauxNotification.svelte`.
 *   2. Le tracé SVG de la marque WhatsApp n'est permis que dans `Icon.svelte`.
 *
 * Le contrôle s'auto-contrôle : s'il n'analyse aucun fichier, ou s'il ne trouve
 * plus le composant partagé ni un seul de ses usages, il ÉCHOUE au lieu de
 * conclure au vert (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const COMPOSANT = 'lib/components/CanauxNotification.svelte';
const ICONE = 'lib/components/Icon.svelte';

/** Variables de canal, dans les deux conventions de nommage du dépôt. */
const CANAUX = [
	'partager_whatsapp',
	'partagerWhatsapp',
	'envoyer_syndic',
	'envoyerSyndic',
	'envoyer_cs',
	'envoyerCs',
	'destinataireSyndic',
	'destinataireCs',
];
const CASE_DE_CANAL = new RegExp(
	`bind:checked=\\{[^}]*\\b(${CANAUX.join('|')})\\b`,
	'g',
);
/**
 * Les écrans qui écrivent LÉGITIMEMENT une case de canal à la main, avec leur
 * raison — comme `lint:soumission` et `lint:styles` le font déjà.
 *
 * ⚠️ Ce mécanisme n'existait pas : le contrôle refusait toute case hors du
 * composant, sans recours. Un garde-fou sans exception déclarable pousse à le
 * contourner — ici, il aurait suffi de renommer la variable pour lui échapper, ce
 * qui est bien pire qu'une entrée écrite noir sur blanc.
 *
 * Une exception se JUSTIFIE, sinon elle ne sert qu'à se taire.
 */
const EXCEPTIONS = {
	'lib/components/FormulaireAnnonceHall.svelte':
		"affiche de hall : UN seul canal, et c'est un envoi INTERNE — le conseil " +
		"syndical reçoit le PDF pour l'imprimer. `CanauxNotification` sert la " +
		'diffusion EXTERNE (WhatsApp, syndic, CS) et ne sait pas masquer un canal ; ' +
		"l'utiliser ici ouvrirait deux cases que le serveur n'accepte pas — ce que le " +
		'cadre #430 interdit explicitement (vérifier que le serveur CONSOMME avant ' +
		"d'ouvrir un champ).",
};

/** Deux fragments distinctifs, un par tracé WhatsApp trouvé dans l'historique. */
const TRACES_WHATSAPP = ['M17.472 14.382', 'M12 2C6.477 2 2 6.237'];

function fichiers(dossier) {
	const trouves = [];
	for (const entree of readdirSync(dossier)) {
		const chemin = join(dossier, entree);
		if (statSync(chemin).isDirectory()) trouves.push(...fichiers(chemin));
		else if (/\.(svelte|ts|js)$/.test(entree)) trouves.push(chemin);
	}
	return trouves;
}

const tous = fichiers(RACINE);
const fautes = [];
let usagesDuComposant = 0;
let composantPresent = false;

for (const chemin of tous) {
	//  Normalisé en `/` : sur Windows, `relative()` rend des `\`, et une clé
	//  d'exception écrite avec des `/` ne correspondrait jamais — l'exception
	//  serait ignorée en silence, ce qui est le pire des deux mondes.
	const rel = relative(RACINE, chemin).split(sep).join('/');
	const source = readFileSync(chemin, 'utf8');

	if (rel === COMPOSANT) {
		composantPresent = true;
		continue; // c'est LA définition : elle a le droit de tout faire
	}
	if (EXCEPTIONS[rel]) {
		//  Déclarée et justifiée : on ne la relit pas, mais on la COMPTE — voir le
		//  bilan, qui les nomme toutes.
		continue;
	}
	if (source.includes('CanauxNotification')) usagesDuComposant++;

	for (const m of source.matchAll(CASE_DE_CANAL)) {
		fautes.push(
			`${rel.split(sep).join('/')} — case « ${m[1] } » écrite à la main : ` +
				'utiliser <CanauxNotification bind:whatsapp bind:syndic bind:cs />',
		);
	}
	if (rel !== ICONE) {
		for (const trace of TRACES_WHATSAPP) {
			if (source.includes(trace)) {
				fautes.push(
					`${rel.split(sep).join('/')} — tracé SVG WhatsApp recopié : ` +
						'utiliser <Icon name="whatsapp" />',
				);
			}
		}
	}
}

//  Planchers : un contrôle qui n'a rien examiné n'est pas un contrôle vert.
if (tous.length < 50) {
	console.error(`✗ Seulement ${tous.length} fichier(s) analysé(s) — portée cassée.`);
	process.exit(2);
}
if (!composantPresent) {
	console.error(`✗ ${COMPOSANT} introuvable — le contrôle n'a plus de référence.`);
	process.exit(2);
}
if (usagesDuComposant < 5) {
	console.error(
		`✗ CanauxNotification n'est utilisé que dans ${usagesDuComposant} fichier(s) ; ` +
			'il en desservait 6 au moment du regroupement. Un écran a-t-il repris une ' +
			'écriture à la main sous une autre forme ?',
	);
	process.exit(2);
}

if (fautes.length) {
	console.error('✗ Canaux de notification réécrits hors du composant partagé :');
	for (const f of fautes) console.error(`   ${f}`);
	process.exit(1);
}

console.log(
	`✓ ${tous.length} fichiers analysés — canaux de notification centralisés ` +
		`(${usagesDuComposant} écrans servis par CanauxNotification).`,
);
