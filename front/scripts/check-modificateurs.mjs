/**
 * Garde-fou — **un modificateur ne s'emploie jamais sans sa classe de base.**
 *
 * ## Pourquoi (20/08/2026, signalé à l'écran)
 *
 * *« le bouton enregistrer ne semble pas au standard UX »* — capture à l'appui,
 * onglet Maintenance. Le bouton s'affichait en **gris système**, sans fond bleu,
 * sans arrondi, sans espacement : le rendu par défaut du navigateur au milieu
 * d'un site qui a une charte.
 *
 * La cause tient en un mot manquant :
 *
 * ```svelte
 * <button class="btn-primary">        <!-- ❌ tout le style vit dans .btn -->
 * <button class="btn btn-primary">    <!-- ✅ -->
 * ```
 *
 * `.btn` porte `display`, `padding`, `border-radius`, `font-weight`, `cursor` et
 * la transition. `.btn-primary` ne porte que `background` et `color` — deux
 * propriétés qui, seules sur un `<button>` natif, donnent un bouton bleu carré
 * sans marge intérieure. Presque juste, donc, et c'est ce qui le rend difficile à
 * voir en relisant du code : la classe est là, elle est correctement orthographiée,
 * elle est bien définie dans `app.css`.
 *
 * ## Pourquoi les contrôles existants ne le voyaient pas
 *
 * | Contrôle | Question posée | Verdict ici |
 * |---|---|---|
 * | `lint:classes-nues` | la classe est-elle **définie** quelque part ? | ✅ oui, `app.css:141` |
 * | `svelte-check` | un sélecteur ne matche-t-il **rien** ? | ✅ il matche |
 * | `lint:styles` | un sélecteur d'**élément** est-il nu ? | hors sujet |
 *
 * Les trois répondent juste à leur question. Aucun ne pose celle-ci : **cette
 * classe se suffit-elle à elle-même ?** C'est la cinquième occurrence de la
 * famille « rendu nu en production » (cf. l'en-tête de `check-classes-nues.mjs`),
 * et la première où la classe employée était pourtant définie.
 *
 * ## Comment la question se tranche — sans liste tenue à la main
 *
 * Une liste `['btn-primary', 'btn-danger', …]` divergerait au premier
 * modificateur ajouté, et c'est justement le nouveau que personne n'a en tête.
 * Le contrôle **déduit** la réponse de la feuille de style :
 *
 * > une classe d'une famille (`btn-*`) est un **modificateur** si sa définition
 * > ne déclare **ni `display` ni `cursor`** — les deux propriétés qui font qu'un
 * > élément se comporte comme un bouton. Sinon, elle ne fait que **peindre**.
 *
 * `.btn-icon` déclare `cursor` : elle se suffit, et les vingt-cinq boutons icône
 * du site sont corrects. `.btn-primary`, `.btn-danger`, `.btn-outline` et
 * `.btn-sm` n'en déclarent aucune : elles exigent `.btn`. Le jour où quelqu'un
 * ajoute `.btn-warning { background: … }`, il est couvert sans toucher à ce
 * fichier.
 *
 * ⚠️ Le critère est justifié à `PROPRIETES_AUTONOMES` — et il a été **resserré**
 * une fois : voir là-bas, c'est le compte affiché en fin d'exécution qui a montré
 * qu'il laissait passer la moitié de la famille.
 *
 * ⚠️ **Le cas zéro compte double ici** : si la famille n'est plus trouvée dans
 * `app.css` — renommage, découpage de la feuille — le contrôle ne mesure plus
 * rien et le dirait en vert. Il échoue alors, bruyamment.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { cssGlobal } from './lib-css-global.mjs';
import {
	balisageSeul,
	baliseAvant,
	classesDe,
	reglesCss,
	decouperDeclarations,
} from './lib-analyse-styles.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/**
 * Les familles surveillées : préfixe, et la base qui les porte.
 *
 * Seules les familles sont écrites ici — jamais leurs membres. Une famille est un
 * choix d'architecture (« il existe un objet bouton »), ses membres sont une
 * donnée de la feuille de style, qui se lit.
 */
const FAMILLES = [{ prefixe: 'btn-', base: 'btn' }];

/**
 * Ce qui rend une classe autonome : elle fait de l'élément un BOUTON, elle ne se
 * contente pas de le peindre.
 *
 * ⚠️ Deux propriétés, et pas une de plus — le premier jet en listait sept
 * (`padding`, `border`, `position`…) et ne surveillait plus que **deux** classes
 * sur quatre : `.btn-outline` déclare `border`, `.btn-sm` déclare `padding`, et
 * les deux passaient donc pour autonomes. Ni l'une ni l'autre ne pose un bouton :
 * employées seules, elles rendent une bordure ou une marge sur un élément nu.
 *
 * `display` et `cursor` sont les deux propriétés qui disent « ceci se comporte
 * comme un bouton ». `.btn` déclare les deux, `.btn-icon*` déclarent `cursor` —
 * ce sont exactement les classes qui se suffisent.
 *
 * 🔴 C'est le COMPTE affiché en fin d'exécution qui a révélé le critère trop
 * large : un contrôle qui ne dit pas combien il surveille se croit vert
 * (`standards/04` §1).
 */
const PROPRIETES_AUTONOMES = ['display', 'cursor'];

/**
 * Les modificateurs d'une famille, LUS dans la feuille.
 *
 * On ignore les sélecteurs composés (`.btn-icon:hover`, `.btn-icon[title]::after`)
 * pour décider de l'autonomie : ils décorent un état, ils ne définissent pas la
 * classe. Mais on retient toute classe de la famille **vue** dans un sélecteur,
 * même seulement en `:hover` — sinon une classe définie uniquement au survol
 * passerait pour inexistante et échapperait au contrôle.
 */
export function classerFamille(css, prefixe) {
	const autonomes = new Set();
	const vues = new Set();
	for (const [tete, corps] of reglesCss(css)) {
		const proprietes = new Set(decouperDeclarations(corps).map((d) => d.propriete));
		for (const partie of tete.split(',')) {
			const brut = partie.trim();
			for (const m of brut.matchAll(/\.([A-Za-z][\w-]*)/g)) {
				if (!m[1].startsWith(prefixe)) continue;
				vues.add(m[1]);
				//  Sélecteur SIMPLE seulement (`.btn-icon`, ou une liste de classes
				//  simples) : `.btn-icon:hover` ne définit pas l'autonomie de la classe.
				if (!/^\.[A-Za-z][\w-]*$/.test(brut)) continue;
				if (PROPRIETES_AUTONOMES.some((p) => proprietes.has(p))) {
					autonomes.add(m[1]);
				}
			}
		}
	}
	return { modificateurs: [...vues].filter((c) => !autonomes.has(c)).sort(), vues };
}

/** Les emplois d'un modificateur sans sa base, dans un fichier. */
export function emploisNus(source, modificateurs, base) {
	const balisage = balisageSeul(source);
	const trouves = [];
	for (const m of balisage.matchAll(/\bclass="/g)) {
		const balise = baliseAvant(balisage, m.index);
		if (!balise) continue;
		const classes = classesDe(balisage.slice(m.index - balise.attributs.length + 1, m.index + 400));
		const fautives = classes.filter((c) => modificateurs.includes(c));
		if (!fautives.length || classes.includes(base)) continue;
		trouves.push({
			ligne: balisage.slice(0, m.index).split('\n').length,
			classes: fautives,
		});
	}
	return trouves;
}

function fichiers(dir, sortie = []) {
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) fichiers(chemin, sortie);
		else if (chemin.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

function principal() {
	//  Tous les fragments de style, pas le seul `app.css` qui ne fait plus
	//  qu'importer (#453).
	const css = cssGlobal(RACINE);
	const defauts = [];
	let modificateursTotal = 0;

	for (const { prefixe, base } of FAMILLES) {
		const { modificateurs, vues } = classerFamille(css, prefixe);
		//  🔴 CAS ZÉRO — sans membres trouvés, tout le reste passerait au vert sans
		//  rien lire. Une famille disparue est un renommage à répercuter, pas un
		//  succès (`standards/04` §2).
		if (!vues.size) {
			console.error(
				`✗ famille « ${prefixe}* » introuvable dans app.css : ce contrôle ne mesure plus rien.`,
			);
			process.exit(1);
		}
		if (!modificateurs.length) {
			console.error(
				`✗ famille « ${prefixe}* » : ${vues.size} classe(s) trouvée(s), aucune classée modificateur.\n` +
					`  Soit elles sont toutes autonomes — alors cette famille n'a plus rien à surveiller et sort de FAMILLES —,\n` +
					`  soit le critère d'autonomie ne correspond plus à la feuille.`,
			);
			process.exit(1);
		}
		modificateursTotal += modificateurs.length;

		for (const chemin of fichiers(RACINE)) {
			for (const t of emploisNus(readFileSync(chemin, 'utf8'), modificateurs, base)) {
				defauts.push(
					`${relative(RACINE, chemin)}:${t.ligne} — « ${t.classes.join(' ')} » sans « ${base} »`,
				);
			}
		}
	}

	if (defauts.length) {
		console.error(`✗ ${defauts.length} modificateur(s) employé(s) sans leur classe de base :\n`);
		for (const d of defauts) console.error(`   ${d}`);
		console.error(
			`\n  Un modificateur ne peint que le fond et la couleur. Sans sa base, l'élément\n` +
				`  sort en rendu natif du navigateur — bouton gris carré au milieu de la charte.\n` +
				`  Corriger en ajoutant la base : class="btn btn-primary".`,
		);
		process.exit(1);
	}
	console.log(
		`✓ aucun modificateur employé sans sa base (${modificateursTotal} modificateur(s) surveillé(s))`,
	);
}

// ── Self-test ────────────────────────────────────────────────────────────────

function selftest() {
	const echecs = [];
	const verifier = (nom, condition) => {
		if (!condition) echecs.push(nom);
	};

	//  La feuille RÉELLE, réduite : c'est elle qui doit se laisser classer.
	const css = `
.btn { display: inline-flex; padding: .5rem 1rem; cursor: pointer; }
.btn-primary { background: var(--color-primary); color: #fff; }
.btn-primary:hover:not(:disabled) { background: var(--color-primary-dark); }
.btn-sm { padding: .25rem .6rem; font-size: .875rem; }
.btn-outline { background: transparent; border: 1px solid var(--color-border); color: var(--color-text); }
.btn-icon, .btn-icon-edit { background: transparent; border: none; cursor: pointer; padding: .25rem; }
.btn-icon[aria-pressed="true"] { background: var(--color-primary); }
`;
	const { modificateurs, vues } = classerFamille(css, 'btn-');
	verifier('btn-primary est un modificateur', modificateurs.includes('btn-primary'));
	verifier('btn-icon est autonome', !modificateurs.includes('btn-icon'));
	verifier(
		'btn-icon-edit est autonome (sélecteur groupé)',
		!modificateurs.includes('btn-icon-edit'),
	);
	//  🔴 Les deux que le premier critère laissait passer : `.btn-sm` déclare
	//  `padding`, `.btn-outline` déclare `border` — aucune ne pose un bouton.
	verifier('btn-sm est un modificateur', modificateurs.includes('btn-sm'));
	verifier('btn-outline est un modificateur', modificateurs.includes('btn-outline'));
	verifier('la base elle-même n’est pas de la famille', !vues.has('btn'));

	//  Le défaut RÉEL du 20/08/2026, tel qu'il était écrit.
	const fautif = `<button class="btn-primary" type="submit" disabled={x}>Enregistrer</button>`;
	verifier('le défaut réel est attrapé', emploisNus(fautif, modificateurs, 'btn').length === 1);

	const correct = `<button class="btn btn-primary" type="submit">Enregistrer</button>`;
	verifier('la forme correcte passe', emploisNus(correct, modificateurs, 'btn').length === 0);

	const inverse = `<button class="btn-primary btn">Enregistrer</button>`;
	verifier(
		'l’ordre des classes n’a pas d’importance',
		emploisNus(inverse, modificateurs, 'btn').length === 0,
	);

	//  Un commentaire qui CITE la forme fautive ne doit pas la déclencher — c'est
	//  le défaut qu'ont eu quatre de ces contrôles avant que `balisageSeul` existe.
	const cite = `<!-- ne jamais écrire class="btn-primary" seul -->\n<button class="btn btn-primary">ok</button>`;
	verifier(
		'un commentaire qui cite la faute ne la déclenche pas',
		emploisNus(cite, modificateurs, 'btn').length === 0,
	);

	//  Un bouton icône n'a pas de base à porter.
	const icone = `<button class="btn-icon" aria-label="Modifier">✏️</button>`;
	verifier(
		'un bouton icône n’est pas réclamé',
		emploisNus(icone, modificateurs, 'btn').length === 0,
	);

	if (echecs.length) {
		console.error('✗ self-test : ' + echecs.length + ' cas en échec :');
		for (const e of echecs) console.error('   • ' + e);
		process.exit(1);
	}
	console.log('✓ self-test check-modificateurs : 9 cas');
}

if (process.argv.includes('--selftest')) selftest();
else principal();
