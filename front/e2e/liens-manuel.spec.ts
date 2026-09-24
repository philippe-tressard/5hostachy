/**
 *  Aucune adresse interne du manuel, ni des textes légaux livrés, ne mène à une
 *  page 404 (#1070).
 *
 *  ## 🔴 Pourquoi ce test existe (24/09/2026)
 *
 *  Le manuel a proposé pendant des mois un lien vers `/politique-confidentialite`
 *  quand la route est `/politique-de-confidentialite`, et le même lien mort vivait
 *  dans les mentions légales servies en base (0170, corrigé par la 0218). Aucun
 *  contrôle ne regardait les `href` : `check-manuel-menus` lit les cartes
 *  d'écran, pas les liens.
 *
 *  ⚠️ C'est un test de NAVIGATEUR et non un linter : résoudre une adresse
 *  demande de connaître les groupes de routes, les paramètres et `reroute` (les
 *  onglets servis sans dossier propre). Réécrire ce routage dans un script, c'est
 *  écrire un second routeur qui divergera du premier. On demande donc l'adresse
 *  au serveur, et on lit sa réponse (`standards/04` §14).
 *
 *  Hors périmètre : les liens `http(s)`, les ancres `#…`, `mailto:` — et
 *  `/api/…`, que `api/tests/test_liens_api_du_manuel.py` confronte aux routes
 *  réellement montées de l'API.
 */
import { readFileSync } from 'node:fs';

import { expect, test } from '@playwright/test';

const SOURCES = ['../docs/manuel-utilisateur.html', '../api/app/seed/contenus_legaux.py'];

function adressesInternes(): Map<string, string> {
	const vues = new Map<string, string>();
	for (const source of SOURCES) {
		const texte = readFileSync(new URL(source, `file://${process.cwd()}/`), 'utf8');
		for (const [, adresse] of texte.matchAll(/href=\\?["'](\/[^"'#?\\]*)/g)) {
			if (!adresse.startsWith('/api/') && !vues.has(adresse)) vues.set(adresse, source);
		}
	}
	return vues;
}

test('chaque adresse interne du manuel et des textes légaux existe', async ({ request }) => {
	const adresses = adressesInternes();
	//  Cas zéro : un motif qui ne lit plus rien rendrait ce test vert à vide.
	expect(
		adresses.size,
		'aucune adresse lue — le motif ne lit plus les sources',
	).toBeGreaterThanOrEqual(3);
	const mortes: string[] = [];
	for (const [adresse, source] of adresses) {
		const reponse = await request.get(adresse, { maxRedirects: 0 });
		if (reponse.status() === 404) mortes.push(`${adresse}  (${source})`);
	}
	expect(mortes, `adresse(s) en 404 :\n${mortes.join('\n')}`).toEqual([]);
});
