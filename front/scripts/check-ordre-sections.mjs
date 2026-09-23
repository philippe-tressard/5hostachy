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

/**
 *  🔴 L'ordre ne s'écrit PLUS ici — il se lit dans `lib/entites/types.ts`.
 *
 *  ## Pourquoi (#1124, 21/09/2026)
 *
 *  Ce fichier portait sa propre table de rangs, et son en-tête affirmait
 *  *« ce tableau est la SOURCE »*. Il y en avait donc DEUX : celle-ci et
 *  `SECTIONS_ORDRE`. Elles ont divergé comme le dépôt l'a déjà vu quatre fois
 *  (périmètres #316, canaux, statuts #415, pages #401) :
 *
 *  | La table disait | La réalité |
 *  |---|---|
 *  | « Photos » et « Documents », deux rangs | fusionnés en « Pièces jointes » (#1095) |
 *  | « Workflow », « Saisi pour » | renommés « Suivi » et « Au nom de » (21/09) |
 *  | dix sections | **treize** |
 *
 *  Résultat : le contrôle était vert en faisant respecter scrupuleusement un
 *  ordre qui n'était plus celui du cadre — et l'écran rendait « Au nom de »
 *  (rang 10) en troisième position sans que rien ne le dise. Signalé à l'écran :
 *  *« L'ordre des sections du tableau n'est pas respecté »*.
 *
 *  Une documentation ne fait échouer personne ; une seconde table non plus —
 *  elle se contente de mentir avec assurance.
 */
const TYPES_SECTIONS = join(RACINE, 'lib', 'entites', 'types.ts');

/** Le bloc d'une déclaration, du nom jusqu'au terminateur donné. */
function bloc(nom, terminateur) {
	const src = readFileSync(TYPES_SECTIONS, 'utf8');
	const d = src.indexOf(nom);
	if (d < 0) throw new Error(`${nom} introuvable dans ${TYPES_SECTIONS}`);
	return src.slice(d, src.indexOf(terminateur, d));
}

/** `{ id → rang }`, lu dans `SECTIONS_ORDRE` — le rang EST la position. */
function rangsParId() {
	//  ⚠️ `export const` : le nom apparaît AUSSI dans les commentaires du fichier,
	//  et partir de la première occurrence lisait des identifiants de prose — la
	//  section « nature » s'est retrouvée au rang 15.
	const ids = [...bloc('export const SECTIONS_ORDRE', '];').matchAll(/'([a-z_]+)'/g)].map(
		(m) => m[1],
	);
	if (ids.length < 10)
		throw new Error(`SECTIONS_ORDRE : ${ids.length} identifiant(s) lu(s) — le motif a derive.`);
	return Object.fromEntries(ids.map((id, i) => [id, i + 1]));
}

/** `{ id → libellé }`, lu dans `SECTIONS_LIBELLE`. */
function libellesParId() {
	const couples = [...bloc('SECTIONS_LIBELLE', '};').matchAll(/^\t([a-z_]+): '([^']+)'/gm)];
	if (couples.length < 10)
		throw new Error(`SECTIONS_LIBELLE : ${couples.length} couple(s) lu(s) — le motif a derive.`);
	return Object.fromEntries(couples.map((m) => [m[1], m[2]]));
}

/**
 *  Les intitulés qu'un écran affiche SANS être celui de la table, et la section
 *  qu'ils occupent — chacun avec sa raison. Une liste d'alias, jamais un
 *  passe-droit : un intitulé absent d'ici ET de la table n'est pas classé, donc
 *  pas contrôlé.
 */
const ALIAS = {
	//  Le ticket dit « Catégorie » là où la table dit « Nature » : c'est le mot
	//  du métier, et le renommer changerait l'écran sans rien gagner.
	Catégorie: 'nature',
	//  Une évolution parle de « Commentaire » là où une actualité parle de
	//  « Description » : même notion, même rang, deux mots.
	Commentaire: 'description',
};

const RANGS_PAR_ID = rangsParId();
const LIBELLES = libellesParId();

/** `{ intitulé affiché → rang }` — dérivé, jamais écrit. */
export const RANGS = {
	...Object.fromEntries(
		Object.entries(LIBELLES)
			.filter(([id]) => RANGS_PAR_ID[id])
			.map(([id, libelle]) => [libelle, RANGS_PAR_ID[id]]),
	),
	...Object.fromEntries(
		Object.entries(ALIAS).map(([libelle, id]) => {
			if (!RANGS_PAR_ID[id])
				throw new Error(`ALIAS « ${libelle} » vise « ${id} », absent de SECTIONS_ORDRE.`);
			return [libelle, RANGS_PAR_ID[id]];
		}),
	),
};

/**
 *  Les composants qui PORTENT une section — leur intitulé vit chez eux.
 *
 *  ⚠️ Un écran qui les appelle n'écrit aucun `titre=`, donc rien ne les
 *  trahissait : c'est par là que « Au nom de » (`ChampSaisiPour`) et « Mise en
 *  avant » (`SectionOptionsPublication`) étaient rendus en tête du formulaire
 *  d'affaire sans qu'un contrôle le voie.
 */
const COMPOSANTS_SECTION = [
	['SectionOptionsPublication', 'mise_en_avant'],
	['ChampSaisiPour', 'au_nom_de'],
	['SectionsPiecesJointes', 'pieces_jointes'],
	['SectionQuand', 'quand'],
	['SectionDescription', 'description'],
	['SectionDiffusion', 'diffusion'],
	['SectionWorkflow', 'suivi'],
];

/**  Les props de `ChampsCommuns` et la SECTION que chacune active.
 *
 *   🔴 L'ordre de ce tableau est celui du COMPOSANT — il rend dans cet ordre-là,
 *   quelles que soient les props écrites par l'appelant. Le rang, lui, vient de
 *   la table : si le composant cesse de rendre dans l'ordre déclaré, les rangs
 *   ne sont plus croissants et le contrôle le dit.
 *
 *   ⚠️ C'est exactement ce qui a été trouvé le 21/09/2026 : « Au nom de » (10)
 *   et « Mise en avant » (11) étaient rendus en tête, avant « Suivi » (4). */
const PROPS_CHAMPS_COMMUNS = [
	['avecWorkflow', 'suivi'],
	['avecQuand', 'quand'],
	['avecPerimetre', 'perimetre'],
	['avecDescription', 'description'],
	['avecPhotos', 'pieces_jointes'],
	['avecDocuments', 'pieces_jointes'],
	['avecSaisiPour', 'au_nom_de'],
	['avecDestinataires', 'destinataires'],
	['avecOptions', 'mise_en_avant'],
	['avecDiffusion', 'diffusion'],
].map(([prop, id]) => {
	if (!RANGS_PAR_ID[id])
		throw new Error(`La prop ${prop} vise « ${id} », absent de SECTIONS_ORDRE.`);
	return [prop, RANGS_PAR_ID[id]];
});

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

	//  🔴 Ces composants PORTENT leur section : leur intitulé n'est pas écrit
	//  dans l'écran qui les appelle, donc aucun `titre=` ne les trahit. Ils
	//  étaient invisibles au contrôle — et « Au nom de », rendu en troisième
	//  position au lieu de la dixième, l'est resté (#1124, 21/09/2026).
	for (const [balise, id] of COMPOSANTS_SECTION) {
		const re = new RegExp(`<${balise}\\b`, 'g');
		let x;
		while ((x = re.exec(source))) {
			if (!ignoree(x.index)) {
				trouvees.push({ position: x.index, rang: RANGS_PAR_ID[id], quoi: balise });
			}
		}
	}
	//  …ou LU DANS LA TABLE, ce qui est la forme correcte depuis #1095.
	//
	//  🔴 Le contrôle ne lisait que `titre="…"` : une section dont l'intitulé
	//  vient de `SECTIONS_LIBELLE` lui était invisible. Plus un écran suivait la
	//  règle, moins il était contrôlé.
	const reTitreTable = /titre={SECTIONS_LIBELLE\.([a-z_]+)}/g;
	while ((m = reTitreTable.exec(source))) {
		const rangT = RANGS_PAR_ID[m[1]];
		if (rangT && !ignoree(m.index)) {
			trouvees.push({ position: m.index, rang: rangT, quoi: LIBELLES[m[1]] ?? m[1] });
		}
	}
	//  Les autres se reconnaissent à leur intitulé, écrit en clair.
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
		'<SectionFormulaire titre="Suivi" /><SectionFormulaire titre="Périmètre" />' +
			'<SectionOptionsPublication />',
		0,
	);
	//  🔴 LE CAS DU 21/09/2026 : la « Mise en avant » (11) rendue AVANT le
	//  « Suivi » (4) — l'ordre réel du formulaire d'affaire, que l'ancienne table
	//  de rangs laissait passer puisqu'elle plaçait les options en 3ᵉ.
	t(
		'la mise en avant avant le suivi',
		'<SectionOptionsPublication /><SectionFormulaire titre="Suivi" />',
		1,
	);
	t(
		'le suivi après la diffusion',
		'<SectionFormulaire titre="Diffusion" /><SectionFormulaire titre="Suivi" />',
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
			'<SectionFormulaire titre="Suivi" />',
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
//  ⬇️ Il SUIT le relevé : 69 sections lues au 21/09/2026 — contre 54 la veille,
//  parce que le contrôle voit enfin les composants qui PORTENT leur section et
//  les intitulés lus dans `SECTIONS_LIBELLE` (#1124).
//  60 → 55 le 23/09/2026 : le formulaire d'événement est parti avec le Calendrier
//  (#1092) — ses sections, pas le repérage. 58 lues ce jour-là.
const PLANCHER_SECTIONS = 55;
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
		//  🔴 L'ordre s'AFFICHE depuis la table, il ne se récite plus : la version
		//  récitée ici est restée à dix sections pendant que le cadre en comptait
		//  treize — et c'est ce message qui faisait autorité auprès de qui le lisait.
		'\n  L’ordre, lu dans `SECTIONS_ORDRE` :\n    ' +
			Object.entries(RANGS_PAR_ID)
				.map(([id, rang]) => `${rang} ${LIBELLES[id] ?? id}`)
				.join(' · ') +
			'\n\n  Il ne se discute pas par écran : deux formulaires qui rangent les mêmes\n' +
			'  notions différemment se lisent comme deux produits.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Ordre des sections : ${sectionsLues} section(s) lue(s) dans ${tous.length} composant(s), toutes dans l'ordre arbitré.`,
);
