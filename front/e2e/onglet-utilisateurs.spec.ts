/*
 *  **L'onglet Utilisateurs de l'administration** (#779, 30/09/2026).
 *
 *  Extrait de `admin/+page.svelte` en composant (`OngletUtilisateurs`, et sa
 *  modale d'accueil `ModaleAccueilArrivant`). Ce test tient ce que l'extraction
 *  devait conserver — la liste, la recherche, la modale d'accueil — et ce
 *  qu'elle a corrigé en passant : un chargement en échec restait une liste vide
 *  sans un mot (`try/finally` sans `catch`, invisible à `lint:catch-vide`).
 */
import { expect, test, type Page } from '@playwright/test';
import { attendreHydratation, MEMBRE_CS, simulerApi } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const COMPTES = [
	{
		id: 21,
		prenom: 'Jeanne',
		nom: 'Martin',
		email: 'jeanne@exemple.test',
		statut: 'copropriétaire_résident',
		role: 'résident',
		roles: ['résident'],
		actif: true,
		batiment_id: null,
	},
	{
		id: 22,
		prenom: 'Paul',
		nom: 'Durand',
		email: 'paul@exemple.test',
		statut: 'locataire',
		role: 'résident',
		roles: ['résident'],
		actif: true,
		batiment_id: null,
	},
];

async function ouvrir(page: Page, echec = false) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/utilisateurs') return COMPTES;
	});
	if (echec)
		await page.route(
			(url) => url.pathname === '/api/admin/utilisateurs',
			(route) =>
				route.fulfill({
					status: 500,
					contentType: 'application/json',
					body: JSON.stringify({ detail: 'Panne simulée' }),
				}),
		);
	await page.goto('/admin?onglet=utilisateurs');
	await attendreHydratation(page);
}

test('la liste s’affiche, et la recherche la filtre', async ({ page }) => {
	await ouvrir(page);
	const lignes = page.locator('table tbody tr');
	await expect(lignes).toHaveCount(2);
	await page.getByRole('searchbox').or(page.getByRole('textbox').first()).fill('Durand');
	await expect(lignes).toHaveCount(1);
	await expect(lignes.first()).toContainText('Paul DURAND');
});

test('un chargement en échec le dit, au lieu d’une liste vide', async ({ page }) => {
	await ouvrir(page, true);
	await expect(page.getByText('Impossible d’afficher les utilisateurs')).toBeVisible();
	await expect(page.getByText('Aucun résultat')).toHaveCount(0);
});

test('le bouton 🏠 ouvre l’accueil de l’arrivant, avec ses deux champs', async ({ page }) => {
	await ouvrir(page);
	await page.getByRole('button', { name: 'Accueil nouvel arrivant' }).first().click();
	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('Accueil nouvel arrivant');
	await expect(boite.getByLabel('Bâtiment / logement')).toBeVisible();
	await expect(boite.getByLabel('Ancien résident')).toBeVisible();
	await boite.getByRole('button', { name: 'Annuler' }).click();
	await expect(page.getByRole('dialog')).toHaveCount(0);
});
