/**
 * Lire une source Svelte ou TypeScript SANS supposer sa mise en forme.
 *
 * ## Le défaut que ce module retire (#419, 29/08/2026)
 *
 * Quatre garde-fous lisaient le code avec des motifs ancrés sur une DISPOSITION :
 * `^\t{ id: 'x', href:` — une tabulation, tout sur une ligne, une espace après
 * chaque deux-points. Ils mesuraient donc la mise en forme autant que le sens.
 *
 * Passer Prettier sur le dépôt ne change pas une ligne de comportement, et les
 * quatre tombaient :
 *
 * | Contrôle | Ce qu'il annonçait |
 * |---|---|
 * | `lint:pages` | « 0 identifiant extrait, au moins 10 attendus » |
 * | `lint:modales` | « 0 fichier emploie `<Modale>` » |
 * | `lint:taches` | des libellés « écrits en dur » qui ne l'étaient pas |
 * | `lint:soumission` | « aucun bouton de soumission repérable » |
 *
 * 🔴 Deux d'entre eux **disaient** ne plus rien mesurer — leur cas zéro a
 * fonctionné, et c'est ce qui a permis de les croire. Les deux autres ont rendu
 * un relevé FAUX, ce qui est pire : un contrôle qui accuse à tort finit désarmé
 * aussi sûrement qu'un contrôle muet.
 *
 * C'est le même motif que la modularité venait de quitter (elle comptait des
 * LIGNES, donc pénalisait le formatage standard et récompensait l'écriture
 * dense — l'inverse de son but). Il est ici retiré une fois, pour les quatre.
 *
 * ⚠️ **Ce module ne rend rien permissif.** Chacun de ces contrôles protège un
 * défaut réel, et le protège toujours : on cesse d'exiger une disposition, pas
 * de vérifier une règle.
 */

/**
 * Les valeurs des déclarations `champ: 'valeur'`, quelle que soit la mise en page.
 *
 * Tolère l'indentation, les sauts de ligne autour des deux-points, et les deux
 * guillemets. `suivi` permet d'exiger ce qui vient APRÈS — c'est ainsi que la
 * table des pages distingue `id:` suivi de `href:` d'un `id:` quelconque.
 *
 * @param {string} source
 * @param {string} champ   nom du champ, ou fragment d'expression (`[a-z_]+`)
 * @param {{ valeur?: string, suivi?: string }} [options]
 * @returns {string[]}
 */
export function valeursDeclarees(source, champ, options = {}) {
	const valeur = options.valeur ?? "[^']+";
	const suivi = options.suivi ? `\\s*,\\s*${options.suivi}\\s*:` : '';
	const motif = new RegExp(`\\b${champ}\\s*:\\s*'(${valeur})'${suivi}`, 'g');
	return [...source.matchAll(motif)].map((m) => m[1]);
}

/**
 * Le fichier emploie-t-il ce composant ?
 *
 * ⚠️ `source.includes('<Modale ')` était faux dès qu'un attribut passait à la
 * ligne — Prettier écrit alors `<Modale\n\ttitre="…"`. On exige donc une
 * frontière (espace, saut de ligne, `>` ou `/`), jamais une espace littérale.
 *
 * ⚠️ La frontière est nécessaire : sans elle, `<ModaleConfirmation>` compterait
 * pour `<Modale>`, et le contrôle croirait couvert un écran qui ne l'est pas.
 */
export function emploieComposant(source, nom) {
	return new RegExp(`<${nom}(?=[\\s/>])`).test(source);
}

/**
 * Le corps des tables `export const NOM = { … }` dont le nom correspond.
 *
 * 🔴 Pourquoi lire un BLOC et non une ligne. Le motif d'origine de
 * `lint:taches` était `^	[a-z_]+: '…'` : une tabulation, donc « entrée
 * directe d'une table ». Cette contrainte disait deux choses à la fois — la
 * PROFONDEUR et la mise en page — et seule la première comptait. La remplacer
 * par un motif sans ancre a ramassé toute la source, `couleur: 'badge-green'`
 * comprise, et le contrôle a réclamé qu'on remplace des classes CSS par des
 * libellés de tâche.
 *
 * ⚠️ **C'est le piège symétrique de celui qu'on corrige** : un contrôle rendu
 * insensible au formatage ne doit pas devenir insensible au SENS. Le nom de la
 * table est ce qui porte le sens ; c'est donc lui qu'on lit.
 *
 * ⚠️ Le motif de nom reste large (`LIBELLE_[A-Z_]+`) : une table ajoutée demain
 * est couverte sans qu'on y pense, ce qui était déjà l'intention d'origine.
 *
 * @param {string} source
 * @param {RegExp} motifNom  doit porter le drapeau `g`
 * @returns {string[]} le contenu entre accolades de chaque table retenue
 */
export function corpsDesTables(source, motifNom) {
	const corps = [];
	for (const m of source.matchAll(motifNom)) {
		const ouvrante = source.indexOf('{', m.index);
		if (ouvrante < 0) continue;
		let profondeur = 1;
		let i = ouvrante + 1;
		while (i < source.length && profondeur > 0) {
			if (source[i] === '{') profondeur++;
			else if (source[i] === '}') profondeur--;
			i++;
		}
		//  Une accolade jamais refermée = source tronquée : on ne devine pas.
		if (profondeur === 0) corps.push(source.slice(ouvrante + 1, i - 1));
	}
	return corps;
}

/**
 * L'index de la balise fermante `</nom>`, tolérante à sa coupure.
 *
 * 🔴 Prettier écrit `</button` puis `>` À LA LIGNE quand la balise ouvrante
 * déborde — c'est sa façon de ne pas introduire d'espace significative dans le
 * texte. `src.indexOf('</button>')` ne trouve alors plus rien, et
 * `lint:soumission` annonçait « aucun bouton de soumission repérable » sur des
 * formulaires qui en portaient un (#419).
 *
 * @returns {{ debut: number, fin: number } | null} `debut` = index du `<`,
 *   `fin` = index du `>` fermant. `null` si la balise n'est pas refermée.
 */
export function baliseFermante(source, nom, depuis = 0) {
	const motif = new RegExp(`</${nom}\\s*>`, 'g');
	motif.lastIndex = depuis;
	const m = motif.exec(source);
	return m ? { debut: m.index, fin: m.index + m[0].length - 1 } : null;
}

//  ⚠️ `.then(…)` et NON `await` : le module de test importe celui-ci en retour,
//  et un `await` au niveau supérieur suspendrait l'évaluation d'ici pendant que
//  l'autre l'attend — motif déjà éprouvé sur `lib-analyse-styles`.
if (process.argv.includes('--selftest')) {
	import('./lib-lecture-source.selftest.mjs').then((m) => m.selftest());
}
