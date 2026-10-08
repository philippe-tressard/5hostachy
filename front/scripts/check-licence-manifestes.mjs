#!/usr/bin/env node
/**
 * Garde-fou : les manifestes `package.json` du dépôt DÉCLARENT la licence du
 * projet (#1583, 02/10/2026).
 *
 * ## Pourquoi
 *
 * `front/package.json` et `whatsapp-bridge/package.json` ne portaient aucun champ
 * `license` : tout outil qui lit les manifestes (`license-checker`, `npm view`,
 * un audit de conformité) rendait « UNLICENSED » pour un projet dont la licence
 * est, au contraire, très écrite. Le fichier public disait une chose, la
 * métadonnée une autre — et aucun contrôle ne confrontait les deux.
 *
 * ## Ce qui est vérifié (depuis #1726, 08/10/2026)
 *
 * Le projet est sous **AGPL-3.0-or-later**, une licence SPDX : le champ
 * `license` de chaque manifeste vaut donc l'identifiant que `REUSE.toml`
 * accorde (son premier `SPDX-License-Identifier`, celui du motif `**`), et le
 * texte `LICENSES/<identifiant>.txt` existe et porte le même texte que
 * `LICENSE`. Sous l'ancienne licence, hors SPDX, la forme était
 * `SEE LICENSE IN LICENSE-5Hostachy.md` : elle est désormais refusée, puisque
 * le fichier n'existe plus.
 *
 * ⚠️ L'identifiant n'est pas écrit ici : il est LU dans `REUSE.toml`. Un nom
 * recopié dans un contrôle diverge le jour où la licence change — ce contrôle
 * l'a appris à ce changement-là.
 *
 * ## Ce qui n'est pas vérifié
 *
 * `api/` n'a pas de manifeste (ni `pyproject.toml`) : il n'y a rien à déclarer.
 * Le `package-lock.json` reçoit `license` à la prochaine écriture de `npm` ;
 * `lint:lock` ne le compare pas, et ce contrôle non plus.
 *
 * ## Cas zéro
 *
 * Un manifeste illisible, un `LICENSE` absent ou un `REUSE.toml` sans
 * identifiant rend INCONNU (code 2), jamais ✓.
 *
 * Usage : node scripts/check-licence-manifestes.mjs [--selftest] [--racine <dépôt>]
 */
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/** L'identifiant SPDX accordé par `REUSE.toml` — le premier déclaré. PURE. */
export function identifiantAccorde(reuse) {
	const trouve = /SPDX-License-Identifier\s*=\s*"([^"]+)"/.exec(reuse ?? '');
	return trouve ? trouve[1] : null;
}

/**
 * Ce qui manque à un manifeste, ou `null`. PURE.
 *
 * @param {{license?: unknown}} manifeste
 * @param {string} spdx  l'identifiant accordé par REUSE.toml
 * @param {(nom: string) => (string | null)} texteRacine  le texte d'un fichier du dépôt, ou null
 */
export function licenceManquante(manifeste, spdx, texteRacine) {
	const licence = manifeste?.license;
	if (typeof licence !== 'string' || !licence)
		return 'aucun champ `license` (outils : « UNLICENSED »)';
	if (licence !== spdx) {
		return `\`license\` vaut « ${licence} » : le dépôt accorde « ${spdx} » (REUSE.toml)`;
	}
	const texte = texteRacine(`LICENSES/${spdx}.txt`);
	if (texte === null) return `LICENSES/${spdx}.txt est absent : REUSE l'exige`;
	if (texte !== texteRacine('LICENSE')) {
		return `LICENSES/${spdx}.txt n'est pas le même texte que LICENSE`;
	}
	return null;
}

function selftest() {
	let ko = 0;
	const SPDX = 'AGPL-3.0-or-later';
	const racine = { LICENSE: 'texte', [`LICENSES/${SPDX}.txt`]: 'texte' };
	const lire = (nom) => racine[nom] ?? null;
	const verifier = (nom, obtenu, attendu) => {
		if (obtenu !== attendu) ko++;
		console.log(`${obtenu === attendu ? 'PASS' : 'ÉCHEC'}  ${nom}`);
	};
	const accepte = (manifeste, l = lire) => licenceManquante(manifeste, SPDX, l) === null;
	//  🔴 LES CAS FAUTIFS : le manifeste d'avant #1583, puis celui d'avant #1726.
	verifier('aucun champ license : refusé', accepte({ name: 'x', private: true }), false);
	verifier(
		'ancienne forme hors SPDX : refusée',
		accepte({ license: 'SEE LICENSE IN LICENSE-5Hostachy.md' }),
		false,
	);
	verifier('licence SPDX non accordée : refusée', accepte({ license: 'MIT' }), false);
	verifier('champ vide : refusé', accepte({ license: '' }), false);
	verifier(
		'texte REUSE absent : refusé',
		accepte({ license: SPDX }, (n) => (n === 'LICENSE' ? 'texte' : null)),
		false,
	);
	verifier(
		'texte REUSE différent de LICENSE : refusé',
		accepte({ license: SPDX }, (n) => (n === 'LICENSE' ? 'texte' : 'autre')),
		false,
	);
	verifier('forme attendue : acceptée', accepte({ license: SPDX }), true);
	verifier('cas zéro : manifeste vide', accepte({}), false);
	verifier(
		'identifiant lu dans REUSE.toml',
		identifiantAccorde('path = "**"\nSPDX-License-Identifier = "AGPL-3.0-or-later"\n'),
		SPDX,
	);
	verifier('REUSE.toml sans identifiant : null', identifiantAccorde('version = 1'), null);
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
const SPDX = identifiantAccorde(texteRacine('REUSE.toml'));
if (!SPDX) {
	console.error('\n⚠️  INCONNU — REUSE.toml ne déclare aucun identifiant de licence.\n');
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
	const manque = licenceManquante(manifeste, SPDX, texteRacine);
	if (manque) fautes.push(`${m} — ${manque}`);
}

if (fautes.length) {
	console.error(
		`\n✗ ${fautes.length} manifeste(s) sans la licence du dépôt (#1583, #1726) :\n\n  ` +
			fautes.join('\n  ') +
			`\n\n  Écrire "license": "${SPDX}" — l'identifiant que REUSE.toml accorde.\n`,
	);
	process.exit(1);
}
console.log(
	`✓ Licence : ${MANIFESTES.length} manifeste(s) déclarent ${SPDX}, la licence du dépôt.`,
);
