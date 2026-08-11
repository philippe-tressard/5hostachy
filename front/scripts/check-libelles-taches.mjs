/**
 * Garde-fou : le nom d'une tâche planifiée ne s'écrit qu'à un seul endroit.
 *
 * POURQUOI. Le nom d'une tâche apparaissait à trois endroits qui ne se voyaient
 * pas les uns les autres : la synthèse « Santé des tâches planifiées », la
 * colonne Tâche du journal des exécutions, et le titre de la carte qui détaillait
 * cette tâche — ces deux derniers dans des FICHIERS DIFFÉRENTS. Ils avaient
 * divergé : la synthèse annonçait « Sauvegarde quotidienne » quand la carte
 * s'appelait « Système — Sauvegardes ». On ne pouvait donc pas relier une ligne
 * de la synthèse au tableau censé la détailler — signalé par l'utilisateur le
 * 11/08/2026.
 *
 * Les cartes de détail ont disparu avec #299, et `titreDetail()` avec elles. Ce
 * contrôle reste utile : il reste deux emplacements dans deux fichiers, et rien
 * n'empêcherait le prochain écran de retaper un nom à la main.
 *
 * Regrouper les libellés dans `$lib/taches.ts` ne suffit pas : rien n'empêche
 * le prochain écran de retaper « Sauvegarde quotidienne » dans un titre. Ce
 * contrôle échoue en CI si c'est le cas.
 *
 * LA RÈGLE : un libellé de tâche en toutes lettres n'est permis que dans
 * `lib/taches.ts`. Ailleurs, passer par `LIBELLE_TACHE[...]`.
 *
 * Le contrôle s'auto-contrôle : s'il n'analyse aucun fichier, s'il ne trouve
 * plus la source unique, ou s'il n'en extrait aucun libellé, il ÉCHOUE au lieu
 * de conclure au vert (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const SOURCE = join('lib', 'taches.ts');

/** Fichiers à analyser : tout le front sauf la source unique elle-même. */
function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (/\.(svelte|ts)$/.test(nom)) sortie.push(chemin);
	}
	return sortie;
}

const tous = fichiers(RACINE);
if (tous.length === 0) {
	console.error('✗ check-libelles-taches : aucun fichier analysé — contrôle inopérant.');
	process.exit(1);
}

const cheminSource = join(RACINE, SOURCE);
let source;
try {
	source = readFileSync(cheminSource, 'utf8');
} catch {
	console.error(`✗ check-libelles-taches : ${SOURCE} introuvable — la source unique a disparu.`);
	process.exit(1);
}

//  Les libellés sont extraits de la source, jamais recopiés ici : une seconde
//  liste serait exactement la duplication que ce contrôle interdit.
const LIBELLES = [...source.matchAll(/^\t[a-z_]+: '([^']+)'/gm)].map((m) => m[1]);
if (LIBELLES.length < 5) {
	console.error(
		`✗ check-libelles-taches : ${LIBELLES.length} libellé(s) extrait(s) de ${SOURCE} — ` +
			'le format a changé et le contrôle ne mesure plus rien.'
	);
	process.exit(1);
}

const fautes = [];
for (const chemin of tous) {
	const rel = relative(RACINE, chemin);
	if (rel === SOURCE) continue;
	const lignes = readFileSync(chemin, 'utf8').split('\n');
	lignes.forEach((ligne, i) => {
		//  Un commentaire qui CITE un libellé pour expliquer l'historique n'est pas
		//  un affichage : c'est même ce qui rend la règle compréhensible.
		const nue = ligne.trim();
		if (nue.startsWith('//') || nue.startsWith('*') || nue.startsWith('<!--')) return;
		for (const libelle of LIBELLES) {
			if (ligne.includes(libelle)) {
				fautes.push(`${rel.split(sep).join('/')}:${i + 1}  « ${libelle} »`);
			}
		}
	});
}

if (fautes.length) {
	console.error('✗ Libellé de tâche écrit en dur hors de lib/taches.ts :\n');
	for (const f of fautes) console.error(`   ${f}`);
	console.error(
		`\n  ${fautes.length} occurrence(s). Utiliser LIBELLE_TACHE[...] :` +
			'\n  un nom recopié diverge, et la synthèse cesse de renvoyer à son détail.'
	);
	process.exit(1);
}

console.log(
	`✓ Libellés de tâches : ${LIBELLES.length} noms, source unique respectée ` +
		`(${tous.length} fichiers analysés).`
);
