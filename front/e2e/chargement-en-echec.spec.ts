/*
 *  **Un chargement en échec se DIT — et n'écrase rien** (#1459, 30/09/2026).
 *
 *  Quatorze écrans faisaient `try { x = await … } catch { }` : la variable
 *  restait à sa valeur initiale — `[]`, `''`, un formulaire vide — et l'écran
 *  la montrait comme une réponse du serveur. Trois étaient des formulaires
 *  d'administration : affichés vides, puis enregistrés, ils effaçaient ce
 *  qu'ils n'avaient pas pu lire (textes légaux, fiche de la copropriété).
 *
 *  `lint:catch-vide` refuse la forme dans le code ; ce test tient l'ÉCRAN, sur
 *  les cas où le silence coûtait une donnée.
 */
import { expect, test, type Page } from '@playwright/test';
import { attendreHydratation, MEMBRE_CS, simulerApi } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

/** Fait échouer un chemin d'API — enregistré APRÈS `simulerApi`, donc essayé d'abord. */
async function enEchec(page: Page, chemin: string, status = 500) {
	await page.route(
		(url) => url.pathname === chemin,
		(route) =>
			route.fulfill({
				status,
				contentType: 'application/json',
				body: JSON.stringify({ detail: status === 404 ? 'Introuvable' : 'Panne simulée' }),
			}),
	);
}

for (const [lecture, onglet] of [
	['/api/config/legal', 'legal'],
	['/api/config/admin', 'smtp'],
] as const) {
	test(`Admin : ${lecture} illisible — l’onglet ${onglet} le dit et n’offre rien à enregistrer`, async ({
		page,
	}) => {
		await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
		await enEchec(page, lecture);
		await page.goto(`/admin?onglet=${onglet}`);
		await attendreHydratation(page);

		await expect(page.getByText('Affichage incomplet.')).toBeVisible();
		await expect(page.getByText('Paramétrage illisible — rien n’a été modifié')).toBeVisible();
		await expect(page.getByRole('button', { name: /Enregistrer/ })).toHaveCount(0);
	});
}

test('Admin : la fiche de la copropriété illisible ne s’affiche pas en formulaire vide', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await enEchec(page, '/api/copropriete');
	await page.goto('/admin?onglet=copropriete');
	await attendreHydratation(page);

	await expect(page.getByText('Impossible d’afficher la fiche')).toBeVisible();
	await expect(page.getByLabel(/Nom de la résidence/)).toHaveCount(0);
});

test('Admin : une fiche pas encore créée (404) ouvre le formulaire vide, et c’est juste', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await enEchec(page, '/api/copropriete', 404);
	await page.goto('/admin?onglet=copropriete');
	await attendreHydratation(page);

	await expect(page.getByLabel(/Nom de la résidence/)).toBeVisible();
	await expect(page.getByText('Impossible d’afficher la fiche')).toHaveCount(0);
});

test('Communauté : la file de modération illisible le dit au conseil', async ({ page }) => {
	await simulerApi(page);
	await enEchec(page, '/api/signalements');
	await page.goto('/sondages');
	await attendreHydratation(page);

	await expect(page.locator('.etat-erreur').first()).toBeVisible();
});
