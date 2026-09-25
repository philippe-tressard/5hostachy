#!/usr/bin/env node
/**
 *  Les tests de navigateur lancent LEUR serveur, et ne l'empruntent jamais (#1150).
 *
 *  ## Pourquoi ce contrôle
 *
 *  `playwright.config.ts` portait le port de `npm run dev` (5173) et
 *  `reuseExistingServer: true`. Un rejeu qui trouvait un serveur sur ce port
 *  s'y branchait sans un mot — celui du poste, ou celui d'une autre session,
 *  dans un autre worktree. Mesuré le 25/09/2026 :
 *
 *   - quand ce serveur s'arrêtait, les tests tombaient en
 *     `ERR_CONNECTION_REFUSED`, un différent à chaque fois — l'intermittence
 *     du ticket, prise pendant trois jours pour une affaire de charge ;
 *   - et tant qu'il tournait, les tests lisaient le code de QUI L'AVAIT LANCÉ :
 *     `rejouer-ci.sh` pouvait dire vert sur un autre arbre que le sien.
 *
 *  Remettre `true` accélère un lancement local de deux secondes. C'est
 *  précisément le geste qu'on fait sans y penser — d'où ce contrôle.
 *
 *  ## Ce qu'il refuse, dans la config (commentaires neutralisés)
 *
 *   1. `reuseExistingServer` autre que `false` ;
 *   2. une commande de serveur sans `--strictPort` — Vite se replierait en
 *      silence sur un port voisin, pendant que Playwright interroge le premier ;
 *   3. le port de développement écrit en dur.
 *
 *  Lancer : node scripts/check-e2e-serveur.mjs [--selftest]
 */
import { readFileSync } from 'node:fs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const CONFIG = 'playwright.config.ts';

/**  Les fautes d'une config, PURES. @returns {string[]} */
export function fautes(source) {
	const code = neutraliserCommentaires(source);
	const f = [];
	const reuse = code.match(/reuseExistingServer\s*:\s*([^,\n}]+)/);
	if (!reuse || reuse[1].trim() !== 'false')
		f.push('reuseExistingServer doit valoir `false` : un serveur emprunté sert le code d’un autre');
	if (!/--strictPort\b/.test(code))
		f.push(
			'la commande du serveur doit porter `--strictPort` : sinon Vite change de port en silence',
		);
	if (/\b5173\b/.test(code))
		f.push('le port 5173 est celui de `npm run dev` : un port partagé est un serveur partagé');
	return f;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const n = fautes(src).length;
		console.log(`${n === attendu ? 'PASS' : 'FAIL'}  ${libelle} → ${n} faute(s)`);
		if (n !== attendu) ko = 1;
	};
	const CONFORME =
		'const PORT = Number(process.env.E2E_PORT);\n' +
		'webServer: { command: `npm run dev -- --port ${PORT} --strictPort`, reuseExistingServer: false }';
	//  🔴 L'état exact d'avant le 25/09/2026 : les trois fautes à la fois.
	t(
		'la config d’avant #1150',
		3,
		"const PORT = 5173;\nwebServer: { command: 'npm run dev -- --port ' + PORT, reuseExistingServer: true }",
	);
	t('la config conforme', 0, CONFORME);
	t(
		'réutilisation remise',
		1,
		CONFORME.replace('reuseExistingServer: false', 'reuseExistingServer: true'),
	);
	t('réutilisation laissée au défaut', 1, CONFORME.replace(', reuseExistingServer: false', ''));
	t('réutilisation conditionnelle', 1, CONFORME.replace('false }', '!process.env.CI }'));
	t('port de développement cité en commentaire seulement', 0, CONFORME + '\n// jadis 5173');
	process.exit(ko);
}

const trouvees = fautes(readFileSync(CONFIG, 'utf8'));
if (trouvees.length) {
	console.error(`✗ ${CONFIG} :`);
	for (const f of trouvees) console.error(`  • ${f}`);
	console.error('\n  Voir le commentaire d’en-tête de la config, et #1150.');
	process.exit(1);
}
console.log('✓ Tests de navigateur : un serveur à eux, sur un port à eux, jamais emprunté.');
