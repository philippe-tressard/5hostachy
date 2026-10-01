/*
 *  **L'accueil : la frise du fil et le lien vers les consignes** (#779, 01/10/2026).
 *
 *  Deux factorisations, tenues ici par ce que l'utilisateur VOIT :
 *
 *  - `FriseDuFil` rend désormais les trois listes du fil — l'Épinglé, le fil
 *    récent et les Archives —, que la page et `ArchivesDuFil` écrivaient chacune
 *    de leur côté. Une carte se déplie au clic, une seule à la fois, dans
 *    chacune des trois.
 *  - `LienConsignes` rend le lien vers la fiche des consignes, écrit trois fois
 *    avec deux libellés : l'accueil et l'annuaire disent maintenant la même
 *    chose, vers la même adresse.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const ADRESSE = '/api/admin/fiche-arrivant';
const LIBELLE = 'Consignes de la copropriété';

const ilYA = (jours: number) => new Date(Date.now() - jours * 86400000).toISOString();

const ITEMS = [
	{
		id: 'pub-1',
		type: 'publication',
		date: ilYA(0),
		titre: 'Coupure d’eau jeudi',
		detail: 'De 9 h à 12 h',
		badges: [],
		icon: '📰',
		meta: {},
	},
	{
		id: 'pub-2',
		type: 'publication',
		date: ilYA(3),
		titre: 'Règles du local vélos',
		detail: 'À relire',
		badges: [],
		icon: '📰',
		meta: { epingle: true },
	},
	{
		id: 'pub-3',
		type: 'publication',
		date: ilYA(90),
		titre: 'Ravalement terminé',
		detail: 'Fin du chantier',
		badges: [],
		icon: '📰',
		meta: {},
	},
];

async function accueil(page: Page) {
	await simulerApi(page, (chemin) =>
		chemin === '/api/flux' ? { items: ITEMS, sante: {} } : undefined,
	);
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
}

test('le fil récent est groupé sous « Aujourd’hui »', async ({ page }) => {
	await accueil(page);
	await expect(page.locator('.flux-day-label', { hasText: "Aujourd'hui" })).toBeVisible();
	await expect(page.getByText('Coupure d’eau jeudi')).toBeVisible();
});

test('l’épinglé a son bandeau, sans intitulé de jour ni ligne de temps', async ({ page }) => {
	await accueil(page);
	const bandeau = page.locator('.epingle-bloc');
	await expect(bandeau.getByText('Règles du local vélos')).toBeVisible();
	await expect(bandeau.locator('.flux-day-label')).toHaveCount(0);
	const ligne = await bandeau
		.locator('.flux-timeline')
		.evaluate((el) => getComputedStyle(el, '::before').display);
	expect(ligne).toBe('none');
	//  Et il n'est pas lu deux fois : la chronologie ne le reprend pas.
	await expect(page.getByText('Règles du local vélos')).toHaveCount(1);
});

test('les Archives s’ouvrent et rendent leur carte, atténuée', async ({ page }) => {
	await accueil(page);
	await expect(page.getByText('Ravalement terminé')).toHaveCount(0);
	await page.getByRole('button', { name: /Archives/ }).click();
	await expect(page.getByText('Ravalement terminé')).toBeVisible();
	const opacite = await page
		.locator('.flux-timeline', { hasText: 'Ravalement terminé' })
		.evaluate((el) => getComputedStyle(el).opacity);
	expect(Number(opacite)).toBeLessThan(1);
});

test('l’accueil porte la carte des consignes, vers la fiche', async ({ page }) => {
	await accueil(page);
	const lien = page.getByRole('link', { name: new RegExp(LIBELLE) });
	await expect(lien).toHaveAttribute('href', ADRESSE);
	await expect(lien).toHaveAttribute('target', '_blank');
});

test('l’annuaire dit la même chose, sous forme de bouton', async ({ page }) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/admin/annuaire'
			? {
					cs: { ag_annee: null, ag_date: null, membres: [] },
					syndic: { nom_syndic: '', adresse: '', site_web: null, membres: [] },
					whatsapp_url: null,
				}
			: undefined,
	);
	await page.goto('/annuaire');
	await attendreHydratation(page);
	const lien = page.getByRole('link', { name: LIBELLE });
	await expect(lien).toHaveAttribute('href', ADRESSE);
	await expect(lien).toHaveClass(/btn/);
});
