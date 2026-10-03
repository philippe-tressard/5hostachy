/*
 *  **Une affaire neuve est adressée au conseil par défaut** (03/10/2026, signalé à
 *  l'écran sur TK-264069).
 *
 *  Le courriel « Nouvelle affaire » partait au conseil quelle que soit sa Diffusion ;
 *  il ne part plus de lui-même quand le conseil diffuse : la case « Envoyer au
 *  Conseil Syndical » décide. Pour que créer une affaire continue de prévenir le
 *  conseil, elle est COCHÉE par défaut (*« envoyé au CS doit être coché par défaut,
 *  y a un truc pas cohérent »*) ; une actualité, publiée par le conseil, reste
 *  décochée.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

async function nouvelleAffaire(page: Page) {
	await simulerApi(page);
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: /Nouvelle affaire/ }).click();
	await page
		.getByText(/Ascenseur, chauffage, éclairage/)
		.first()
		.click();
}

const caseCs = (page: Page) => page.getByLabel(/Envoyer au Conseil Syndical/);

test('Nouvelle affaire : « Envoyer au Conseil Syndical » est cochée par défaut', async ({
	page,
}) => {
	await nouvelleAffaire(page);
	await expect(caseCs(page)).toBeChecked();
});

test('Nouvelle affaire : la case se décoche, c’est elle qui décide', async ({ page }) => {
	await nouvelleAffaire(page);
	await caseCs(page).uncheck();
	await expect(caseCs(page)).not.toBeChecked();
});
