/*
 *  **Se déconnecter ne montre jamais un écran à moitié vidé** (29/09/2026).
 *
 *  Le geste vidait l'utilisateur, PUIS naviguait vers la mire : le temps que
 *  celle-ci se charge, le tableau de bord se re-rendait sans utilisateur —
 *  « Bonsoir » sans prénom, menu vide, kanban et fil toujours là. Signalé par
 *  l'utilisateur avec une capture ; reproduit ici en ralentissant la mire.
 *
 *  Ce qu'on vérifie : pendant la déconnexion, l'écran reste celui de
 *  l'utilisateur ; la session est révoquée AVANT de quitter la page ; on arrive
 *  sur la mire.
 */
import { expect, test } from '@playwright/test';
import { MEMBRE_CS, attendreHydratation, simulerApi } from './aides';

test('la déconnexion révoque, puis quitte sans passer par un écran vidé', async ({ page }) => {
	const ordre: string[] = [];
	await simulerApi(page);
	//  Une révocation lente : c'est pendant cette attente que l'écran se vidait.
	await page.route(
		(url) => url.pathname === '/api/auth/logout',
		async (route) => {
			ordre.push('revocation');
			await new Promise((fin) => setTimeout(fin, 1500));
			await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
		},
	);
	page.on('request', (r) => {
		if (r.isNavigationRequest() && new URL(r.url()).pathname === '/auth/connexion')
			ordre.push('mire');
	});

	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
	const salutation = page.locator('h1').first();
	//  Cas zéro : l'écran de départ nomme bien l'utilisateur.
	await expect(salutation).toContainText(MEMBRE_CS.prenom);

	//  Sur téléphone, « Déconnexion » est dans le menu : on l'ouvre d'abord.
	const menu = page.locator('button.hamburger');
	if (await menu.isVisible()) await menu.click();
	await page.locator('.nav-logout:visible').click();
	await page.waitForTimeout(500);
	await expect(page).toHaveURL(/\/tableau-de-bord/);
	await expect(salutation, 'l’écran s’est vidé avant de quitter la page').toContainText(
		MEMBRE_CS.prenom,
	);

	await expect(page).toHaveURL(/\/auth\/connexion$/);
	expect(ordre).toEqual(['revocation', 'mire']);
});
