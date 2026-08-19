/**
 * Garde-fou — **un champ de saisie qui porte un libellé vit dans un `.field`**.
 *
 * ## Pourquoi (#374 puis #413)
 *
 * `.field` est la définition unique du champ : sa mise en page, son fond beige,
 * son contour de focus, son état lecture seule. Une page qui réécrit ce motif
 * sous un autre nom obtient un champ qui *ressemble* — jusqu'à ce qu'il diverge.
 *
 * Le 19/08/2026, le dépôt en portait **six** nomenclatures concurrentes :
 * `.field-label` (3 définitions incompatibles), `.form-group` (3), `.champ`,
 * `.ah-champ`/`.ah-select`, `.email-label`/`.email-input`, et le `<label>` nu
 * appuyé sur une règle `.form-grid label`. Trois fichiers redéfinissaient même
 * `.field` — le nom canonique — avec d'autres valeurs.
 *
 * Deux d'entre elles ne renvoyaient à **aucune** définition (`OngletWhatsApp`,
 * `acces-securite`) : extraites d'`admin` sans ses styles, elles rendaient leurs
 * champs nus en production. C'est la régression des pastilles nues, appliquée
 * cette fois au formulaire.
 *
 * ## Ce que ce contrôle cherche
 *
 * Tout `<input>` de **saisie**, `<select>` ou `<textarea>` qui est **associé à un
 * libellé** — enveloppé par un `<label>`, ou visé par un `for=` du fichier —
 * doit avoir `field` dans les classes d'un de ses ancêtres, ou dans les siennes.
 *
 * 🔴 **Les trois formes d'écriture comptent, et c'est tout l'enseignement de
 * #413.** Le relevé de #374 ne cherchait qu'un `<label>` enveloppant sur une
 * ligne ; il a manqué la forme multi-lignes (deux champs de l'écran Admin), puis
 * la forme « libellé frère » reliée par `for=` — celle-là trouvée **en production
 * par l'utilisateur**, sur un fond blanc au milieu d'un site beige. Un relevé par
 * motif textuel ne prouve rien sur ce qu'il n'a pas cherché : ce contrôle-ci lit
 * donc l'ARBRE des balises, où les trois formes se ramènent à une seule question.
 *
 * Éprouvé en réintroduisant les trois formes une par une — voir `--selftest`.
 *
 * ## Ce qu'il ne cherche PAS
 *
 * Un contrôle **sans** libellé : filtre de barre d'outils, recherche, renommage
 * en ligne. Ce n'est pas un champ de formulaire, et l'y forcer donnerait des
 * dérogations à la pelle — donc un contrôle qu'on désarme (`standards/04`).
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/**
 * Champs LIBELLÉS qui vivent hors d'un `.field`, **avec la raison**.
 * Chemin relatif à `src/`, en séparateurs POSIX → raison.
 * Une exception qui ne sert plus fait échouer le contrôle.
 */
const EXCEPTIONS = {
	'routes/(app)/calendrier/+page.svelte':
		"Les deux sélecteurs « Exercice » et « Bâtiment » de la barre du kanban : ce sont " +
		"des filtres de VUE, pas des champs d'un formulaire. Ils portent un libellé parce " +
		"qu'on doit savoir ce qu'ils filtrent, et vivent sur une ligne dans `.kanban-toolbar` " +
		'— un `.field`, qui empile en colonne sur toute la largeur, les sortirait de la barre.',
};

/** `<input type="…">` qui se saisissent. Les autres sont des contrôles. */
const TYPES_DE_SAISIE = new Set([
	'text', 'email', 'tel', 'url', 'password', 'number', 'date', 'time',
	'datetime-local', 'search', 'month', 'week',
]);

/** Balises sans fermeture : elles n'empilent rien. */
const BALISES_VIDES = new Set([
	'br', 'hr', 'img', 'meta', 'link', 'source', 'area', 'base', 'col', 'embed',
	'track', 'wbr', 'input',
]);

/** Nombre minimal de champs libellés attendus — cas zéro. */
const PRISES_MINIMALES = 120;

function composants(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...composants(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

/** Neutralise script, style et commentaires SANS déplacer les numéros de ligne. */
function gabarit(source) {
	const blanc = (m) => m.replace(/[^\n]/g, ' ');
	return source
		.replace(/<script[\s\S]*?<\/script>/g, blanc)
		.replace(/<style[\s\S]*?<\/style>/g, blanc)
		.replace(/<!--[\s\S]*?-->/g, blanc);
}

const CLASSE = /class\s*=\s*"([^"]*)"|class\s*=\s*'([^']*)'/;
const porteField = (classes) => classes.split(/\s+/).includes('field');

/**
 * Relève les champs libellés hors `.field` d'un gabarit.
 * Exporté de fait pour `--selftest` : c'est la fonction PURE du contrôle.
 */
export function releve(source, chemin = '?') {
	const src = gabarit(source);
	//  Les `for=` du fichier : ils désignent des champs FRÈRES, la 3ᵉ forme.
	const cibles = new Set([...src.matchAll(/\bfor\s*=\s*["']([^"']+)["']/g)].map((m) => m[1]));
	const pile = [];
	const trouves = [];
	let libelles = 0;

	const balise = /<(\/?)([a-zA-Z][\w-]*)((?:"[^"]*"|'[^']*'|\{[^}]*\}|[^>"'])*?)(\/?)>/g;
	let m;
	while ((m = balise.exec(src)) !== null) {
		const [, fermante, nom, attributs, autofermante] = m;
		const tag = nom.toLowerCase();

		if (fermante) {
			for (let i = pile.length - 1; i >= 0; i--) {
				if (pile[i].tag === tag) { pile.length = i; break; }
			}
			continue;
		}

		const trouvee = CLASSE.exec(attributs);
		const classes = (trouvee && (trouvee[1] ?? trouvee[2])) || '';

		if (tag === 'input' || tag === 'select' || tag === 'textarea') {
			const type = (/type\s*=\s*"([^"]*)"/.exec(attributs) || [])[1];
			//  Un `type` dynamique (`type={…}`) ou absent sur un `<input>` : on ne
			//  conclut pas — ce contrôle ne cherche que la saisie qu'il reconnaît.
			if (tag === 'input' && (!type || !TYPES_DE_SAISIE.has(type))) continue;

			const id = (/\bid\s*=\s*["']([^"']+)["']/.exec(attributs) || [])[1];
			const enveloppe = pile.some((e) => e.tag === 'label');
			const frere = Boolean(id && cibles.has(id));
			if (!enveloppe && !frere) continue; // pas de libellé : hors périmètre

			libelles++;
			if (pile.some((e) => porteField(e.classes)) || porteField(classes)) continue;

			trouves.push({
				chemin,
				ligne: src.slice(0, m.index).split('\n').length,
				tag,
				type,
				forme: enveloppe ? 'libellé enveloppant' : 'libellé frère (for=)',
				contexte: pile.slice(-2).map((e) => e.tag + (e.classes ? '.' + e.classes.split(/\s+/)[0] : '')).join(' > '),
			});
			continue;
		}

		if (!autofermante && !BALISES_VIDES.has(tag) && /^[a-z]/.test(nom)) {
			pile.push({ tag, classes });
		}
	}
	return { trouves, libelles };
}

// ── `--selftest` : le contrôle doit être VU refuser les TROIS formes ──────────
if (process.argv.includes('--selftest')) {
	const cas = [
		['libellé enveloppant, sur une ligne',
			'<div class="form-grid"><label>Question *<input type="text" bind:value={q} /></label></div>'],
		['libellé enveloppant, multi-lignes',
			'<div class="form-grid">\n<label>Statut\n<select bind:value={s}><option>a</option></select>\n</label>\n</div>'],
		['libellé frère, relié par for=',
			'<div><label for="faq-q">Question *</label>\n<input id="faq-q" class="input-field" type="text" /></div>'],
	];
	let echecs = 0;
	for (const [nom, gabaritCas] of cas) {
		const { trouves } = releve(gabaritCas, 'cas');
		const vu = trouves.length === 1;
		console.log(`${vu ? '✓' : '✗'} refusé — ${nom}`);
		if (!vu) echecs++;
	}
	//  Le symétrique : la même écriture DANS un `.field` passe. Sans lui, un
	//  contrôle qui refuserait tout aurait l'air de marcher.
	const conformes = [
		['libellé enveloppant dans un .field',
			'<label class="field">Question *<input type="text" /></label>'],
		['libellé frère dans un .field',
			'<div class="field"><label for="x">Sujet</label><input id="x" type="text" /></div>'],
		['contrôle SANS libellé : hors périmètre',
			'<div class="filters"><input type="search" placeholder="Rechercher" /></div>'],
	];
	for (const [nom, gabaritCas] of conformes) {
		const { trouves } = releve(gabaritCas, 'cas');
		const vu = trouves.length === 0;
		console.log(`${vu ? '✓' : '✗'} accepté — ${nom}`);
		if (!vu) echecs++;
	}
	if (echecs) {
		console.error(`\n✗ ${echecs} cas d'autotest en échec.`);
		process.exit(1);
	}
	console.log('\n✓ Autotest : les trois formes d’écriture sont refusées, et acceptées dans un `.field`.');
	process.exit(0);
}

// ── Le relevé ────────────────────────────────────────────────────────────────
const fichiers = composants(RACINE);
if (fichiers.length === 0) {
	console.error("✗ Cas zéro : aucun composant analysé — l'arborescence a changé.");
	console.error('Ne pas lire ceci comme un succès.');
	process.exit(1);
}

const erreurs = [];
const exceptionsServies = new Set();
let libelles = 0;

for (const chemin of fichiers) {
	const relatif = relative(RACINE, chemin).replace(/\\/g, '/');
	const r = releve(readFileSync(chemin, 'utf8'), relatif);
	libelles += r.libelles;
	for (const t of r.trouves) {
		if (relatif in EXCEPTIONS) { exceptionsServies.add(relatif); continue; }
		erreurs.push(
			`${t.chemin}:${t.ligne} — <${t.tag}${t.type ? ` type="${t.type}"` : ''}> ` +
				`[${t.forme}] hors d'un \`.field\`, sous [${t.contexte || 'racine'}].`,
		);
	}
}

if (libelles < PRISES_MINIMALES) {
	console.error(
		`✗ Cas zéro : ${libelles} champ(s) libellé(s) reconnu(s), ${PRISES_MINIMALES} attendus au minimum.`,
	);
	console.error(
		"Le front en portait 196 le 19/08/2026. Un effondrement du relevé dit que le\n" +
			"contrôle a cessé de voir, pas que le défaut a disparu (`standards/04` §2).",
	);
	process.exit(1);
}

const mortes = Object.keys(EXCEPTIONS).filter((f) => !exceptionsServies.has(f));
if (mortes.length) {
	console.error('✗ Exception déclarée et jamais servie — la retirer de `EXCEPTIONS` :\n');
	for (const f of mortes) console.error(`  • ${f}`);
	console.error(
		"\nSoit le fichier n'existe plus, soit il a été mis en conformité. Dans les deux\n" +
			'cas la dérogation ne protège plus rien, et elle masquera le prochain écart.\n',
	);
	process.exit(1);
}

if (erreurs.length) {
	console.error('✗ Champ libellé hors du motif `.field` :\n');
	for (const e of erreurs) console.error(`  • ${e}`);
	console.error(
		'\n🔴 Règle : un `<input>` de saisie, `<select>` ou `<textarea>` qui porte un\n' +
			'   libellé vit dans un `.field` — la définition unique du champ (`app.css`).\n' +
			'   Les deux écritures conviennent :\n' +
			'     <label class="field">Titre *<input type="text" /></label>\n' +
			'     <div class="field"><label for="x">Titre *</label><input id="x" …></div>\n' +
			'   Une page qui réécrit ce motif sous un autre nom obtient un champ qui\n' +
			'   RESSEMBLE, jusqu’à ce qu’il diverge — six nomenclatures coexistaient\n' +
			'   avant #413, dont deux qui ne renvoyaient à aucune définition.\n' +
			'   Une exception se DÉCLARE dans `EXCEPTIONS` avec sa raison.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Champs : ${libelles} champs libellés dans ${fichiers.length} composants — ` +
		`tous dans un \`.field\`, ${Object.keys(EXCEPTIONS).length} exception déclarée et servie.`,
);
