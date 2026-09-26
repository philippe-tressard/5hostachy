/**
 * Garde-fou : la pastille de lecture dit ce que le serveur FAIT — exécutée,
 * pas relue.
 *
 * ## Pourquoi (lot 1 de la pastille de lecture, 25/09/2026)
 *
 * La carte d'une affaire dit qui la lit (« Copropriétaires », « CS »…).
 * Le résumé est calculé à l'écran (`src/lib/lecture.ts`) ; la règle vit au
 * serveur (`ticket_visible`). Un écart ne casse rien, il MENT : une pastille
 * « Tous » sur une affaire que les locataires ne lisent pas.
 *
 * Les deux sont tenus par une seule attente, `api/tests/donnees/lecture_pastille.json` :
 * `test_lecture_pastille.py` l'exécute contre la règle du serveur, ce contrôle
 * contre le résumé de l'écran. Même montage que `lint:libelle-perimetre`.
 *
 * Cas zéro : attente absente ou vide, module qui ne se charge pas ou ne rend
 * plus `lectureDe` → le contrôle ÉCHOUE, il ne conclut pas au vert.
 */
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chargerModule } from './lib/charger-module.mjs';

const ICI = dirname(fileURLToPath(import.meta.url));
const SOURCE = resolve(ICI, '..', 'src', 'lib', 'lecture.ts');
const ATTENTES = resolve(ICI, '..', '..', 'api', 'tests', 'donnees', 'lecture_pastille.json');

function echouer(message) {
	console.error(`✗ ${message}`);
	process.exit(1);
}

if (!existsSync(ATTENTES)) echouer(`Cas zéro : ${ATTENTES} est introuvable — contrôle inopérant.`);
const cas = JSON.parse(readFileSync(ATTENTES, 'utf8')).cas ?? [];
if (cas.length < 10) echouer(`Cas zéro : ${cas.length} cas seulement dans ${ATTENTES}.`);

const { lectureDe, PROFILS } = await chargerModule(SOURCE, echouer);
if (typeof lectureDe !== 'function' || !Array.isArray(PROFILS)) {
	echouer(
		"Cas zéro : lib/lecture.ts n'exporte plus lectureDe/PROFILS — mettre ce contrôle à jour.",
	);
}
const STATUT = Object.fromEntries(PROFILS.map((p) => [p.code, p.statut]));

const echecs = [];
for (const c of cas) {
	const restreint = c.perimetre !== 'global';
	const l = lectureDe({
		actualite: c.actualite,
		confidentiel: c.confidentiel,
		publicCible: c.public_cible,
		perimetreRestreint: restreint,
		reservePerimetre: c.reserve_perimetre,
		datee: c.datee === true,
		enAg: c.en_ag === true,
		categorie: c.categorie,
		dansBatiments: c.perimetre === 'batiment',
	});
	const lecteurs = l.profils.map((p) => STATUT[p]);
	if (JSON.stringify(lecteurs) !== JSON.stringify(c.lecteurs)) {
		echecs.push(
			`« ${c.nom} » : la pastille dit ${JSON.stringify(lecteurs)}, le serveur ${JSON.stringify(c.lecteurs)}`,
		);
	}
	//  Le cadenas : « hors du périmètre, personne ne lit ». Il n'a de sens que
	//  sur un périmètre restreint et quand quelqu'un lit.
	if (c.hors_perimetre !== null && c.lecteurs.length) {
		const cadenas = !c.hors_perimetre;
		if (l.perimetreReserve !== cadenas) {
			echecs.push(`« ${c.nom} » : cadenas ${l.perimetreReserve}, attendu ${cadenas}`);
		}
	} else if (l.perimetreReserve) {
		echecs.push(`« ${c.nom} » : cadenas affiché sans périmètre restreint ni lecteur`);
	}
}

if (echecs.length) {
	console.error('✗ La pastille de lecture ne dit pas ce que le serveur fait :');
	for (const e of echecs) console.error(`  • ${e}`);
	console.error(
		'\n  Corriger src/lib/lecture.ts — ou, si la RÈGLE a changé, le fichier d’attentes ET le test Python.',
	);
	process.exit(1);
}
console.log(`✓ Pastille de lecture : ${cas.length} cas conformes à la règle du serveur.`);
