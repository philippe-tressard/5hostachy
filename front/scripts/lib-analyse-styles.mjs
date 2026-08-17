/**
 * lib-analyse-styles.mjs — Fonctions d'ANALYSE pures de `check-styles-nus.mjs`.
 *
 * Module IMPORTÉ, jamais exécuté par la CI : pas de bit x, versionné en 100644.
 *
 * POURQUOI. `check-styles-nus.mjs` a dépassé 500 lignes en recevant le volet
 * « recomposition » (#425), et le garde-fou de modularité — rang 1, sans
 * dérogation — a refusé le push. Même frontière que `scripts/lib/lib-verdicts.sh`
 * côté infra : les fonctions PURES d'un côté, la lecture du disque et la sortie de
 * l'autre.
 *
 * « Pures » veut dire ici : aucune lecture de fichier, aucune écriture, aucun
 * `process.exit`. Elles reçoivent du texte et rendent une structure. C'est ce qui
 * les rend éprouvables sans arborescence — d'où `--selftest`, qui teste le TUYAU
 * (savoir lire une feuille de style et une balise) et non seulement la décision.
 * La leçon est celle du 11/08/2026 : « je testais la décision, pas le tuyau qui la
 * nourrit », et le contrôle était vert sur un script mort.
 *
 * Self-test : node scripts/lib-analyse-styles.mjs --selftest
 */

// ── CSS ──────────────────────────────────────────────────────────────────────

/** Le contenu des blocs `<style>` d'un composant, avec le décalage de ligne. */
export function blocsStyle(source) {
	const blocs = [];
	const motif = /<style[^>]*>([\s\S]*?)<\/style>/g;
	let m;
	while ((m = motif.exec(source)) !== null) {
		blocs.push({ contenu: m[1], ligneDebut: source.slice(0, m.index).split('\n').length });
	}
	return blocs;
}

/**
 * Les sélecteurs d'un bloc CSS réduits à un nom d'ÉLÉMENT parmi `elements`.
 *
 * On lit les en-têtes de règle (ce qui précède un `{`), commentaires retirés. Un
 * sélecteur composé (`.case input`, `input[type=…]`, `input:focus`) ne correspond
 * pas : c'est justement le besoin légitime, et un contrôle qui crie dessus finit
 * désarmé.
 */
export function selecteursNus(css, elements) {
	const sansCommentaires = css.replace(/\/\*[\s\S]*?\*\//g, (c) => c.replace(/[^\n]/g, ' '));
	const trouves = [];
	const motif = /([^{}();@]+)\{/g;
	let m;
	while ((m = motif.exec(sansCommentaires)) !== null) {
		const entete = m[1];
		const ligne = sansCommentaires.slice(0, m.index + entete.length).split('\n').length;
		for (const sel of entete.split(',')) {
			const propre = sel.trim();
			if (elements.includes(propre)) trouves.push({ selecteur: propre, ligne });
		}
	}
	return trouves;
}

/**
 * Les règles `sélecteur { corps }` d'une feuille, `@media` compris — on y descend :
 * une règle qui n'existe qu'en responsive reste une règle qu'on ne doit pas
 * recomposer. Écrit à la main plutôt qu'en expression régulière : les accolades
 * s'imbriquent (`@keyframes`, `@media`), et un motif qui les compterait sans savoir
 * où il est se tromperait de fin de règle, donc de valeurs de référence.
 */
export function reglesCss(source) {
	const src = source.replace(/\/\*[\s\S]*?\*\//g, '');
	const regles = [];
	let tete = '';
	let i = 0;
	while (i < src.length) {
		const c = src[i];
		if (c === '{') {
			const selecteur = tete.trim();
			tete = '';
			if (selecteur.startsWith('@')) {
				i++; // on entre dans le bloc pour lire les règles qu'il contient
				continue;
			}
			let profondeur = 1;
			let j = i + 1;
			while (j < src.length && profondeur > 0) {
				if (src[j] === '{') profondeur++;
				else if (src[j] === '}') profondeur--;
				j++;
			}
			regles.push([selecteur, src.slice(i + 1, j - 1)]);
			i = j;
			continue;
		}
		if (c === '}') {
			tete = '';
			i++;
			continue;
		}
		tete += c;
		i++;
	}
	return regles;
}

/** Une valeur CSS comparable : casse, espaces et `0.5` / `.5` normalisés. */
export function normaliser(valeur) {
	return valeur
		.trim()
		.toLowerCase()
		.replace(/\s+/g, ' ')
		.replace(/(^|[\s(,])0\./g, '$1.');
}

/** Découpe `a:1;b:2` en `[{ propriete, valeur }]`, sans se perdre dans `var(…)`. */
export function decouperDeclarations(texte) {
	const sortie = [];
	let profondeur = 0;
	let courante = '';
	const pousser = () => {
		const sep = courante.indexOf(':');
		if (sep > 0) {
			sortie.push({
				propriete: courante.slice(0, sep).trim().toLowerCase(),
				valeur: normaliser(courante.slice(sep + 1)),
			});
		}
		courante = '';
	};
	for (const c of texte) {
		if (c === '(' || c === '{') profondeur++;
		else if (c === ')' || c === '}') profondeur--;
		if (c === ';' && profondeur === 0) pousser();
		else courante += c;
	}
	pousser();
	return sortie;
}

/** Les déclarations d'un sélecteur EXACT : `Map(propriété → valeur normalisée)`. */
export function declarationsDe(regles, selecteur) {
	const sortie = new Map();
	for (const [tete, corps] of regles) {
		if (!tete.split(',').some((s) => s.trim() === selecteur)) continue;
		for (const decl of decouperDeclarations(corps)) {
			if (decl.propriete) sortie.set(decl.propriete, decl.valeur);
		}
	}
	return sortie;
}

// ── Balisage ─────────────────────────────────────────────────────────────────

/** Neutralise ce qui n'est pas du balisage, en gardant le compte des lignes. */
export function balisageSeul(source) {
	const blanchir = (bloc) => bloc.replace(/[^\n]/g, ' ');
	return source
		.replace(/<!--[\s\S]*?-->/g, blanchir)
		.replace(/<script[\s\S]*?<\/script>/g, blanchir)
		.replace(/<style[\s\S]*?<\/style>/g, blanchir);
}

/**
 * La balise ouvrante qui porte l'attribut trouvé à `pos` : `{ nom, attributs }`.
 * On remonte au `<` précédent en vérifiant qu'aucun `>` ne s'intercale, valeurs
 * d'attributs et expressions Svelte retirées — `on:click={() => saveEdit(t)}` en
 * contient un. Sans ce nettoyage, un `<input>` re-peint à la main passerait pour un
 * `<div>` et échapperait à la signature qui le vise. Rend `null` si la balise n'est
 * pas nommable : l'appelant doit le traiter comme INCONNU, jamais comme « rien ».
 */
export function baliseAvant(source, pos) {
	const debut = source.lastIndexOf('<', pos);
	if (debut < 0) return null;
	let zone = source.slice(debut, pos).replace(/"[^"]*"|'[^']*'/g, ' ');
	//  Du plus profond vers le plus large : `{() => { a; b; }}` s'imbrique, et une
	//  seule passe laisserait le `>` de la flèche — donc croirait la balise fermée.
	for (let precedent = ''; precedent !== zone; ) {
		precedent = zone;
		zone = zone.replace(/\{[^{}]*\}/g, ' ');
	}
	if (zone.includes('>')) return null;
	const m = /^<([A-Za-z][\w.:-]*)/.exec(zone);
	if (!m) return null;
	return { nom: m[1].toLowerCase(), attributs: source.slice(debut, pos) };
}

/** Les classes littérales portées par une balise (les `{expr}` ne sont pas lisibles). */
export function classesDe(attributs) {
	const m = /\bclass="([^"]*)"/.exec(attributs);
	if (!m) return [];
	return m[1]
		.replace(/\{[^{}]*\}/g, ' ')
		.split(/\s+/)
		.filter(Boolean);
}

// ── Self-test ────────────────────────────────────────────────────────────────

/**
 * Chaque cas est un défaut RÉEL de l'historique, pas un exemple inventé : c'est ce
 * qui fait la différence entre un test qui rassure et un test qui attrape.
 */
function selftest() {
	const echecs = [];
	const verifier = (nom, obtenu, attendu) => {
		const a = JSON.stringify(attendu);
		const o = JSON.stringify(obtenu);
		if (o !== a) echecs.push(`${nom}\n      attendu ${a}\n      obtenu  ${o}`);
	};

	//  Les valeurs de référence se lisent, y compris sur un sélecteur en liste et
	//  sur plusieurs lignes — c'est la forme exacte de `.field input, …` d'app.css.
	const regles = reglesCss(`
		/* commentaire { piégeux } */
		.field label { font-size: .875rem; font-weight: 500; }
		.field input,
		.field select { padding: 0.45rem .6rem; border: 1px solid var(--color-border); }
		@media (max-width: 640px) { .largeur-saisie { max-width: 720px; } }
	`);
	verifier(
		'reglesCss + declarationsDe : sélecteur en liste',
		[...declarationsDe(regles, '.field select').keys()],
		['padding', 'border'],
	);
	verifier(
		'declarationsDe : la valeur est normalisée (0.45 → .45)',
		declarationsDe(regles, '.field input').get('padding'),
		'.45rem .6rem',
	);
	verifier(
		'reglesCss : on descend dans les @media',
		declarationsDe(regles, '.largeur-saisie').get('max-width'),
		'720px',
	);
	verifier(
		'declarationsDe : un sélecteur absent ne rend rien (cas zéro de l’appelant)',
		declarationsDe(regles, '.form-actions').size,
		0,
	);

	//  `var(--x, var(--y))` contient une virgule ET des parenthèses ; un découpage
	//  naïf y perdait la propriété suivante.
	verifier(
		'decouperDeclarations : var() imbriqué',
		decouperDeclarations('background:var(--a, var(--b));color:red').map((d) => d.propriete),
		['background', 'color'],
	);

	//  Le défaut du 17/08 : `{() => { a; b; }}` s'imbrique, et le `>` de la flèche
	//  faisait croire la balise fermée — l'`<input>` passait pour un `<div>`.
	const bal = '<input on:input={() => { v = v.trim(); }} class="a b" style="x">';
	//  Null-safe : une mutation qui casse `baliseAvant` doit produire un VERDICT
	//  lisible, pas une exception — un contrôle qui plante en dit moins qu'un
	//  contrôle qui nomme le cas en échec.
	const porteuse = baliseAvant(bal, bal.indexOf('style="')) ?? {};
	verifier('baliseAvant : flèche dans une expression imbriquée', porteuse.nom, 'input');
	verifier('classesDe : les classes littérales', classesDe(porteuse.attributs ?? ''), ['a', 'b']);
	verifier(
		'classesDe : une classe calculée ne se lit pas, et ne doit pas mentir',
		classesDe('<div class="carte {actif ? \'on\' : \'\'}"'),
		['carte'],
	);

	//  Le pendant du cas précédent, et le seul que le garde `>` protège : un
	//  `style="…"` qui n'est PAS un attribut — cité dans du texte, ou dans une
	//  chaîne du balisage. Sans ce garde, il serait attribué à la balise ouvrante
	//  la plus proche, donc rapporté sur un élément qui ne le porte pas.
	const texte = '<p>ne jamais écrire style="border:1px" à la main</p>';
	verifier('baliseAvant : un style= en TEXTE n’est pas un attribut', baliseAvant(texte, texte.indexOf('style="')), null);
	const apresFermeture = '<span class="x"></span> style="color:red"';
	verifier(
		'baliseAvant : un style= après une balise fermée n’est attribué à personne',
		baliseAvant(apresFermeture, apresFermeture.indexOf('style="')),
		null,
	);

	//  Ce qui n'est pas du balisage ne doit produire aucune prise, et les numéros
	//  de ligne doivent rester justes après neutralisation.
	const src = '<div>\n<!-- <input style="border:1px"> -->\n<style>\ninput { width: 100% }\n</style>\n<p style="color:red">x</p>';
	const propre = balisageSeul(src);
	verifier('balisageSeul : le commentaire et le <style> sont neutralisés', propre.match(/style="/g).length, 1);
	verifier('balisageSeul : le compte des lignes est préservé', propre.split('\n').length, src.split('\n').length);
	verifier(
		'selecteursNus : l’élément nu est vu, le sélecteur qualifié ne l’est pas',
		selecteursNus('input { a:1 } .f input { b:2 } input[type="range"] { c:3 }', ['input']).map(
			(s) => s.selecteur,
		),
		['input'],
	);

	if (echecs.length) {
		console.error(`\n✗ lib-analyse-styles --selftest : ${echecs.length} cas en échec\n`);
		for (const e of echecs) console.error(`   ${e}\n`);
		process.exit(1);
	}
	console.log('✓ lib-analyse-styles --selftest : les fonctions d’analyse lisent ce qu’on croit.');
}

if (process.argv.includes('--selftest')) selftest();
