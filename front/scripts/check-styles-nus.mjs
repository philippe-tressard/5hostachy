/**
 * Garde-fou : un composant ne redéfinit pas un ÉLÉMENT de formulaire tout entier.
 *
 * ## Le défaut qui a fait naître ce contrôle (16/08/2026)
 *
 * `routes/(app)/sondages/+page.svelte` portait, dans son `<style>` :
 *
 *     input, textarea { … width: 100%; }
 *
 * Un sélecteur d'ÉLÉMENT nu. Il visait les champs de saisie — et atteignait donc
 * aussi **toutes les cases à cocher de la page**, qui s'étiraient sur la largeur
 * du formulaire et repoussaient leur libellé à l'autre bout de la ligne. Signalé
 * par l'utilisateur sur DEUX écrans (« Nouveau sondage » et « Déposer une
 * annonce ») ; une seule ligne, deux symptômes, aucun lien apparent entre eux.
 *
 * Le contournement était devenu un réflexe ailleurs sur le site : quatre
 * composants posaient `style="width:auto"` **sur chaque case à cocher**, ou une
 * règle `input[type="checkbox"] { width: auto }` pour annuler un global. Un
 * remède recopié à chaque occurrence est le signe qu'on soigne le symptôme.
 *
 * ## Ce qui est refusé
 *
 * Dans le `<style>` d'un `.svelte`, un sélecteur qui est EXACTEMENT un nom
 * d'élément de formulaire (`input`, `textarea`, `select`, `button`, `label`),
 * sans classe, sans attribut, sans parent. Ces règles-là appartiennent à
 * `app.css`, où elles sont écrites une fois, pour tout le site, et où `.field
 * input` les porte déjà.
 *
 * Reste autorisé — et c'est l'essentiel du besoin légitime :
 *   • `.case input[type="checkbox"]`  (parent + attribut)
 *   • `.form-grid select`             (parent)
 *   • `input[type="range"]`           (attribut : la règle vise un type précis)
 *
 * ⚠️ `app.css` n'est PAS concerné : c'est justement l'endroit où une règle
 * d'élément est légitime, parce qu'elle est alors globale et assumée.
 *
 * Le contrôle s'auto-contrôle : s'il ne trouve aucun `.svelte` à lire, il ÉCHOUE
 * au lieu de conclure au vert (`standards/04-fiabilite-des-controles.md` §2).
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/** Les éléments dont une règle nue casse silencieusement un autre usage. */
const ELEMENTS = ['input', 'textarea', 'select', 'button', 'label'];

/**
 * Tolérances, chacune avec sa raison. Une liste sans raison devient un dépotoir ;
 * et le contrôle échoue si l'une d'elles cesse de servir (voir plus bas).
 */
const TOLERANCES = {
	// (aucune pour l'instant — les ajouter ici avec leur justification)
};

function fichiersSvelte(dossier) {
	const trouves = [];
	for (const entree of readdirSync(dossier)) {
		const chemin = join(dossier, entree);
		if (statSync(chemin).isDirectory()) trouves.push(...fichiersSvelte(chemin));
		else if (entree.endsWith('.svelte')) trouves.push(chemin);
	}
	return trouves;
}

/** Le contenu des blocs `<style>` d'un composant, avec le décalage de ligne. */
function blocsStyle(source) {
	const blocs = [];
	const motif = /<style[^>]*>([\s\S]*?)<\/style>/g;
	let m;
	while ((m = motif.exec(source)) !== null) {
		const ligneDebut = source.slice(0, m.index).split('\n').length;
		blocs.push({ contenu: m[1], ligneDebut });
	}
	return blocs;
}

/**
 * Les sélecteurs nus d'un bloc CSS.
 *
 * On lit les en-têtes de règle (ce qui précède un `{`), commentaires retirés, et
 * on ne retient que les sélecteurs réduits à un nom d'élément. Un sélecteur
 * composé (`.case input`, `input[type=…]`, `input:focus`) ne correspond pas.
 */
function selecteursNus(css) {
	const sansCommentaires = css.replace(/\/\*[\s\S]*?\*\//g, (c) => c.replace(/[^\n]/g, ' '));
	const trouves = [];
	const motif = /([^{}();@]+)\{/g;
	let m;
	while ((m = motif.exec(sansCommentaires)) !== null) {
		const entete = m[1];
		const ligne = sansCommentaires.slice(0, m.index + entete.length).split('\n').length;
		for (const sel of entete.split(',')) {
			const propre = sel.trim();
			if (ELEMENTS.includes(propre)) trouves.push({ selecteur: propre, ligne });
		}
	}
	return trouves;
}

const fichiers = fichiersSvelte(RACINE);

//  Cas zéro : un contrôle qui n'a rien lu ne dit pas « tout va bien ».
if (fichiers.length < 20) {
	console.error(
		`✗ lint:styles — ${fichiers.length} fichier(s) .svelte trouvé(s) sous ${RACINE} : ` +
			'le contrôle ne peut pas s\'exécuter, il ne passe donc pas au vert.',
	);
	process.exit(1);
}

const fautes = [];
const toleragesVus = new Set();

for (const fichier of fichiers) {
	const relatif = relative(RACINE, fichier).split(sep).join('/');
	const source = readFileSync(fichier, 'utf8');
	for (const { contenu, ligneDebut } of blocsStyle(source)) {
		for (const { selecteur, ligne } of selecteursNus(contenu)) {
			const cle = `${relatif}:${selecteur}`;
			if (cle in TOLERANCES) {
				toleragesVus.add(cle);
				continue;
			}
			fautes.push(`${relatif}:${ligneDebut + ligne - 1} — sélecteur nu « ${selecteur} »`);
		}
	}
}

//  Une tolérance qui ne sert plus doit disparaître, sinon la liste couvre un jour
//  un cas redevenu normal et le contrôle reste vert sans rien contrôler.
const perimees = Object.keys(TOLERANCES).filter((c) => !toleragesVus.has(c));
if (perimees.length) {
	console.error(
		'✗ lint:styles — ces tolérances ne servent plus, les retirer :\n  ' + perimees.join('\n  '),
	);
	process.exit(1);
}

if (fautes.length) {
	console.error(
		'✗ lint:styles — un sélecteur d\'ÉLÉMENT nu dans un composant atteint TOUS les\n' +
			'  éléments de ce type, y compris ceux qu\'on n\'avait pas en tête : c\'est ainsi\n' +
			'  que les cases à cocher de l\'écran Communauté se sont retrouvées étirées sur\n' +
			'  toute la largeur, séparées de leur libellé (16/08/2026).\n\n' +
			'  Corriger en QUALIFIANT le sélecteur — `.mon-champ input`, `input[type="range"]` —\n' +
			'  ou en portant la règle dans `app.css`, où elle est globale et assumée.\n\n  ' +
			fautes.join('\n  '),
	);
	process.exit(1);
}

console.log(`✓ lint:styles — ${fichiers.length} composants, aucun sélecteur d'élément nu`);
