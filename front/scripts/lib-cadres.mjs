/**
 * **Lire les cadres d'un fichier Svelte** — les balises ouvrantes qui peuvent
 * rendre une modale, et le contenu qu'elles enveloppent.
 *
 * Extrait le 02/09/2026 de `check-formulaire-creation.mjs`, où il vivait, pendant
 * que `check-modales.mjs` en portait **une seconde écriture** (`ouverturesModale`)
 * qui faisait la même chose en moins bien : elle ne comptait pas les imbrications,
 * et elle rendait le contenu sans la balise.
 *
 * 🔴 Les deux avaient déjà divergé sur ce qu'elles savaient lire, et c'est ce qui
 * rendait la duplication coûteuse : apprendre une forme d'ouverture à l'une ne
 * l'apprenait pas à l'autre. La forme dynamique a été ajoutée à la première le
 * 30/08 ; la seconde l'a reçue séparément. Le cadre factorisé, lui, a fait
 * échouer les deux le même jour — pour deux raisons différentes.
 *
 * ## Les trois formes, et pourquoi les appelants n'en veulent pas les mêmes
 *
 * | Forme | Toujours une modale ? |
 * |---|---|
 * | `<Modale …>` | oui |
 * | `<svelte:component this={… Modale …}>` | oui — c'est le filtre qui l'assure |
 * | `<CadreFormulaire …>` | **non** : fenêtre en édition, boîte dans la page sinon |
 *
 * ⚠️ D'où deux jeux, et pas une liste unique :
 *
 * - `check-modales` veut **les trois**. Il garde l'invariant « le titre ne se
 *   réécrit pas dans le contenu », qui vaut dès qu'un cadre reçoit `titre` en
 *   prop — ce que `CadreFormulaire` fait dans les deux gestes.
 * - `check-formulaire-creation` veut **les deux premières** pour sa règle
 *   « une modale portant un formulaire doit se déclarer `edition` ».
 *   `CadreFormulaire` ne rend une fenêtre QUE si `edition` est posé : l'invariant
 *   y est structurel, et le compter produirait un faux positif sur chaque
 *   formulaire de création.
 *
 * Le jour où une quatrième forme apparaîtra, elle s'ajoutera **ici**, et les deux
 * contrôles la recevront ensemble.
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
export const FORME_MODALE = {
	tag: '<Modale',
	fermeture: '</Modale>',
	//  ⚠️ Le motif est une FABRIQUE, pas un littéral partagé : un `RegExp` global
	//  réutilisé porte son `lastIndex` d'un appel à l'autre, et le deuxième
	//  fichier analysé n'y trouve alors plus rien. Un contrôle qui ne lit que le
	//  premier fichier est vert sur tous les autres.
	ouvrant: () => /<Modale(?=[\s>])/g,
};

/**  `<CadreFormulaire>` — le cadre qui CHOISIT (02/09/2026, voir l'en-tête).
 *
 *   Il n'est pas toujours une modale : c'est pourquoi il est nommé à part et non
 *   ajouté au premier. Seul `check-modales` le retient.
 */
export const FORME_CADRE = {
	tag: '<CadreFormulaire',
	fermeture: '</CadreFormulaire>',
	ouvrant: () => /<CadreFormulaire(?=[\s>])/g,
};

export const FORME_DYNAMIQUE = {
	tag: '<svelte:component',
	fermeture: '</svelte:component>',
	ouvrant: () => /<svelte:component(?=[\s>])/g,
	//  Seules celles qui montent une `Modale` nous concernent : ce tag sert
	//  aussi, légitimement, à tout autre choix de composant.
	//
	//  ⚠️ **Une inclusion de chaîne, et surtout pas une expression régulière
	//  avec ``.** Ce filtre en a porté une, et les deux `` se sont écrits
	//  dans le fichier en **caractères de recul U+0008**, invisibles à la
	//  relecture. Le motif ne correspondait alors à rien : `filtre` rendait
	//  toujours `false`, aucune modale dynamique n'était vue, et le contrôle
	//  affichait un ✓.
	//
	//  🔴 C'est EXACTEMENT le défaut trouvé le 20/08/2026 dans
	//  `check-workflow-envoye.mjs` (#549) — un `` au milieu d'un motif qui
	//  ne retirait donc rien — reproduit dix jours plus tard, dans un autre
	//  garde-fou, par la même cause : un motif écrit depuis un interpréteur de
	//  commandes, où `` est **un** caractère et non deux.
	//
	//  ⚠️ ET LE GARDE-FOU EXISTAIT. `no-control-regex` d'ESLint le nomme, et il
	//  est actif sur `scripts/**`. Il n'a rien dit parce qu'il n'a pas été LANCÉ
	//  entre l'écriture et la mesure : un défaut de conduite, pas de couverture.
	//
	//  Ce qui l'a rattrapé en attendant : avoir exigé que le compteur de modales
	//  AUGMENTE après la conversion. Il est resté à 28, et c'est le seul signe
	//  qu'il y a eu. Un contrôle se vérifie par son échec **et** par son
	//  décompte — `standards/04` §27.
	filtre: (balise) => balise.includes('Modale'),
};

/** Les deux formes qui sont TOUJOURS une modale. */
export const FORMES_MODALES = [FORME_MODALE, FORME_DYNAMIQUE];
/** Les trois formes qui reçoivent un `titre` en prop. */
export const FORMES_CADRES = [FORME_MODALE, FORME_CADRE, FORME_DYNAMIQUE];

/**
 * Les cadres d'un contenu : `{ balise, suite }` pour chacun.
 *
 * `formes` par défaut = celles qui sont toujours une modale — le choix le plus
 * restrictif, pour qu'un appelant qui ne se pose pas la question n'élargisse pas
 * la règle sans le vouloir.
 */
export function modales(contenu, formes = FORMES_MODALES) {
	const sorties = [];
	for (const forme of formes) sorties.push(...modalesDe(contenu, forme));
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
