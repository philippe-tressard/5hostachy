#!/usr/bin/env node
/**
 * Garde-fou : les manifestes `package.json` du dépôt DÉCLARENT la licence du
 * projet (#1583, 02/10/2026).
 *
 * ## Pourquoi
 *
 * Le dépôt est sous Licence 5Hostachy — source-available, hors SPDX — et la dit
 * dans `LICENSE`, `LICENSES/LicenseRef-5Hostachy.txt` et `REUSE.toml`. Mais
 * `front/package.json` et `whatsapp-bridge/package.json` ne portaient aucun champ
 * `license` : tout outil qui lit les manifestes (`license-checker`, `npm view`,
 * un audit de conformité) rendait « UNLICENSED » pour un projet dont la licence
 * est, au contraire, très écrite. Le fichier public disait une chose, la
 * métadonnée une autre — et aucun contrôle ne confrontait les deux.
 *
 * `npm` prévoit la forme pour une licence hors SPDX : `SEE LICENSE IN <fichier>`.
 *
 * ## Ce qui est vérifié
 *
 * Pour chaque manifeste : le champ `license` vaut `SEE LICENSE IN <fichier>`, et
 * `<fichier>` existe à la racine du dépôt et porte **le même texte** que
 * `LICENSE` — celui que GitHub lit. (L'égalité des trois exemplaires de la
 * licence entre eux est tenue par `api/tests/test_gouvernance_depot.py`.)
 *
 * ⚠️ Le nom du fichier n'est pas écrit ici : c'est le manifeste qui le désigne, et
 * le contrôle vérifie qu'il pointe un texte réel. Un nom recopié dans un contrôle
 * diverge le jour où la licence change de fichier.
 *
 * ## Ce qui n'est pas vérifié
 *
 * `api/` n'a pas de manifeste (ni `pyproject.toml`) : il n'y a rien à déclarer.
 * Le `package-lock.json` reçoit `license` à la prochaine écriture de `npm` ;
 * `lint:lock` ne le compare pas, et ce contrôle non plus — le lock n'est jamais
 * réécrit à la main.
 *
 * ## Cas zéro
 *
 * Un manifeste illisible ou un `LICENSE` absent rend INCONNU (code 2), jamais ✓.
 *
 * Usage : node scripts/check-licence-manifestes.mjs [--selftest] [--racine <dépôt>]
 */
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const PREFIXE = 'SEE LICENSE IN ';

/**
 * Ce qui manque à un manifeste, ou `null`. PURE.
 *
 * @param {{license?: unknown}} manifeste
 * @param {(nom: string) => (string | null)} texteRacine  le texte d'un fichier de la racine, ou null
 */
export function licenceManquante(manifeste, texteRacine) {
	const licence = manifeste?.license;
	if (typeof licence !== 'string' || !licence)
		return 'aucun champ `license` (outils : « UNLICENSED »)';
	if (!licence.startsWith(PREFIXE)) {
		return `\`license\` vaut « ${licence} » : la licence du dépôt est hors SPDX, la forme est « ${PREFIXE}<fichier> »`;
	}
	const nom = licence.slice(PREFIXE.length).trim();
	const texte = texteRacine(nom);
	if (texte === null) return `\`license\` désigne « ${nom} », absent de la racine du dépôt`;
	if (texte !== texteRacine('LICENSE')) {
		return `« ${nom} » n'est pas le même texte que LICENSE : le manifeste désigne une autre licence`;
	}
	return null;
}

function selftest() {
	let ko = 0;
	const racine = { LICENSE: 'texte', 'LICENSE-5Hostachy.md': 'texte', 'AUTRE.md': 'autre' };
	const lire = (nom) => racine[nom] ?? null;
	const verifier = (nom, manifeste, attendu) => {
		const obtenu = licenceManquante(manifeste, lire) === null;
		if (obtenu !== attendu) ko++;
		console.log(`${obtenu === attendu ? 'PASS' : 'ÉCHEC'}  ${nom}`);
	};
	//  🔴 LE CAS FAUTIF : le manifeste d'avant #1583.
	verifier('aucun champ license : refusé', { name: 'x', private: true }, false);
	verifier('licence SPDX affirmée à tort : refusée', { license: 'MIT' }, false);
	verifier('fichier désigné absent : refusé', { license: `${PREFIXE}ABSENT.md` }, false);
	verifier('fichier désigné d’un autre texte : refusé', { license: `${PREFIXE}AUTRE.md` }, false);
	verifier('champ vide : refusé', { license: '' }, false);
	verifier('forme attendue : accepté', { license: `${PREFIXE}LICENSE-5Hostachy.md` }, true);
	verifier('cas zéro : manifeste vide', {}, false);
	console.log(ko ? `== ${ko} ÉCHEC(S) ==` : '== TOUS OK ==');
	return ko ? 1 : 0;
}

if (process.argv.includes('--selftest')) process.exit(selftest());

const i = process.argv.indexOf('--racine');
const RACINE = resolve(
	i > 0 ? process.argv[i + 1] : fileURLToPath(new URL('../..', import.meta.url)),
);
const MANIFESTES = ['front/package.json', 'whatsapp-bridge/package.json'];

const texteRacine = (nom) => {
	const chemin = join(RACINE, nom);
	return existsSync(chemin) ? readFileSync(chemin, 'utf8').replace(/\r\n/g, '\n') : null;
};

if (texteRacine('LICENSE') === null) {
	console.error('\n⚠️  INCONNU — LICENSE est absent de la racine : rien à confronter.\n');
	process.exit(2);
}

const fautes = [];
for (const m of MANIFESTES) {
	let manifeste;
	try {
		manifeste = JSON.parse(readFileSync(join(RACINE, m), 'utf8'));
	} catch (e) {
		console.error(`\n⚠️  INCONNU — ${m} illisible (${e.message}).\n`);
		process.exit(2);
	}
	const manque = licenceManquante(manifeste, texteRacine);
	if (manque) fautes.push(`${m} — ${manque}`);
}

if (fautes.length) {
	console.error(
		`\n✗ ${fautes.length} manifeste(s) sans licence déclarée (#1583) :\n\n  ` +
			fautes.join('\n  ') +
			'\n\n  Écrire "license": "SEE LICENSE IN LICENSE-5Hostachy.md" — la forme npm pour une\n' +
			'  licence hors SPDX. Sans elle, les outils lisent « UNLICENSED ».\n',
	);
	process.exit(1);
}
console.log(`✓ Licence : ${MANIFESTES.length} manifeste(s) déclarent la licence du dépôt.`);
