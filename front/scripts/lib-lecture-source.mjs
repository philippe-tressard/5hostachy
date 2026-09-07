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

/**
 *  ── Lire une DÉCLARATION comme un littéral, sans exécuter le fichier ──
 *
 *  🔴 Déplacé ici depuis `check-etats.mjs` le 08/09/2026, qui dépassait son
 *  plafond de modularité. Ce bloc répond à une question qui n'est pas celle du
 *  cadre d'interface : « comment lire une table déclarée en TypeScript sans
 *  évaluer le code qui l'entoure ? » — et c'est exactement ce que ce module
 *  existe pour faire.
 *
 *  ⚠️ `echec` est passé par l'appelant plutôt qu'importé : un module de lecture
 *  ne décide pas de ce qui est une faute. Il rapporte, l'appelant tranche.
 */
//  ── Lecture d'un littéral TypeScript ────────────────────────────────────────
//
//  Node ne sait pas importer un `.ts`. Plutôt que de relire la déclaration à
//  coups d'expressions régulières — ce qui reviendrait à en tenir une seconde
//  lecture, libre de diverger —, on EXTRAIT le littéral et on l'évalue tel quel.
//  Le scanner saute chaînes et commentaires : une accolade dans un texte
//  d'explication ne doit pas fermer l'objet.
export function litteralApres(source, index) {
	//  Le littéral commence à la PREMIÈRE des deux ouvertures possibles : chercher
	//  `{` puis se rabattre sur `[` ferait ouvrir un tableau sur l'accolade d'une
	//  déclaration suivante, à des centaines de lignes de là.
	const candidats = [source.indexOf('{', index), source.indexOf('[', index)].filter((n) => n >= 0);
	if (candidats.length === 0) return null;
	let i = Math.min(...candidats);
	const ouvrants = { '{': '}', '[': ']' };
	const pile = [ouvrants[source[i]]];
	const debut = i;
	i += 1;
	while (i < source.length && pile.length) {
		const c = source[i];
		if (c === '/' && source[i + 1] === '/') {
			i = source.indexOf('\n', i);
			if (i < 0) return null;
			continue;
		}
		if (c === '/' && source[i + 1] === '*') {
			i = source.indexOf('*/', i);
			if (i < 0) return null;
			i += 2;
			continue;
		}
		if (c === "'" || c === '"' || c === '`') {
			i += 1;
			while (i < source.length && source[i] !== c) {
				if (source[i] === '\\') i += 1;
				i += 1;
			}
			i += 1;
			continue;
		}
		if (c === '{' || c === '[') pile.push(ouvrants[c]);
		else if (c === '}' || c === ']') {
			if (c !== pile[pile.length - 1]) return null;
			pile.pop();
		}
		i += 1;
	}
	return pile.length ? null : source.slice(debut, i);
}

/** Constantes de chaîne du fichier — `const DETTE_API = '#431';` et consorts. */
export function prelude(source) {
	const lignes = [];
	const re = /^const\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*('[^']*'|"[^"]*")\s*;/gm;
	let m;
	while ((m = re.exec(source))) lignes.push(`const ${m[1]} = ${m[2]};`);
	return lignes.join('\n');
}

/**
 *  Les divergences PARTAGÉES, déclarées dans `types.ts` et citées par référence.
 *
 *  🔴 Ce contrôle évalue chaque déclaration comme un LITTÉRAL pur — c'est ce qui
 *  le rend sûr, il n'exécute pas le code du dépôt. Mais une explication écrite
 *  quatre fois à l'identique doit pouvoir devenir une constante, et le contrôle
 *  refusait alors de lire l'entité entière : « DIFFUSION_NE_SE_LIT_PAS is not
 *  defined » (#824).
 *
 *  Le remède n'est pas de renoncer à la factorisation, ni d'évaluer du code
 *  arbitraire : c'est d'injecter dans le contexte les constantes `Divergence`
 *  que `types.ts` exporte — un jeu fermé, lu au même endroit que le reste du
 *  cadre. Une entité ne peut donc citer que ce que le cadre déclare.
 *
 *  ⚠️ `Divergence` et rien d'autre. Étendre à toute constante exportée
 *  reviendrait à évaluer le fichier, ce que ce contrôle refuse depuis toujours.
 */
export function preludePartage(srcTypes) {
	const lignes = [];
	const re = /export\s+const\s+([A-Z][A-Z0-9_]*)\s*:\s*Divergence\s*=\s*(\{[\s\S]*?\n\});/g;
	let m;
	while ((m = re.exec(srcTypes))) lignes.push(`const ${m[1]} = ${m[2]};`);
	return lignes.join('\n');
}

export function evaluer(source, nom, litteral, chemin, { partage = '', echec }) {
	try {
		return new Function(`${partage}\n${prelude(source)}\nreturn (${litteral});`)();
	} catch (e) {
		echec(`${chemin} — impossible de lire le littéral \`${nom}\` : ${e.message}`);
		return null;
	}
}

export function extraire(source, nom, chemin, { partage = '', echec }) {
	const ancre = source.search(new RegExp(`export\\s+const\\s+${nom}\\b`));
	if (ancre < 0) {
		echec(`${chemin} — \`${nom}\` est introuvable.`);
		return null;
	}
	//  ⚠️ On part de l'`=`, pas de l'ancre : une annotation de type porte des
	//  crochets (`readonly IdSection[]`), et démarrer avant elle faisait lire un
	//  tableau VIDE — un cas zéro qui se serait présenté comme « 0 section lue ».
	const affectation = source.slice(ancre).search(/=(?![=>])/);
	if (affectation < 0) {
		echec(`${chemin} — \`${nom}\` n'est pas une affectation.`);
		return null;
	}
	const litteral = litteralApres(source, ancre + affectation);
	if (!litteral) {
		echec(`${chemin} — le littéral de \`${nom}\` n'est pas équilibré.`);
		return null;
	}
	return evaluer(source, nom, litteral, chemin, { partage, echec });
}
