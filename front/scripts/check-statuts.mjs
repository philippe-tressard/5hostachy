/**
 * Garde-fou : un écran ne réécrit pas « quel statut a cette personne ».
 *
 * ## Ce qui l'a rendu nécessaire (15/09/2026)
 *
 * Le même test était recomposé d'un écran à l'autre :
 *
 * | Notion | Écrite dans |
 * |---|---|
 * | « est locataire » | `OngletAcces`, `AccesConnexes`, `calendrier`, `mon-lot`, `residence`, `tableau-de-bord` — **six** fichiers |
 * | « est bailleur » | `OngletAcces`, `mon-lot` |
 * | « est syndic **ou** mandataire » | `PageCommunaute`, `sondages/[id]` |
 * | « est bailleur **ou** résident » | `mon-lot`, deux fois dans le même fichier |
 *
 * 🔴 `mon-lot` définissait `isLocataire` en ligne 92 **et** recomposait
 * `$currentUser?.statut === 'locataire'` aux lignes 172 et 449 : la dérivée
 * existait, dans le fichier même, et n'était pas employée. Une duplication n'a
 * pas besoin de traverser le dépôt pour diverger.
 *
 * 🔴 Pire : le commentaire de `sondages/[id]` affirmait *« cet écran ne réécrit
 * pas la règle d'accès à la Communauté »* juste au-dessus de la ligne qui la
 * réécrivait. Le seul endroit qui parlait du sujet disait que le problème
 * n'existait pas — le motif déjà rencontré sur les destinataires CS
 * (`CLAUDE.md`).
 *
 * ## Ce qui est cherché
 *
 * Une comparaison de `.statut` à un littéral, dans `src/` hors de `$lib/roles`.
 * Les prédicats (`estLocataire`, `estBailleur`, `estResident`,
 * `estCoproprietaire`, `estGestionnaire`) sont là pour ça.
 *
 * ⚠️ **Seul le statut d'une PERSONNE est visé.** `bail.statut === 'actif'`,
 * `imp.statut === 'resolu'`, `acces.statut === 'perdu'` sont d'autres axes, sur
 * d'autres objets : les viser ferait crier le contrôle sur du légitime, et un
 * contrôle qui crie sur du légitime finit désarmé — la leçon de C16 et de
 * `check-stack`. La cible est donc reconnue à son PORTEUR (`currentUser`,
 * `user`, `utilisateur`, `membre`, `porteur`, `personne`), pas au mot `statut`.
 *
 * ## Cas zéro
 *
 * Si `$lib/roles` cessait d'exporter ces prédicats, ce contrôle n'aurait plus de
 * quoi renvoyer les fautifs : il ÉCHOUE alors, au lieu de passer au vert en ne
 * mesurant rien (`standards/04` §2).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const SOURCE = join(RACINE, 'lib', 'roles.ts');

/** Les prédicats que la source DOIT exposer — sinon il n'y a rien à conseiller. */
const PREDICATS = [
	'estLocataire',
	'estBailleur',
	'estResident',
	'estCoproprietaire',
	'estGestionnaire',
	//  Trouvée par ce contrôle lui-même, dans `espace-cs` : « aidant ou
	//  mandataire », que le relevé à la main avait manquée.
	'agitPourAutrui',
];

/**
 * Le porteur d'un statut de PERSONNE. Un `bail.statut` ou un `imp.statut`
 * décrivent tout autre chose et ne sont pas concernés.
 */
const PORTEURS = '(?:\\$?currentUser|user|utilisateur|membre|porteur|personne|profil)';
const COMPARAISON = new RegExp(`${PORTEURS}\\s*\\??\\.\\s*statut\\s*[=!]==\\s*['"\`]`, 'g');

function fichiers(dossier) {
	const out = [];
	for (const entree of readdirSync(dossier)) {
		const chemin = join(dossier, entree);
		if (statSync(chemin).isDirectory()) out.push(...fichiers(chemin));
		else if (/\.(svelte|ts)$/.test(entree)) out.push(chemin);
	}
	return out;
}

//  ── Cas zéro : la source existe et porte bien ce qu'on va conseiller ────────
if (!existsSync(SOURCE)) {
	console.error(`✗ ${relative(RACINE, SOURCE)} est introuvable — contrôle INCONNU, pas OK.`);
	process.exit(1);
}
const source = readFileSync(SOURCE, 'utf8');
const absents = PREDICATS.filter((p) => !new RegExp(`export const ${p}\\b`).test(source));
if (absents.length) {
	console.error(
		`✗ $lib/roles n'exporte plus : ${absents.join(', ')}.\n` +
			"  Ce contrôle n'a plus de quoi renvoyer les écrans fautifs : il échoue " +
			'plutôt que de passer au vert sans rien mesurer.',
	);
	process.exit(1);
}

//  ── Le relevé ───────────────────────────────────────────────────────────────
const fautifs = [];
for (const chemin of fichiers(RACINE)) {
	const rel = relative(RACINE, chemin).split(sep).join('/');
	if (rel === 'lib/roles.ts') continue; // la source a le droit, c'est elle la règle
	const code = sansCommentaires(readFileSync(chemin, 'utf8'));
	for (const ligne of code.split('\n')) {
		COMPARAISON.lastIndex = 0;
		if (COMPARAISON.test(ligne)) fautifs.push(`${rel} : ${ligne.trim().slice(0, 110)}`);
	}
}

if (fautifs.length) {
	console.error(
		`✗ ${fautifs.length} écran(s) recomposent un statut de personne :\n  ` +
			fautifs.join('\n  ') +
			`\n\n  Emploie un prédicat de $lib/roles — ${PREDICATS.join(', ')} —\n` +
			'  ou ajoutes-y la notion si elle manque. Une notion écrite deux fois\n' +
			"  diverge : « bailleur ou résident » l'était déjà deux fois dans le\n" +
			'  même fichier (#959).',
	);
	process.exit(1);
}

console.log('✓ Statuts de personne : aucun écran ne recompose la règle de $lib/roles');
