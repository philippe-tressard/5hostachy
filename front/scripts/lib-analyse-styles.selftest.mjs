/**
 * Auto-test de `lib-analyse-styles.mjs` — le TUYAU, pas seulement la décision.
 *
 * Séparé du module le 28/08/2026 (#593) : en recevant `reglesDeSaisie`, le fichier
 * est passé à 524 lignes et le contrôle de modularité — rang 1, sans dérogation —
 * a refusé de le laisser grossir. La frontière choisie est celle qui coupe le
 * moins de choses en deux : le code analysé d'un côté, ce qui l'éprouve de
 * l'autre. Aucune fonction d'analyse n'a été déplacée.
 *
 * ⚠️ La commande ne change PAS : `node scripts/lib-analyse-styles.mjs --selftest`,
 * qui est ce que lance la CI. Le module principal importe celui-ci DYNAMIQUEMENT,
 * et seulement sous cette option — un import statique ferait un cycle, et
 * déplacer la commande aurait laissé la CI lancer un fichier devenu muet.
 *
 * Chaque cas est un défaut RÉEL de l'historique, pas un exemple inventé : c'est ce
 * qui fait la différence entre un test qui rassure et un test qui attrape.
 */
import {
	baliseAvant,
	balisageSeul,
	classesDe,
	decouperDeclarations,
	declarationsDe,
	globalesDeFeuille,
	reglesCss,
	reglesDeSaisie,
	selecteursNus,
} from './lib-analyse-styles.mjs';

// ── Self-test ────────────────────────────────────────────────────────────────

/**
 * Chaque cas est un défaut RÉEL de l'historique, pas un exemple inventé : c'est ce
 * qui fait la différence entre un test qui rassure et un test qui attrape.
 */
export function selftest() {
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
	//  #607 — le pendant exact, et c'est ce qui distingue les deux usages : pour
	//  COMPARER une règle d'écran à la charte, il faut la valeur de BASE. Le
	//  relevé du 28/08 comparait à la règle du téléphone et annonçait des
	//  recompositions qui n'existaient pas.
	const horsMedia = reglesCss(
		`.form-grid { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: .75rem; }
		 @media (max-width: 640px) { .form-grid { grid-template-columns: 1fr !important; } }`,
		{ horsMedia: true },
	);
	verifier(
		'reglesCss horsMedia : la valeur de BASE, pas celle du téléphone',
		declarationsDe(horsMedia, '.form-grid').get('grid-template-columns'),
		'repeat(auto-fit, minmax(220px, 1fr))',
	);
	verifier(
		'reglesCss horsMedia : un @media imbriqué est sauté ENTIER, pas à moitié',
		reglesCss(
			`@media print { @media (min-width: 40em) { .x { color: red } } } .y { color: blue }`,
			{ horsMedia: true },
		).map(([s]) => s),
		['.y'],
	);
	verifier(
		'declarationsDe : un sélecteur absent ne rend rien (cas zéro de l’appelant)',
		declarationsDe(regles, '.form-actions').size,
		0,
	);

	//  #562 — les trois formes qui cohabitaient dans le dépôt le 28/08/2026, et
	//  qu'un seul regex `:global\(…\)` confondait : la fuite pure (les huit badges
	//  qui redéfinissaient la charte depuis quatre pages), la fuite légitime (le
	//  HTML injecté par l'éditeur riche, qu'aucune règle scopée n'atteint) et
	//  l'imbriquée (un composant qui habille l'élément d'un enfant).
	const glob = globalesDeFeuille(`
		:global(.badge-orange) { background: #fef3c7; }
		:global(.custom-content p) { margin-bottom: .5rem; }
		.history-item:hover :global(.ec-titre) { color: red; }
		.bloc > :global(.field:last-child) { margin-bottom: 0; }
	`);
	verifier(
		'globalesDeFeuille : une REDÉFINITION pure est nommée',
		glob.fuites.filter((f) => f.classeSeule).map((f) => f.classeSeule),
		['badge-orange'],
	);
	verifier(
		'globalesDeFeuille : une fuite qui vise du contenu injecté n’est pas une redéfinition',
		glob.fuites.filter((f) => !f.classeSeule).map((f) => f.selecteur),
		[':global(.custom-content p)'],
	);
	verifier(
		'globalesDeFeuille : un :global() SOUS un ancêtre scopé n’est pas une fuite',
		glob.imbriquees.map((i) => i.selecteur),
		['.history-item:hover :global(.ec-titre)', '.bloc > :global(.field:last-child)'],
	);
	//  Cas zéro de l'appelant : une feuille sans `:global()` ne doit rien inventer.
	verifier(
		'globalesDeFeuille : cas zéro',
		globalesDeFeuille('.a { color: red } @media (max-width: 640px) { .b { color: blue } }').fuites.length,
		0,
	);
	//  Un sélecteur en LISTE : chaque partie se juge séparément, sinon la fuite se
	//  cache derrière une partie scopée écrite avant elle.
	verifier(
		'globalesDeFeuille : la fuite se voit même en 2ᵉ position d’une liste',
		globalesDeFeuille('.a, :global(.badge-red) { color: red }').fuites.map((f) => f.classeSeule),
		['badge-red'],
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

	//  #593 — le pendant EXACT du cas précédent, et c'est tout l'intérêt : ce que
	//  `selecteursNus` laisse passer parce que c'est qualifié, `reglesDeSaisie` le
	//  regarde. `.reponse-form textarea` repeignait `.field textarea` — champ blanc
	//  au milieu d'un site aux champs beiges — et lint:styles était vert.
	const saisie = reglesDeSaisie(
		`
			textarea { a: 1 }
			.reponse-form textarea { padding: .45rem .6rem }
			.filtres > select:focus { border: 1px solid red }
			.case input[type="checkbox"] { width: auto }
			.bloc .champ { color: red }
			label input { margin: 0 }
			@media (max-width: 640px) { .etroit input { padding: 0 } }
		`,
		['input', 'select', 'textarea'],
	);
	verifier(
		'reglesDeSaisie : le NU est laissé à selecteursNus, le qualifié est vu',
		saisie.map((r) => r.selecteur),
		[
			'.reponse-form textarea',
			'.filtres > select:focus',
			'.case input[type="checkbox"]',
			'label input',
			'.etroit input',
		],
	);
	verifier(
		'reglesDeSaisie : c’est la CIBLE du sélecteur qui compte, pas l’ancêtre',
		saisie.map((r) => r.element),
		['textarea', 'select', 'input', 'input', 'input'],
	);
	verifier(
		'reglesDeSaisie : les déclarations sont lues et normalisées',
		saisie[0].declarations.map((d) => `${d.propriete}=${d.valeur}`),
		['padding=.45rem .6rem'],
	);
	//  Cas zéro de l'appelant : une feuille sans règle de saisie ne doit rien
	//  inventer — c'est ce que le PLANCHER du contrôle surveille en grand.
	verifier(
		'reglesDeSaisie : cas zéro',
		reglesDeSaisie('.a { color: red } .b .c { color: blue }', ['input']).length,
		0,
	);
	//  Un `:global(input)` a une portée PLUS large, jamais plus étroite : l'exclure
	//  ferait un angle mort à l'endroit le plus exposé.
	verifier(
		'reglesDeSaisie : un :global(input) reste vu',
		reglesDeSaisie('.riche :global(input) { padding: 0 }', ['input']).map((r) => r.element),
		['input'],
	);

	if (echecs.length) {
		console.error(`\n✗ lib-analyse-styles --selftest : ${echecs.length} cas en échec\n`);
		for (const e of echecs) console.error(`   ${e}\n`);
		process.exit(1);
	}
	console.log('✓ lib-analyse-styles --selftest : les fonctions d’analyse lisent ce qu’on croit.');
}


