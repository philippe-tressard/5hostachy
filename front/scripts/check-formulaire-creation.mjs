/**
 * Garde-fou : un formulaire de création s'écrit d'UNE seule façon.
 *
 * ## Pourquoi (#367, 15/08/2026)
 *
 * Le produit offrait **trois paradigmes** pour la même intention — créer un objet :
 * une boîte dans la page (actualités, sondages), une modale (calendrier,
 * prestataires — avec deux largeurs différentes), une page dédiée (nouveau
 * ticket). Un résident qui publie une actualité, ouvre un ticket et propose un
 * événement faisait trois gestes différents.
 *
 * Signalé **trois fois** par l'utilisateur avant d'être traité. Les deux premiers
 * lots (#361 largeur de saisie, #363 en-tête de page) avaient corrigé des
 * symptômes périphériques sans jamais ouvrir le formulaire lui-même.
 *
 * Le paradigme retenu est la **boîte dans la page**, sur désignation de
 * l'utilisateur : les actualités sont le modèle.
 *
 * ## Ce qui est interdit dans `routes/`
 *
 *   1. `class="card largeur-saisie"` écrit à la main — passer par
 *      `<FormulaireCreation titre="…">` ;
 *   2. une `<Modale>` portant un `<form>` **sans se déclarer `edition`**.
 *
 * ## 🔴 Le point 2 a changé de forme le 30/08/2026 — et il était MORT
 *
 * Il cherchait `class="modal-overlay"` suivi d'un `<form>`. Or #561 (28/08) a
 * fait absorber ce fond par `Modale.svelte`, qui vit dans `lib/` — hors du
 * périmètre `routes/` de ce contrôle. **Le motif ne pouvait donc plus rien
 * trouver, jamais**, et le contrôle restait vert : c'est `standards/04` §27, un
 * contrôle dont le résultat normal est zéro ne peut pas se relire lui-même.
 *
 * Il lit maintenant les `<Modale>` elles-mêmes, et il porte un **plancher
 * d'éléments lus** — sans quoi il pourrait redevenir muet de la même façon.
 *
 * ## Et la règle qu'il applique a changé le même jour (`ux-patterns` §14 bis)
 *
 * Arbitré à l'écran : *« en édition, le format modal est plus net que le
 * dépliement sur une même fenêtre »*. Un geste, un format :
 *
 *   - **créer** → la boîte dans la page (ce que #367 a établi, et qui tient) ;
 *   - **éditer** → la modale, qui se déclare par `<Modale edition>`.
 *
 * ⚠️ La modale de CRÉATION reste refusée. Sans cette moitié-là, la règle
 * redeviendrait « au cas par cas », c'est-à-dire les trois paradigmes que #367 a
 * supprimés après trois signalements.
 *
 * Le contrôle s'auto-contrôle : composant absent, prop disparue ou plus aucune
 * page utilisatrice → il ÉCHOUE au lieu de conclure au vert
 * (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const ROUTES = join(RACINE, 'routes');
const COMPOSANTS = join(RACINE, 'lib', 'components');
const COMPOSANT = join(COMPOSANTS, 'FormulaireCreation.svelte');

/**
 * Les composants de `lib/components/` qui rendent eux-mêmes un `<form>`.
 *
 * 🔴 SANS CELA, LE CONTRÔLE EST AVEUGLE À TOUT FORMULAIRE FACTORISÉ — et donc à
 * ceux qu'on vient d'extraire, c'est-à-dire au bon code. Il cherchait `<form>`
 * dans le balisage de la page ; une modale montant `<FormulaireContrat />`
 * n'en contient aucun, et passait sans sa déclaration `edition`.
 *
 * Constaté le 30/08/2026 en éprouvant le contrôle **par son échec** : la
 * première modale d'édition du site a été écrite, sa déclaration retirée
 * exprès — et le contrôle est resté vert. Même famille que la première version
 * du self-test de `lib-volumes.sh`, qui avait échoué le jour où le code s'est
 * amélioré : *un contrôle qui ne voit pas la factorisation mesure la forme, pas
 * le fait.*
 *
 * La liste est **calculée**, jamais tenue à la main : une liste recopiée
 * diverge au premier composant ajouté, et c'est justement le composant ajouté
 * qui échappe au contrôle.
 */
function composantsPorteursDeFormulaire() {
	const noms = new Set();
	for (const nom of readdirSync(COMPOSANTS)) {
		if (!nom.endsWith('.svelte')) continue;
		if (/<form\b/.test(sansCommentaires(readFileSync(join(COMPOSANTS, nom), 'utf8')))) {
			noms.add(nom.replace(/\.svelte$/, ''));
		}
	}
	return noms;
}

/**
 * Emplois légitimes hors du composant, avec leur raison.
 *
 * Une tolérance sans raison devient un dépotoir : chacune est nommée, et le
 * contrôle échoue si l'une cesse de servir.
 */
const EXCEPTIONS = {
	//  🔴 QUATRE ÉCRANS, SEPT MODALES DE CRÉATION — suivi en #672, ouvert le
	//  31/08/2026 par l'élargissement de ce contrôle aux champs nus.
	//
	//  Elles créent un objet dans une modale, ce que #367 a supprimé après trois
	//  signalements de l'utilisateur. Elles y ont échappé parce que ce contrôle ne
	//  cherchait qu'un `<form>` : elles n'en portent aucun, seulement des `.field`.
	//
	//  ⚠️ Elles ne sont PAS tolérées « parce que c'est comme ça » : elles sont
	//  datées, ticketées, et R5 impose un écran à la fois. Deux d'entre elles
	//  dépassent le plafond de modularité et demandent d'abord l'extraction d'un
	//  `Formulaire<Entité>`, comme la FAQ le jour même.
	'routes/(app)/delegations/+page.svelte': '#672 — « Nouvelle délégation aidant »',
	'routes/(app)/mon-lot/+page.svelte':
		"#672 — « Nouveau bail » (fichier de 2 230 l., extraction d'abord)",
	'routes/(app)/residence/+page.svelte':
		"#672 — quatre « Ajouter … » (fichier de 1 518 l., extraction d'abord)",
	'lib/components/OngletPerimetres.svelte':
		"#672 — « Nouveau périmètre » (l'édition, elle, est déclarée)",
};

/** Retire commentaires et balisage commenté : expliquer la règle ne doit pas l'enfreindre. */

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

//  ── Auto-contrôle (cas zéro) ────────────────────────────────────────────────
if (!existsSync(COMPOSANT)) {
	console.error(`✗ Cas zéro : ${COMPOSANT} est introuvable — contrôle inopérant.`);
	process.exit(1);
}
if (!/export let titre\b/.test(readFileSync(COMPOSANT, 'utf8'))) {
	console.error(
		"✗ Cas zéro : FormulaireCreation n'expose plus `titre`. Le contrat a changé — " +
			'mettre ce contrôle à jour, sinon il laisse passer les formulaires écrits à la main.',
	);
	process.exit(1);
}

//  🔴 LE PÉRIMÈTRE INCLUT `lib/components/` DEPUIS LE 30/08/2026, ET C'EST LE
//  POINT 1 DE #640.
//
//  Il ne lisait que `routes/`. Or la conversion des écrans en modale d'édition
//  déplace le cadre là où vit le geste — et pour six formulaires sur sept, c'est
//  le composant qui le porte, pas la page (`FormulaireActualite` écrit son
//  propre `<FormulaireCreation>` depuis toujours). Chaque conversion faisait donc
//  SORTIR la modale du champ du contrôle : convertir revenait à se désarmer.
//
//  C'est la même cécité que celle décrite trois fois plus haut dans ce fichier —
//  `modal-overlay` mort depuis #561, le formulaire factorisé invisible — et
//  toujours pour la même raison : *le contrôle ne voyait pas la factorisation,
//  donc il mesurait la forme et non le fait.* La corriger AVANT de convertir est
//  ce que #640 demande en premier, faute de quoi chaque écran converti devrait
//  contourner le contrôle pour passer.
const tous = [...fichiers(ROUTES), ...fichiers(COMPOSANTS)];
if (tous.length === 0) {
	console.error("✗ Cas zéro : aucun fichier analysé — l'arborescence a changé.");
	process.exit(1);
}

//  Cas zéro du repérage par composant : s'il ne trouve plus aucun porteur, la
//  moitié « formulaire factorisé » du contrôle ne mesure plus rien — et elle
//  échouerait en silence, exactement comme le motif `modal-overlay` mort de #561.
const PORTEURS = composantsPorteursDeFormulaire();
if (PORTEURS.size === 0) {
	console.error(
		'✗ Cas zéro : aucun composant de lib/components/ ne rend de <form>. Le repérage ' +
			'des formulaires factorisés ne mord plus — ne pas lire ceci comme un succès.',
	);
	process.exit(1);
}

//  ── Recherche ───────────────────────────────────────────────────────────────
const MOTIFS = [
	{
		//  Le cadre N'EST fautif que s'il enveloppe un `<form>` : `card largeur-saisie`
		//  sert aussi, légitimement, à des cartes de LECTURE (les lots de `mon-lot`,
		//  par exemple, qui n'ont rien d'un formulaire). Sans cette condition, le
		//  contrôle criait sur elles — et un contrôle qui crie sur du légitime finit
		//  désarmé.
		regex: /class="[^"]*\bcard\b[^"]*\blargeur-saisie\b[^"]*"[\s\S]{0,400}?<form/g,
		quoi: 'un cadre de formulaire est rendu à la main',
		remede: '<FormulaireCreation titre="…"> … </FormulaireCreation>',
	},
	//  🔴 Le motif qui cherchait `class="modal-overlay"` est RETIRÉ : il était mort
	//  depuis #561 (28/08/2026). Le fond de modale ne s'écrit plus à la main —
	//  `Modale.svelte` l'a absorbé, et il vit dans `lib/`, hors du périmètre
	//  `routes/` de ce contrôle. Le motif ne pouvait donc plus rien trouver,
	//  jamais, et le contrôle restait vert : `standards/04` §27, un contrôle dont
	//  le résultat normal est zéro ne peut pas se relire lui-même.
	//
	//  Il est remplacé plus bas par une lecture de `<Modale>` — voir `modaleSansEdition`.
	//  Pas de motif sur `<h2 style="font-size…">`. Il avait été écrit, et il criait
	//  sur neuf pages dont sept portaient un titre de SECTION parfaitement légitime
	//  (admin, espace-cs, faq, profil, fiches de ticket et de sondage). Rien dans le
	//  balisage ne distingue un titre de formulaire d'un titre de section — et un
	//  contrôle qui crie sur du légitime finit désarmé, c'est la leçon de C16.
	//  L'uniformisation des titres de section est un autre sujet, qui aura son
	//  propre invariant le jour où il sera tranché.
];

/**
 * Les `<Modale>` d'un fichier : la balise ouvrante et **son contenu réel**.
 *
 * La fin de la balise est le premier `>` HORS accolade — un attribut peut
 * contenir `=>` ou un objet, que suivre naïvement couperait trop tôt.
 *
 * 🔴 LE CONTENU EST BORNÉ PAR `</Modale>`, ET NON PAR UNE FENÊTRE DE N
 * CARACTÈRES (30/08/2026). Il l'était : « les 1200 caractères qui suivent ».
 * C'est une approximation, et elle se trompe **dans les deux sens** :
 *
 *   - trop court, elle rate un formulaire situé plus bas dans une longue modale ;
 *   - trop long, elle déborde sur la modale SUIVANTE — et c'est ce qui est
 *     arrivé le jour où un composant de formulaire a été monté dans la seconde
 *     de deux modales voisines : le contrôle a accusé la première, une simple
 *     confirmation sans le moindre champ.
 *
 * ⚠️ Un contrôle qui crie sur du légitime finit désarmé (leçon de C16). Ici il
 * aurait fallu déclarer `edition` sur une boîte de confirmation — c'est-à-dire
 * mentir sur le geste pour faire taire le contrôle.
 *
 * La borne équilibrée coûte deux lignes et supprime la classe entière.
 */
/**
 * 🔴 UNE MODALE MONTÉE DYNAMIQUEMENT EST UNE MODALE (30/08/2026).
 *
 * `<svelte:component this={modeEdition ? Modale : FormulaireCreation}>` est la
 * seule forme, en syntaxe Svelte 4, qui permette d'écrire le corps d'un
 * formulaire UNE fois pour deux cadres — deux branches `{#if}` en feraient deux
 * copies de deux cents lignes. C'est donc une forme qu'on va rencontrer à chaque
 * conversion de #640, et le contrôle ne la voyait pas : le tag ne s'appelle pas
 * `<Modale>`.
 *
 * Il est resté VERT sur la première conversion, formulaire monté dans une modale
 * comprise. Troisième fois que ce fichier découvre la même cécité — motif
 * `modal-overlay` mort, formulaire factorisé invisible, périmètre borné à
 * `routes/` — et toujours pour la même raison : *il mesurait la forme et non le
 * fait.*
 *
 * ⚠️ Le repérage exige que `Modale` figure dans la balise ouvrante. Un composant
 * choisi ailleurs (`const cadre = …` hors du balisage) échapperait encore ; c'est
 * pourquoi le nom est écrit DANS l'expression `this={…}`, et non déduit d'une
 * variable — écrire le geste là où le contrôle peut le lire fait partie du geste.
 */
const OUVERTURES = [
	//  ⚠️ Le motif est une FABRIQUE, pas un littéral partagé : un `RegExp` global
	//  réutilisé porte son `lastIndex` d'un appel à l'autre, et le deuxième
	//  fichier analysé n'y trouve alors plus rien. Un contrôle qui ne lit que le
	//  premier fichier est vert sur tous les autres.
	{ tag: '<Modale', fermeture: '</Modale>', ouvrant: () => /<Modale(?=[\s>])/g },
	{
		tag: '<svelte:component',
		fermeture: '</svelte:component>',
		ouvrant: () => /<svelte:component(?=[\s>])/g,
		//  Seules celles qui montent une `Modale` nous concernent : ce tag sert
		//  aussi, légitimement, à tout autre choix de composant.
		//
		//  ⚠️ **Une inclusion de chaîne, et surtout pas une expression régulière
		//  avec `\b`.** Ce filtre en a porté une, et les deux `\b` se sont écrits
		//  dans le fichier en **caractères de recul U+0008**, invisibles à la
		//  relecture. Le motif ne correspondait alors à rien : `filtre` rendait
		//  toujours `false`, aucune modale dynamique n'était vue, et le contrôle
		//  affichait un ✓.
		//
		//  🔴 C'est EXACTEMENT le défaut trouvé le 20/08/2026 dans
		//  `check-workflow-envoye.mjs` (#549) — un `\x08` au milieu d'un motif qui
		//  ne retirait donc rien — reproduit dix jours plus tard, dans un autre
		//  garde-fou, par la même cause : un motif écrit depuis un interpréteur de
		//  commandes, où `\b` est **un** caractère et non deux.
		//
		//  ⚠️ ET LE GARDE-FOU EXISTAIT. `no-control-regex` d'ESLint le nomme —
		//  « Unexpected control character(s) in regular expression: \x08, \x08 » —
		//  et il est actif sur `scripts/**`. Il n'a rien dit parce qu'il n'a pas
		//  été LANCÉ entre l'écriture et la mesure : c'est un défaut de conduite,
		//  pas de couverture, et le nommer comme tel évite d'ajouter un contrôle
		//  de plus là où il y en avait déjà un.
		//
		//  Ce qui l'a rattrapé en attendant : avoir exigé que le compteur de
		//  modales AUGMENTE après la conversion. Il est resté à 28, et c'est le
		//  seul signe qu'il y a eu. Un contrôle se vérifie par son échec **et** par
		//  son décompte — `standards/04` §27.
		filtre: (balise) => balise.includes('Modale'),
	},
];

function modales(contenu) {
	const sorties = [];
	for (const forme of OUVERTURES) sorties.push(...modalesDe(contenu, forme));
	return sorties;
}

function modalesDe(contenu, { tag, fermeture, ouvrant, filtre }) {
	const sorties = [];
	for (const m of contenu.matchAll(ouvrant())) {
		let i = m.index + tag.length;
		let accolades = 0;
		for (; i < contenu.length; i++) {
			const c = contenu[i];
			if (c === '{') accolades++;
			else if (c === '}') accolades--;
			else if (c === '>' && accolades === 0) break;
		}
		//  Fermeture ÉQUILIBRÉE : une modale peut en contenir une autre (une
		//  confirmation par-dessus un formulaire). Prendre le premier `</Modale>`
		//  couperait alors le contenu de la première au milieu.
		const balise = contenu.slice(m.index, i + 1);
		if (filtre && !filtre(balise)) continue;
		let profondeur = 1;
		//  `tag` et `fermeture` contiennent `:` et `/` : on les échappe entièrement
		//  plutôt que caractère par caractère — une liste d'exceptions à échapper
		//  oublie toujours le caractère ajouté ensuite.
		const ech = (s) => s.replace(/[.*+?^${}()|[\]\\/:]/g, '\\$&');
		const jetons = new RegExp(`${ech(tag)}(?=[\\s>])|${ech(fermeture)}`, 'g');
		jetons.lastIndex = i + 1;
		let t;
		while ((t = jetons.exec(contenu)) !== null) {
			profondeur += t[0] === fermeture ? -1 : 1;
			if (profondeur === 0) break;
		}
		//  Modale non fermée (fin de fichier) : on prend ce qui reste plutôt que
		//  rien — se taire sur un balisage incomplet serait le pire des deux.
		const fin = t ? t.index : contenu.length;
		sorties.push({ balise, suite: contenu.slice(i + 1, fin) });
	}
	return sorties;
}

/**
 * Une modale qui porte un `<form>` **sans se déclarer `edition`** — donc une
 * modale de CRÉATION, le paradigme que #367 a supprimé.
 *
 * ⚠️ Rien dans le balisage ne dit si l'on crée ou si l'on corrige : le contrôle
 * ne peut pas le deviner, celui qui écrit l'écran si. D'où la prop, et non une
 * heuristique — une heuristique se trompe en silence dans les deux sens.
 */
function modaleSansEdition(contenu, porteurs) {
	//  Un formulaire, dans une modale, s'écrit de TROIS façons : en clair
	//  (`<form>`), monté par un composant qui en porte un, ou — et c'est la plus
	//  fréquente ici — écrit en champs nus, sans jamais la balise.
	//
	//  🔴 LA TROISIÈME A ÉTÉ AJOUTÉE LE 31/08/2026, ET ELLE A TROUVÉ 12 MODALES
	//  dans 8 fichiers : sept créations en modale, et neuf éditions qui n'avaient
	//  jamais déclaré leur geste. Aucune n'avait été vue par ce contrôle.
	//
	//  La FAQ ouvrait une modale pour la CRÉATION d'une question depuis toujours,
	//  soit le paradigme que #367 a supprimé après trois signalements de
	//  l'utilisateur. Elle est passée dessous parce que sa modale ne contient
	//  aucune balise `<form>` : seulement des `<label class="field">` et un
	//  éditeur riche. **Un formulaire n'a pas besoin d'en porter un.**
	//
	//  ⚠️ Le signal est `class="field"`, et NON `<input>` : le projet impose que
	//  tout champ libellé vive dans un `.field` (`lint:champs`, six nomenclatures
	//  locales avant #413). Un `<input>` nu sert aussi à filtrer une liste ou à
	//  chercher — le compter ferait crier sur des modales de lecture, et un
	//  contrôle qui crie sur du légitime finit désarmé (leçon de C16).
	const monteUnFormulaire = (suite) =>
		/<form\b/.test(suite) ||
		/class="[^"]*\bfield\b/.test(suite) ||
		[...porteurs].some((n) => new RegExp(`<${n}\\b`).test(suite));
	return modales(contenu)
		.filter((m) => monteUnFormulaire(m.suite) && !/\bedition\b/.test(m.balise))
		.map((m) => m.balise.slice(0, 80).replace(/\s+/g, ' '));
}

const fautifs = [];
const exceptionsUtiles = new Set();
let pagesAvecFormulaire = 0;
let modalesLues = 0;

for (const f of tous) {
	//  Le chemin est rendu depuis `src/`, les deux racines étant mêlées : « lib/… »
	//  ou « routes/… » se lit sans ambiguïté, là où un relatif à ROUTES écrirait
	//  « ../lib/components/… » pour la moitié du relevé.
	const rel = relative(RACINE, f).split(sep).join('/');
	const brut = readFileSync(f, 'utf8');
	if (brut.includes('<FormulaireCreation')) pagesAvecFormulaire++;
	const contenu = sansCommentaires(brut);
	modalesLues += modales(contenu).length;
	const trouves = [];
	for (const motif of MOTIFS) {
		const m = contenu.match(motif.regex);
		if (m) trouves.push({ ...motif, exemples: [...new Set(m.map((s) => s.trim()))].slice(0, 2) });
	}
	const creationEnModale = modaleSansEdition(contenu, PORTEURS);
	if (creationEnModale.length > 0) {
		trouves.push({
			quoi: 'un formulaire est rendu dans une MODALE sans se déclarer `edition`',
			remede:
				'créer → <FormulaireCreation titre="…"> (la boîte dans la page) · ' +
				'corriger un objet existant → <Modale edition …> (`ux-patterns` §14 bis)',
			exemples: creationEnModale.slice(0, 2),
		});
	}
	if (trouves.length === 0) continue;
	if (rel in EXCEPTIONS) {
		exceptionsUtiles.add(rel);
		continue;
	}
	fautifs.push({ fichier: rel, trouves });
}

//  🔴 Le relevé légitime de ce contrôle est VIDE : il ne peut donc pas distinguer
//  « rien trouvé » de « rien lu » (`standards/04` §27). C'est exactement ainsi que
//  son motif précédent est resté vert en étant mort. Le témoin est un plancher
//  d'éléments LUS : sous ce seuil, le repérage des `<Modale>` ne mord plus.
const PLANCHER_MODALES = 10;
if (modalesLues < PLANCHER_MODALES) {
	console.error(
		`✗ Cas zéro : ${modalesLues} <Modale> recensée(s) dans routes/ et lib/components/, ${PLANCHER_MODALES} ` +
			'attendues au minimum. Le repérage ne mord plus — ne pas lire ceci comme un succès.',
	);
	process.exit(1);
}

//  Le composant peut exister, être conforme, et n'être employé nulle part.
if (pagesAvecFormulaire === 0) {
	console.error(
		"✗ Cas zéro : aucune page n'utilise <FormulaireCreation>. Le composant existe mais " +
			'ne sert plus — ce contrôle ne mesure alors plus rien.',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error('✗ Formulaire(s) de création écrit(s) hors du composant :');
	for (const { fichier, trouves } of fautifs) {
		for (const t of trouves) {
			console.error(`    ${fichier} — ${t.exemples.join(' · ')}`);
			console.error(`        ${t.quoi}`);
			console.error(`        → ${t.remede}`);
		}
	}
	console.error(
		'\n  Trois paradigmes de création coexistaient pour la même intention, et il a fallu\n' +
			"  que l'utilisateur le signale trois fois. Un seul est retenu : la boîte dans la\n" +
			'  page, dont les actualités sont le modèle (#367).',
	);
	process.exit(1);
}

const inutiles = Object.keys(EXCEPTIONS).filter((f) => !exceptionsUtiles.has(f));
if (inutiles.length > 0) {
	console.error('✗ Exception(s) devenue(s) inutile(s) :');
	for (const f of inutiles) console.error(`    ${f} — retirer l'entrée de EXCEPTIONS`);
	process.exit(1);
}

console.log(
	`✓ Formulaires : ${pagesAvecFormulaire} page(s) passent par FormulaireCreation, ` +
		`${tous.length} page(s) et ${modalesLues} modale(s) vérifiée(s), ` +
		`${Object.keys(EXCEPTIONS).length} exception(s) justifiée(s).`,
);
