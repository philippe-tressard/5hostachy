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
 * Les règles d'un bloc `<style>` dont le sélecteur se termine par un élément de
 * SAISIE **qualifié** — `.reponse-form textarea`, `.filtres > select:focus`.
 *
 * 🔴 Pourquoi cette fonction existe (#593, 28/08/2026). `selecteursNus()` refuse
 * `textarea` nu, et c'est sa raison d'être : il déborderait sur les voisins. Mais
 * qualifier un sélecteur le rend inoffensif pour les VOISINS, **pas conforme à la
 * charte**. `.reponse-form textarea` repeignait à la main la peau de `.field
 * textarea` — un champ blanc au milieu d'un site aux champs beiges — et le
 * contrôle était vert : le volet qui compare les propriétés à `app.css` ne
 * regardait que les `style="…"` EN LIGNE.
 *
 * Les deux questions sont distinctes, et il en fallait deux fonctions :
 *
 * | Question | Fonction |
 * |---|---|
 * | ce sélecteur déborde-t-il sur ce qu'il ne vise pas ? | `selecteursNus` |
 * | ce sélecteur **recompose**-t-il une classe de la charte ? | celle-ci |
 *
 * Un sélecteur NU est volontairement exclu ici : `selecteursNus` le refuse déjà,
 * et le signaler deux fois ferait deux verdicts pour un seul défaut.
 *
 * @param css le contenu d'un bloc `<style>`
 * @param elements les noms d'éléments à surveiller (`['input','select','textarea']`)
 * @returns `[{ selecteur, element, declarations, ligne }]`, ligne relative au bloc
 */
export function reglesDeSaisie(css, elements) {
	const src = css.replace(/\/\*[\s\S]*?\*\//g, (c) => c.replace(/[^\n]/g, ' '));
	const trouvees = [];
	let tete = '';
	let i = 0;
	while (i < src.length) {
		const c = src[i];
		if (c === '{') {
			const selecteur = tete.trim();
			const ligne = src.slice(0, i).split('\n').length;
			tete = '';
			if (selecteur.startsWith('@')) {
				i++; // on descend : une règle en @media reste une règle
				continue;
			}
			let profondeur = 1;
			let j = i + 1;
			while (j < src.length && profondeur > 0) {
				if (src[j] === '{') profondeur++;
				else if (src[j] === '}') profondeur--;
				j++;
			}
			const corps = src.slice(i + 1, j - 1);
			for (const part of selecteur.split(',')) {
				const propre = part.trim().replace(/\s+/g, ' ');
				//  Nu : c'est le domaine de `selecteursNus`, pas le nôtre.
				if (!propre || elements.includes(propre)) continue;
				const element = elementCible(propre, elements);
				if (!element) continue;
				trouvees.push({
					selecteur: propre,
					element,
					declarations: decouperDeclarations(corps),
					ligne,
				});
			}
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
	return trouvees;
}

/**
 * L'élément que vise le DERNIER compound d'un sélecteur, ou `null`.
 *
 * `.f textarea:focus` → `textarea` · `.f > input[type=x]` → `input` ·
 * `.f .champ` → `null` (c'est une classe, pas un élément) ·
 * `label input` → `input` (on juge la CIBLE, pas l'ancêtre).
 *
 * ⚠️ `:global(input)` rend `input` : la portée y est plus large encore, jamais
 * plus étroite — l'exclure ferait un angle mort à l'endroit le plus exposé.
 */
function elementCible(selecteur, elements) {
	const dernier = selecteur.split(/\s*[>+~]\s*|\s+/).filter(Boolean).pop();
	if (!dernier) return null;
	const nu = dernier.replace(/^:global\(/, '').replace(/\)$/, '');
	const m = /^([A-Za-z][\w-]*)/.exec(nu);
	return m && elements.includes(m[1]) ? m[1] : null;
}

/**
 * Les règles `sélecteur { corps }` d'une feuille, `@media` compris — on y descend :
 * une règle qui n'existe qu'en responsive reste une règle qu'on ne doit pas
 * recomposer. Écrit à la main plutôt qu'en expression régulière : les accolades
 * s'imbriquent (`@keyframes`, `@media`), et un motif qui les compterait sans savoir
 * où il est se tromperait de fin de règle, donc de valeurs de référence.
 *
 * 🔴 `{ horsMedia: true }` fait le contraire, et il y a une raison précise (#607).
 * Pour comparer une règle d'écran à **la** valeur de la charte, il faut la valeur
 * de BASE : en descendant dans les `@media`, la dernière lue gagne, et c'est la
 * valeur **mobile** qui sert alors de référence. Le relevé du 28/08/2026 annonçait
 * ainsi `.form-grid` recomposé partout, parce qu'il comparait à
 * `grid-template-columns: 1fr !important` — la règle du téléphone, qu'aucun écran
 * de bureau n'écrit jamais.
 *
 * Un relevé qui compte des cas inexistants fait perdre confiance dans les vrais :
 * c'est pour cela que la correction précède la correction.
 */
export function reglesCss(source, { horsMedia = false } = {}) {
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
				if (!horsMedia) {
					i++; // on entre dans le bloc pour lire les règles qu'il contient
					continue;
				}
				//  On SAUTE le bloc entier : sa fin se trouve en comptant les
				//  accolades, `@media` pouvant en contenir d'autres.
				let profondeur = 1;
				let j = i + 1;
				while (j < src.length && profondeur > 0) {
					if (src[j] === '{') profondeur++;
					else if (src[j] === '}') profondeur--;
					j++;
				}
				i = j;
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

/**
 * Les `:global(…)` d'une feuille, **triés par ce qu'ils atteignent réellement**.
 *
 * 🔴 C'est la distinction que `lint:classes-nues` ne faisait pas (#562), et elle
 * n'est pas cosmétique — les deux formes n'ont pas la même portée :
 *
 * | Écrit dans un composant | Ce que la règle atteint |
 * |---|---|
 * | `.carte :global(.titre)` | les `.titre` **descendants d'un `.carte` de ce composant** |
 * | `:global(.titre)` | **tous les `.titre` du site**, dès que la CSS du composant est chargée |
 *
 * La seconde forme est une **fuite** : Svelte n'y met aucune barrière, et
 * SvelteKit charge la CSS d'une page à la visite — sans la décharger ensuite. Une
 * règle écrite là redéfinit donc la charte pour tout le reste de la session, et
 * pour lui seul. Le badge « ⚡ Urgente » n'avait pas la même teinte selon qu'on
 * était passé par `tickets` ou non.
 *
 * `classeSeule` porte le nom quand le sélecteur est **exactement** `:global(.x)` —
 * le cas où la fuite est une pure redéfinition. `:global(.custom-content p)` cible
 * du HTML injecté par un éditeur riche, qu'aucune règle scopée ne peut atteindre :
 * c'est le besoin légitime, et il rend `classeSeule: null`.
 *
 * @param css le contenu d'un bloc `<style>`
 * @returns `{ fuites: [{ selecteur, classeSeule }], imbriquees: [{ selecteur }] }`
 */
export function globalesDeFeuille(css) {
	const fuites = [];
	const imbriquees = [];
	for (const [tete] of reglesCss(css)) {
		for (const part of tete.split(',')) {
			const selecteur = part.trim().replace(/\s+/g, ' ');
			if (!selecteur.includes(':global(')) continue;
			if (!selecteur.startsWith(':global(')) {
				imbriquees.push({ selecteur });
				continue;
			}
			const m = /^:global\(\s*\.([A-Za-z][\w-]*)\s*\)$/.exec(selecteur);
			fuites.push({ selecteur, classeSeule: m ? m[1] : null });
		}
	}
	return { fuites, imbriquees };
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

// ── Self-test ─────────────────────────────────────────────────────────────────────────────

//  Les cas vivent dans `lib-analyse-styles.selftest.mjs` depuis le 28/08/2026
//  (#593) : ce fichier a dépassé 500 lignes et la modularité est de rang 1.
//  L'import est DYNAMIQUE et sous l'option — sinon les trois contrôles qui
//  importent ce module chargeraient aussi 200 lignes de cas de test.
//
//  ⚠️ `.then(…)` et NON `await` : le module de test importe celui-ci en retour, et
//  un `await` au niveau supérieur suspendrait l'évaluation d'ici pendant que
//  l'autre l'attend. Node l'a dit sans ambiguïté à l'écriture — « unsettled
//  top-level await », code 13, aucun cas exécuté. Sans le `.then`, la commande
//  que lance la CI ne testerait plus rien, et le dirait à peine.
if (process.argv.includes('--selftest')) {
	import('./lib-analyse-styles.selftest.mjs').then((m) => m.selftest());
}
