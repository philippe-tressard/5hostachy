/*
 *  **Une erreur vue à l'écran laisse une trace côté serveur** (#1631, 02/10/2026).
 *
 *  Le 16/09/2026, une clé `{#each}` répétée a figé un écran pendant que le
 *  serveur était vert : la cause ne se lisait que dans la console du résident.
 *  Ces tests tiennent les trois bouts — le signalement part dans le lot de la
 *  mesure d'audience, il ne porte jamais le message brut, et l'administrateur
 *  le lit dans l'onglet Télémétrie, téléphone compris.
 */
import {
	attendreHydratation,
	type Evenement,
	expect,
	lotsEnvoyes,
	MEMBRE_CS,
	simulerApi,
	TABLEAU_TELEMETRIE_VIDE,
	test,
	viderLaFile,
} from './aides';

const erreurs = (recus: Evenement[]) => recus.filter((e) => e.action === 'erreur');

test('une réponse 5xx se signale par son statut et son chemin, identifiants masqués', async ({
	page,
}) => {
	await simulerApi(page);
	const recus = await lotsEnvoyes(page);
	await page.route(
		(url) => url.pathname === '/api/signalements',
		(route) =>
			route.fulfill({ status: 502, contentType: 'application/json', body: '{"detail":"x"}' }),
	);
	await page.goto('/sondages');
	await attendreHydratation(page);
	await expect(page.locator('.etat-erreur').first()).toBeVisible();

	await viderLaFile(page);
	await expect.poll(() => erreurs(recus).map((e) => e.detail)).toContain('HTTP 502 /signalements');
	expect(erreurs(recus).every((e) => e.page === '/sondages')).toBe(true);
});

test('une exception se signale par son nom, sans ce qui est entre guillemets ni les nombres', async ({
	page,
}) => {
	await simulerApi(page);
	const recus = await lotsEnvoyes(page);
	await page.goto('/sondages');
	await attendreHydratation(page);

	//  Un `ErrorEvent` posté à la main : ce que le navigateur fait d'une exception
	//  non rattrapée, sans en lever une — le `test` des specs en ferait un échec.
	await page.evaluate(() => {
		const erreur = new TypeError('Lecture de « saisie privée » impossible au rang 42');
		for (let i = 0; i < 3; i++) {
			window.dispatchEvent(new ErrorEvent('error', { error: erreur, message: erreur.message }));
		}
	});
	await viderLaFile(page);

	await expect.poll(() => erreurs(recus).length).toBe(1);
	expect(erreurs(recus)[0].detail).toBe('TypeError: Lecture de … impossible au rang #');
});

test('l’administrateur lit les erreurs dans l’onglet Télémétrie, sans défilement horizontal', async ({
	page,
}) => {
	const codeLong = 'svelte:each_key_duplicate_avec_un_nom_tres_long_qui_ne_se_coupe_nulle_part';
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
		if (chemin === '/api/telemetry/dashboard')
			return {
				...TABLEAU_TELEMETRIE_VIDE,
				erreurs: [
					{
						page: '/tickets/12',
						code: codeLong,
						total: 3,
						premiere_le: '2026-10-02T08:00:00',
						derniere_le: '2026-10-02T09:30:00',
					},
				],
			};
	});
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);

	const ligne = page.getByRole('row', { name: new RegExp(codeLong) });
	await expect(ligne).toBeVisible();
	await expect(ligne.getByRole('cell').nth(1)).toHaveText('3');
	//  Au téléphone, un code long fait défiler la CARTE et jamais la page : les
	//  cellules ne vont pas à la ligne et la carte défile (`normes.css`, la règle
	//  de tous les tableaux). ⚠️ Mesuré sur la page : le tableau, lui, SORT de sa
	//  carte par construction — c'est la carte qui défile.
	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde, 'le panneau des erreurs fait défiler la page horizontalement').toBe(false);
});
