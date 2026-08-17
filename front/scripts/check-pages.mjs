#!/usr/bin/env node
/**
 * Garde-fou : la table des pages ne se recopie pas.
 *
 * Le 17/08/2026 (#401), l'identité des pages — identifiant de configuration, route,
 * libellé de menu, icône, descriptif — vivait dans DEUX tables qui ne se
 * connaissaient pas : `NAV_DEFAULTS` + `DEFAULT_HREFS` dans `Nav.svelte`, et
 * `pagesDefaults` dans l'écran `admin`. Elles avaient déjà divergé de trois façons,
 * et **aucune n'était visible** :
 *
 *   1. les deux ordres par défaut n'étaient pas le même ;
 *   2. `profil` et `notifications` étaient réordonnables sans être dans le menu — le
 *      geste était enregistré, puis écarté en silence ;
 *   3. `delegations` était dans le menu sans être dans l'écran : ni positionnable,
 *      ni renommable.
 *
 * C'est le même motif que les périmètres (#316), les canaux de notification et les
 * libellés de tâches : une table recopiée finit toujours par diverger de celle
 * qu'elle copie, et deux listes d'accord entre elles ne prouvent rien.
 *
 * ## Ce qui est cherché
 *
 * Un fichier qui **déclare** au moins trois identifiants de pages est une TABLE, pas
 * un usage. Deux choses sont donc nécessaires, et c'est la seconde qui fait le tri :
 *
 *   - au moins trois identifiants distincts ;
 *   - écrits sous une forme de DÉCLARATION — `id: 'x'`, `configId: 'x'`, `'x': {` —
 *     et non de simple mention.
 *
 * Sans cette seconde condition, le premier essai accusait `admin/+page.svelte` sur
 * `prestataires`, `espace-cs` et `admin` : les deux premiers venaient de migrations
 * de données historiques (`defaults.id === 'prestataires'`), le troisième est un
 * homonyme — `'admin'` est aussi un RÔLE. Un contrôle qui crie sur du légitime finit
 * désarmé, et l'exception qu'on lui aurait ajoutée aurait rendu aveugle précisément
 * le fichier qui portait la table.
 *
 * Les ROUTES (`/tickets`, `/annuaire`…) ne sont volontairement pas cherchées : elles
 * apparaissent légitimement dans chaque lien et chaque `goto()`. Même raison.
 *
 * Le contrôle s'auto-contrôle : si la source disparaît ou change de forme, il ÉCHOUE
 * au lieu de conclure au vert (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const SOURCE = join(RACINE, 'lib', 'pages.ts');

/** Un fichier qui cite au moins ce nombre d'identifiants distincts est un inventaire. */
const SEUIL = 3;

/**
 * Fichiers qui citent plusieurs identifiants pour une AUTRE notion, avec la raison.
 * Une tolérance sans raison se transforme en dépotoir : chacune est nommée, et le
 * contrôle échoue si l'une devient inutile.
 */
const EXCEPTIONS = {
	'lib/raccourcis.ts':
		'autre axe — les tuiles du tableau de bord, qui portent des compteurs et des ' +
		"règles de visibilité que le menu n'a pas. ⚠️ Ses libellés et ses icônes ne " +
		'suivent PAS la configuration des pages (« Sondages » quand le menu dit ' +
		'« Communauté ») : divergence connue et assumée, pas un oubli.',
};

/**
 * L'identifiant est-il DÉCLARÉ (inventaire) plutôt que simplement mentionné (usage) ?
 *
 *   déclaration : `id: 'faq'`, `configId: 'mes-demandes'`, `'faq': { … }`
 *   mention     : `getPageConfig(raw, 'faq', …)`, `defaults.id === 'faq'`, `'admin'` (rôle)
 */
function declare(texte, id) {
	return (
		new RegExp(`\\b(?:id|configId):\\s*['"\`]${id}['"\`]`).test(texte) ||
		new RegExp(`['"\`]${id}['"\`]\\s*:\\s*\\{`).test(texte)
	);
}

/** Retire commentaires et docstrings : expliquer la règle ne doit pas la violer. */
function sansCommentaires(texte) {
	return texte
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.replace(/(^|[^:'"`\\])\/\/[^\n]*/g, '$1');
}

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (/\.(svelte|ts)$/.test(nom)) sortie.push(chemin);
	}
	return sortie;
}

// ── Auto-contrôle (cas zéro) ──────────────────────────────────────────────────
if (!existsSync(SOURCE)) {
	console.error(`✗ Cas zéro : ${SOURCE} est introuvable — contrôle inopérant.`);
	process.exit(1);
}
const source = readFileSync(SOURCE, 'utf8');
for (const attendu of ['export const PAGES', 'export const HREFS_DEFAUT', 'export const ID_VERS_HREF']) {
	if (!source.includes(attendu)) {
		console.error(
			`✗ Cas zéro : lib/pages.ts n'expose plus \`${attendu}\`. La source a changé de ` +
				'forme — mettre ce contrôle à jour, sinon il laisse repasser toutes les recopies.'
		);
		process.exit(1);
	}
}
const IDS = [...source.matchAll(/^\t\{ id: '([a-z0-9-]+)', href:/gm)].map((m) => m[1]);
if (IDS.length < 10) {
	console.error(
		`✗ Cas zéro : ${IDS.length} identifiant(s) extrait(s) de lib/pages.ts, au moins 10 attendus. ` +
			'Le motif de lecture ne correspond plus à la table — le contrôle ne mesure plus rien.'
	);
	process.exit(1);
}

const tous = fichiers(RACINE);
if (tous.length === 0) {
	console.error("✗ Cas zéro : aucun fichier analysé — l'arborescence a changé.");
	process.exit(1);
}

// ── Recherche ─────────────────────────────────────────────────────────────────
const violations = [];
const exceptionsUtiles = new Set();

for (const chemin of tous) {
	if (chemin === SOURCE) continue;
	const rel = relative(RACINE, chemin).split(sep).join('/');
	const texte = sansCommentaires(readFileSync(chemin, 'utf8'));
	const cites = IDS.filter((id) => declare(texte, id));
	if (cites.length < SEUIL) continue;
	if (rel in EXCEPTIONS) {
		exceptionsUtiles.add(rel);
		continue;
	}
	violations.push({ rel, cites });
}

// Une exception qui ne sert plus est une tolérance qui dort : elle laisserait
// repasser une vraie recopie dans ce fichier sans que personne ne l'ait décidé.
const inutiles = Object.keys(EXCEPTIONS).filter((rel) => !exceptionsUtiles.has(rel));

if (violations.length || inutiles.length) {
	console.error('\n❌ Table des pages recopiée :\n');
	for (const { rel, cites } of violations) {
		console.error(`   ${rel} — ${cites.length} identifiants de pages : ${cites.join(', ')}`);
		console.error('      → importer PAGES / PAGES_MENU / ID_VERS_HREF depuis `$lib/pages`\n');
	}
	for (const rel of inutiles) {
		console.error(`   ${rel} : exception INUTILE — ce fichier ne cite plus ${SEUIL} identifiants`);
		console.error('      → la retirer de EXCEPTIONS dans ce script\n');
	}
	console.error(
		'Rappel : deux listes d\'accord entre elles ne prouvent rien. Les trois divergences\n' +
			"de #401 étaient chacune cohérente de son côté, et aucune n'était juste.\n"
	);
	process.exit(1);
}

console.log(
	`✓ ${tous.length} fichiers analysés — ${IDS.length} pages définies une seule fois ` +
		`(${Object.keys(EXCEPTIONS).length} exceptions nommées).`
);
