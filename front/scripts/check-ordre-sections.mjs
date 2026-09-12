#!/usr/bin/env node
/**
 *  **L'ordre des sections d'un formulaire ne se décide pas par écran.**
 *
 *  ## Le défaut, signalé à l'écran le 12/09/2026
 *
 *  > « La section “Options de publication” n'est pas ordonnée de la même façon
 *  >   entre Actualité et Tickets. »
 *  > « Dans le calendrier, “Épingler dans le fil” est dans Diffusion alors que
 *  >   dans Actualités ou Tickets elle est dans Options de publication. »
 *
 *  L'ordre était arbitré depuis longtemps (`ux-patterns` §9 sexies) et
 *  `ChampsCommuns` l'imposait — **pour les sections 5 à 10 seulement**. Les deux
 *  précédentes, Options de publication et Workflow, restaient posées à la main
 *  par chaque écran : rien ne pouvait les contredire, et elles ont divergé.
 *
 *  🔴 C'est la leçon du dépôt, encore une fois : *une consigne ne se maintient
 *  pas seule, il faut un contrôle qui échoue* (`standards/05`). Une table dans
 *  une documentation décrit l'intention ; elle ne décrit pas le produit.
 *
 *  ## Ce que ce contrôle vérifie, et ce qu'il ne vérifie pas
 *
 *  Il vérifie que les sections NOMMÉES apparaissent dans un ordre **croissant**
 *  au fil du fichier. Il ne vérifie pas qu'elles sont toutes là : un sondage n'a
 *  pas de pièces jointes, une annonce n'a pas de diffusion. Le contrat est
 *  *« quand un écran a une de ces notions, elle est à la même place »*.
 *
 *  ⚠️ Les sections 1 (Titre) et 2 (champs spécifiques) ne sont **pas** classées :
 *  leurs intitulés sont propres à chaque objet — « Catégorie », « Format »,
 *  « Détails » — et les ranger demanderait une liste que personne ne tiendrait à
 *  jour. Les ignorer est le choix prudent : le contrôle ne crie que sur ce qu'il
 *  sait lire, et ce qu'il sait lire est exactement ce qui a divergé.
 *
 *  ⚠️ `<ChampsCommuns>` compte pour les sections que ses PROPS déclarent, dans
 *  l'ordre fixe du composant — et le contenu de ses `slot` est ignoré : ce sont
 *  ses sections à lui, rendues à sa place, pas celles de l'écran.
 *
 *  Lancer : npm run lint:ordre-sections
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';

/**  L'ordre arbitré — `ux-patterns` §9 sexies, révisé le 12/09/2026.
 *
 *   🔴 Ce tableau est la SOURCE : la skill le décrit, ce fichier le fait
 *   respecter. Les deux doivent rester d'accord, et c'est ce contrôle qui
 *   tranche — une documentation ne fait échouer personne. */
export const RANGS = {
	'Options de publication': 3,
	Workflow: 4,
	Périmètre: 5,
	Destinataires: 6,
	Description: 7,
	//  Une évolution parle de « Commentaire » là où une actualité parle de
	//  « Description » : même rang, même notion, deux mots (cf. `ChampsCommuns`).
	Commentaire: 7,
	Photos: 8,
	Documents: 9,
	Diffusion: 10,
};

/**  Les props de `ChampsCommuns` et le rang qu'elles activent. L'ordre du
 *   tableau est celui du composant : il REND toujours dans cet ordre-là. */
const PROPS_CHAMPS_COMMUNS = [
	['avecOptions', 3],
	['avecWorkflow', 4],
	['avecPerimetre', 5],
	['avecDestinataires', 6],
	['avecDescription', 7],
	['avecPhotos', 8],
	['avecDocuments', 9],
	['avecDiffusion', 10],
];

/**
 * Fin de la balise ouvrante commencée en `debut`.
 *
 * 🔴 Un `>` ne ferme la balise que **hors chaîne et hors expression Svelte** :
 * `on:envoyer={() => void enregistrer()}` en contient un, et le lire naïvement
 * coupait les props en deux — la moitié des `avecX` de `ChampsCommuns` n'était
 * donc pas vue, et le contrôle laissait passer le désordre qu'il existe pour
 * refuser. Vérifié en réintroduisant le défaut : il passait au vert.
 *
 * Même lecteur que `check-libelles-soumission.mjs`, pour la même raison.
 */
function finBaliseOuvrante(src, debut) {
	let profondeur = 0;
	let guillemet = null;
	for (let i = debut; i < src.length; i++) {
		const c = src[i];
		if (guillemet) {
			if (c === guillemet) guillemet = null;
		} else if (c === '"' || c === "'" || c === '`') {
			guillemet = c;
		} else if (c === '{') {
			profondeur++;
		} else if (c === '}') {
			profondeur--;
		} else if (c === '>' && profondeur === 0) {
			return i;
		}
	}
	return src.length;
}

/**  Les sections d'une source, dans l'ordre du fichier, avec leur rang.
 *
 *   PURE : c'est ce qui la rend éprouvable par `--selftest`, sans arborescence. */
export function sectionsDe(source) {
	const trouvees = [];
	//  L'élément `<ChampsCommuns …>` : on lit ses props, on saute son contenu.
	const zonesIgnorees = [];
	const reCC = /<ChampsCommuns\b/g;
	let m;
	while ((m = reCC.exec(source))) {
		const finBalise = finBaliseOuvrante(source, m.index);
		const props = source.slice(m.index, finBalise);
		for (const [prop, rang] of PROPS_CHAMPS_COMMUNS) {
			if (new RegExp(String.raw`\b${prop}\b`).test(props)) {
				trouvees.push({ position: m.index, rang, quoi: `ChampsCommuns/${prop}` });
			}
		}
		//  Auto-fermant : rien à ignorer. Sinon on saute jusqu'à la fermeture.
		const fin =
			source[finBalise - 1] === '/' ? finBalise : source.indexOf('</ChampsCommuns>', finBalise);
		zonesIgnorees.push([m.index, fin === -1 ? source.length : fin]);
	}
	const ignoree = (i) => zonesIgnorees.some(([d, f]) => i > d && i < f);

	//  La section d'options a son propre composant : son titre n'est pas écrit
	//  dans l'écran, c'est lui qui le porte.
	const reOptions = /<SectionOptionsPublication\b/g;
	while ((m = reOptions.exec(source))) {
		if (!ignoree(m.index)) {
			trouvees.push({ position: m.index, rang: 3, quoi: 'SectionOptionsPublication' });
		}
	}
	//  Les autres se reconnaissent à leur intitulé.
	const reTitre = /titre="([^"]+)"/g;
	while ((m = reTitre.exec(source))) {
		const rang = RANGS[m[1]];
		if (rang && !ignoree(m.index)) {
			trouvees.push({ position: m.index, rang, quoi: m[1] });
		}
	}
	return trouvees.sort((a, b) => a.position - b.position);
}

/**  Les paires en DÉSORDRE — une section de rang inférieur après une supérieure. */
export function desordres(sections) {
	const ecarts = [];
	let maxVu = null;
	for (const s of sections) {
		if (maxVu && s.rang < maxVu.rang) ecarts.push({ apres: maxVu, avant: s });
		if (!maxVu || s.rang > maxVu.rang) maxVu = s;
	}
	return ecarts;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (nom, src, attendu) => {
		const r = desordres(sectionsDe(src)).length;
		if (r === attendu) return;
		console.error(`  ✗ ${nom} : ${r} désordre(s), attendu ${attendu}`);
		ko++;
	};
	t(
		"l'ordre arbitré passe",
		'<SectionOptionsPublication /><SectionFormulaire titre="Workflow" /><SectionFormulaire titre="Périmètre" />',
		0,
	);
	//  🔴 LE CAS SIGNALÉ : les options après le périmètre.
	t(
		'options après périmètre',
		'<SectionFormulaire titre="Périmètre" /><SectionOptionsPublication />',
		1,
	);
	t(
		'workflow après la diffusion',
		'<SectionFormulaire titre="Diffusion" /><SectionFormulaire titre="Workflow" />',
		1,
	);
	//  `ChampsCommuns` rend DANS SON ORDRE : ses props ne se lisent pas comme
	//  l'ordre où elles sont écrites.
	t(
		'les props de ChampsCommuns sont dans son ordre à lui',
		'<ChampsCommuns avecDiffusion avecPerimetre avecOptions />',
		0,
	);
	//  Le contenu d'un slot appartient à ChampsCommuns, pas à l'écran.
	t(
		'un slot ne compte pas pour l’écran',
		'<ChampsCommuns avecOptions avecWorkflow><svelte:fragment slot="workflow">' +
			'<SectionFormulaire titre="Périmètre" /></svelte:fragment></ChampsCommuns>',
		0,
	);
	//  Un titre inconnu — « Catégorie », « Format » — n'est pas classé.
	t('un intitulé inconnu est ignoré', '<SectionFormulaire titre="Catégorie" />', 0);
	//  🔴 LE CAS QUI A RENDU CE CONTRÔLE MUET : un `=>` dans les props. Sans
	//  lecteur de balise, `avecDiffusion` n'était pas lu et le désordre passait.
	t(
		'un `=>` dans les props ne coupe pas la lecture',
		'<ChampsCommuns on:envoyer={() => void f()} avecDiffusion />' +
			'<SectionFormulaire titre="Workflow" />',
		1,
	);
	//  Cas zéro : une source sans aucune section ne doit pas passer pour conforme
	//  par hasard — c'est le lecteur qui compte les sections lues.
	if (sectionsDe('').length !== 0) {
		console.error('  ✗ une source vide rend des sections');
		ko++;
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.\n`);
		process.exit(1);
	}
	console.log('✓ Auto-test : ordre lu, désordres repérés, slots ignorés.');
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

const tous = fichiers(RACINE);
const fautifs = [];
let sectionsLues = 0;
for (const p of tous) {
	const sections = sectionsDe(readFileSync(p, 'utf8'));
	sectionsLues += sections.length;
	for (const e of desordres(sections)) {
		fautifs.push(
			`${p.split(sep).join('/')} — « ${e.avant.quoi} » (${e.avant.rang}) vient APRÈS ` +
				`« ${e.apres.quoi} » (${e.apres.rang})`,
		);
	}
}

//  🔴 Cas zéro : le relevé légitime est VIDE, donc « rien trouvé » et « rien lu »
//  se ressemblent (`standards/04` §27). Le témoin est le nombre de sections
//  LUES : sous ce plancher, le repérage ne mord plus.
//  ⬇️ Il SUIT le relevé : 54 sections lues au 12/09/2026.
const PLANCHER_SECTIONS = 45;
if (sectionsLues < PLANCHER_SECTIONS) {
	console.error(
		`\n✗ Cas zéro : ${sectionsLues} section(s) lue(s), au moins ${PLANCHER_SECTIONS} attendues —\n` +
			'  le repérage ne reconnaît plus les sections. Le contrôle ne peut pas conclure.\n',
	);
	process.exit(1);
}

if (fautifs.length) {
	console.error(`\n✗ ${fautifs.length} section(s) hors de l'ordre arbitré :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		'\n  L’ordre (`ux-patterns` §9 sexies) :\n' +
			'    1 Titre · 2 Champs spécifiques · 3 Options de publication · 4 Workflow\n' +
			'    5 Périmètre · 6 Destinataires · 7 Description · 8 Photos · 9 Documents · 10 Diffusion\n' +
			'\n  Il ne se discute pas par écran : deux formulaires qui rangent les mêmes\n' +
			'  notions différemment se lisent comme deux produits.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Ordre des sections : ${sectionsLues} section(s) lue(s) dans ${tous.length} composant(s), toutes dans l'ordre arbitré.`,
);
