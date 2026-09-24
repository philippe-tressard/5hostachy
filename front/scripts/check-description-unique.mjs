/**
 * Garde-fou : une section Description passe par `SectionDescription` — jamais un
 * `RichEditor` monté à la main sous un intitulé « Description ».
 *
 * ## Pourquoi ce contrôle existe (#1089, 24/09/2026)
 *
 * L'annonce de hall montait son texte à la main, sous l'intitulé « Message » :
 * c'était le seul formulaire à Description privé de l'assistant de rédaction
 * (#985) — celui d'une affiche lue par toute la résidence. Le composant existait,
 * et l'écran le réécrivait (`project_le_composant_existait_deja`, 9ᵉ fois).
 * En traitant ce cas, deux autres sont apparus (#1240) : ils sont déclarés
 * ci-dessous, et le contrôle échoue le jour où ils sont convertis — pour que la
 * déclaration parte avec eux.
 *
 * ## Ce qu'il lit
 *
 * Chaque `<RichEditor` hors de `SectionDescription.svelte`, et les ~600
 * caractères qui le précèdent : s'ils nomment une Description (le libellé de la
 * table, `titre="Description"`, un libellé « Description », ou l'ancien
 * « Message » de l'annonce de hall), l'éditeur est une Description réécrite.
 * Une « Réponse » de FAQ ou des « Notes » de bail ne sont pas des Descriptions
 * du cadre, et ne sont pas visées.
 *
 * Usage : npm run lint:description-unique
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const COMPOSANT = join(RACINE, 'lib', 'components', 'SectionDescription.svelte');

/** Écarts connus, avec leur raison — ou leur ticket s'ils sont une dette. Une
 *  entrée qui ne sert plus fait échouer. */
const EXCEPTIONS = {
	//  Légitime, pas une dette : le descriptif d'une page du MENU, saisi par
	//  l'administrateur, n'est pas la section Description d'un objet du cadre.
	'lib/components/OngletDescriptifPages.svelte':
		"le descriptif d'une page du menu, pas la Description d'un objet",
	'lib/components/ChampsContrat.svelte': '#1240 — la synthèse IA du contrat y atterrit, à arbitrer',
	'routes/(app)/sondages/[id]/+page.svelte':
		'#1240 — la création passe par SectionDescription, pas la correction',
};

const NOMME_UNE_DESCRIPTION =
	/SECTIONS_LIBELLE\.description|titre="(?:Description|Message)"|>\s*Description\b/;

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

const rel = (f) => relative(RACINE, f).split(sep).join('/');

//  Cas zéro : sans le composant, interdire les copies n'offrirait aucun remplaçant.
if (!/export let assistant\b/.test(readFileSync(COMPOSANT, 'utf8'))) {
	console.error("✗ Cas zéro : SectionDescription n'expose plus `assistant` — le contrat a changé.");
	process.exit(1);
}

const fautifs = new Set();
let editeurs = 0;
for (const f of fichiers(RACINE)) {
	if (f === COMPOSANT) continue;
	const src = readFileSync(f, 'utf8');
	for (const m of src.matchAll(/<RichEditor\b/g)) {
		editeurs++;
		if (NOMME_UNE_DESCRIPTION.test(src.slice(Math.max(0, m.index - 600), m.index))) {
			fautifs.add(rel(f));
		}
	}
}
if (editeurs === 0) {
	console.error(
		'✗ Cas zéro : aucun RichEditor trouvé hors du composant — la lecture ne mesure rien.',
	);
	process.exit(1);
}

const erreurs = [];
for (const f of fautifs) {
	if (!EXCEPTIONS[f]) {
		erreurs.push(`${f} : une Description montée à la main — passer par <SectionDescription>`);
	}
}
for (const f of Object.keys(EXCEPTIONS)) {
	if (!fautifs.has(f)) {
		erreurs.push(`${f} : exception déclarée qui ne sert plus (${EXCEPTIONS[f]}) — la retirer`);
	}
}
if (erreurs.length) {
	console.error(`✗ ${erreurs.length} écart(s) :\n`);
	for (const e of erreurs) console.error(`  ${e}`);
	process.exit(1);
}
console.log(
	`✓ Description : ${editeurs} éditeur(s) riche(s) lus, aucune Description réécrite ` +
		`hors des ${Object.keys(EXCEPTIONS).length} écart(s) déclaré(s).`,
);
