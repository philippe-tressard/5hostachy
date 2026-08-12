/**
 * Garde-fou : la table des périmètres ne s'écrit qu'à un seul endroit.
 *
 * POURQUOI. `PERIMETRE_LABELS` et `perimetreLabel()` vivent dans `lib/utils.ts`
 * depuis toujours — et trois copies s'étaient installées autour, sans que rien ne
 * les voie (#316) :
 *
 *   - `actualites/+page.svelte` réimplémentait la fonction, table identique au
 *     caractère près (corrigé le 12/08/2026 en livrant #300) ;
 *   - `calendrier/+page.svelte` faisait de même, avec une signature différente —
 *     une chaîne au lieu d'un tableau — ce qui est précisément ce qui l'avait fait
 *     diverger et ce qui a retardé sa correction ;
 *   - `prestataires/+page.svelte` et `PerimetrePicker.svelte` recopiaient la table
 *     sous forme de listes d'options.
 *
 * Aucune n'était fausse. C'est le danger : une correction faite dans `utils.ts`
 * — ajouter un bâtiment, renommer « AFUL » — n'aurait atteint aucune des quatre,
 * et l'écart ne se serait vu qu'à l'écran, longtemps après.
 *
 * LA RÈGLE : une clé de périmètre associée au libellé EXACT de `PERIMETRE_LABELS`
 * n'apparaît que dans `lib/utils.ts`. Ailleurs, dériver (`Object.entries`) ou
 * appeler `perimetreLabel()`.
 *
 * Ce que le contrôle NE signale pas, et c'est délibéré :
 *   - une occurrence isolée de « Copropriété entière » dans une phrase ;
 *   - une table qui associe ces clés à AUTRE CHOSE qu'un libellé — les couleurs
 *     de `PERIMETRE_COLORS` sont une notion propre, pas une copie ;
 *   - une variante d'affichage assumée, aux libellés délibérément différents
 *     (`PERIMETRE_SHORT` écrit « bât. 1 » et « privatif ») — déclarée dans
 *     TOLEREES avec sa raison.
 *
 * La première version de ce contrôle signalait ces trois cas. Un contrôle qui
 * crie sur du légitime finit désarmé — c'est ce qui avait été corrigé sur C16 le
 * 06/08. On compare donc aux libellés RÉELS, lus dans la source.
 *
 * Le contrôle s'auto-contrôle : s'il n'analyse aucun fichier, ou si la source
 * elle-même ne contient plus la table, il ÉCHOUE au lieu de conclure au vert
 * (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const SOURCE = join(RACINE, 'lib', 'utils.ts');

/** Clés de périmètre attendues dans la source. */
const CLES = ['bat:1', 'bat:2', 'bat:3', 'bat:4', 'parking', 'cave', 'aful'];

/** Au-delà de ce nombre de couples clé→libellé EXACT, ce n'est plus une coïncidence. */
const SEUIL = 3;

/** Fichiers dont la table est une notion distincte, avec la raison. */
const TOLEREES = {
	'routes/(app)/calendrier/+page.svelte':
		'PERIMETRE_SHORT — libellés volontairement courts et en minuscules pour les ' +
		'pastilles du calendrier (« bât. 1 », « privatif »), et deux clés qui ' +
		"n'existent pas dans PERIMETRE_LABELS (partie commune, partie privative). " +
		'Les trois libellés identiques (Parking, Cave, AFUL) le sont par coïncidence, ' +
		'pas par recopie.',
};

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (/\.(svelte|ts)$/.test(nom)) sortie.push(chemin);
	}
	return sortie;
}

if (!existsSync(SOURCE)) {
	console.error(`✗ Source unique introuvable (${SOURCE}) — contrôle inopérant.`);
	process.exit(1);
}

//  Auto-contrôle : la source doit elle-même porter la table. Sans cela, le
//  motif a changé et ce contrôle ne mesure plus rien — il passerait au vert
//  pour la pire des raisons.
const source = readFileSync(SOURCE, 'utf8');
const clesSource = CLES.filter((c) => source.includes(`'${c}'`) || source.includes(`${c}:`));
if (!source.includes('PERIMETRE_LABELS') || clesSource.length < CLES.length) {
	console.error(
		`✗ Cas zéro : ${clesSource.length}/${CLES.length} clé(s) trouvée(s) dans ` +
			`lib/utils.ts. La table a changé de forme — mettre CLES à jour, sinon ce ` +
			`contrôle laisse passer toutes les copies.`,
	);
	process.exit(1);
}

const tous = fichiers(RACINE).filter((f) => f !== SOURCE);
if (tous.length === 0) {
	console.error("✗ Cas zéro : aucun fichier analysé — l'arborescence a changé.");
	process.exit(1);
}

//  Libellés RÉELS, lus dans la source : c'est la comparaison à ces valeurs qui
//  distingue une copie d'une table qui partage seulement les clés.
const libelles = {};
for (const cle of CLES) {
	//  La clé s'écrit `'bat:1':` (quotée, car elle contient un `:`) ou `parking:`
	//  (nue). On accepte les deux, et on capture le libellé qui suit.
	const cleEchappee = cle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
	const m = source.match(new RegExp(`['"]?${cleEchappee}['"]?\\s*:\\s*['"]([^'"]+)['"]`));
	if (m) libelles[cle] = m[1];
}

/**
 * Espaces normalisées avant comparaison.
 *
 * Sans cela, ce contrôle rate exactement la copie qu'il doit trouver. Le tableau
 * de bord écrivait `'Bât. 1'` — espace INSÉCABLE — quand `utils.ts` écrit une
 * espace normale : indiscernable à l'œil, deux chaînes différentes pour du code.
 * Sa table était bien une copie, divergente de surcroît (`aful` y manquait, donc
 * un événement AFUL affichait la clé brute), et la première version de ce
 * contrôle l'a laissée passer.
 *
 * Une copie « presque identique » est le cas le PLUS fréquent, pas un cas limite :
 * c'est ainsi qu'une table recopiée dérive.
 */
const normaliser = (t) => t.replace(/[\s ]+/g, ' ');

const copies = [];
const tolereesPropres = [];
for (const f of tous) {
	const contenu = normaliser(readFileSync(f, 'utf8'));
	//  Un couple compte quand la clé ET son libellé figurent dans le fichier.
	const trouvees = CLES.filter(
		//  Les deux écritures d'une clé d'objet JS : quotée (obligatoire pour
		//  `'bat:1'`, qui contient un `:`) et nue (`parking:`). Ne chercher que la
		//  première rendait le contrôle aveugle à la moitié d'une table — celle du
		//  calendrier mélange justement les deux.
		(c) =>
			(contenu.includes(`'${c}'`) ||
				contenu.includes(`"${c}"`) ||
				new RegExp(`(^|[\\s,{])${c}\\s*:`).test(contenu)) &&
			libelles[c] &&
			contenu.includes(normaliser(libelles[c])),
	);
	//  Séparateurs normalisés : les clés de TOLEREES s'écrivent en `/`, y compris
	//  sur ce poste Windows où `relative()` rend des `\`.
	const rel = relative(RACINE, f).split(sep).join('/');
	if (trouvees.length >= SEUIL) {
		if (rel in TOLEREES) continue;
		copies.push({ fichier: rel, cles: trouvees });
	} else if (rel in TOLEREES) {
		tolereesPropres.push(rel);
	}
}

if (copies.length > 0) {
	console.error('✗ Table des périmètres recopiée hors de lib/utils.ts :');
	for (const c of copies) {
		console.error(`    ${c.fichier} — ${c.cles.length} clés : ${c.cles.join(', ')}`);
	}
	console.error(
		'\n  Dériver de `PERIMETRE_LABELS` (Object.entries) ou appeler `perimetreLabel()`.\n' +
			"  Une table correcte mais recopiée reste un manquement : c'est la correction\n" +
			'  suivante qui ne l\'atteindra pas.',
	);
	process.exit(1);
}

//  Une tolérance qui n'a plus lieu d'être fait échouer, comme pour les routes
//  admin : sinon la liste se remplit et ne protège plus rien.
if (tolereesPropres.length > 0) {
	console.error('✗ Tolérance(s) devenue(s) inutile(s) — plus aucune table recopiée :');
	for (const f of tolereesPropres) console.error(`    ${f} — retirer l'entrée de TOLEREES`);
	process.exit(1);
}

console.log(
	`✓ Périmètres : table unique dans lib/utils.ts, ${tous.length} fichier(s) vérifié(s), ` +
		`${Object.keys(TOLEREES).length} tolérée(s) et justifiée(s).`,
);
