/*
 *  **Une valeur par défaut ACTIVE remplit le champ : son étoile n'est pas rouge.**
 *
 *  Signalé à l'écran le 27/09/2026, capture à l'appui : « DESTINATAIRES* » en
 *  rouge sur un formulaire où la pastille « Tous » était déjà sélectionnée.
 *
 *  > « Les sections obligatoires ayant une valeur par défaut devraient avoir *
 *  >   en noir, car une valeur par défaut est déjà active ; * rouge, c'est
 *  >   uniquement s'il n'y a aucune valeur. »
 *
 *  La cause : Destinataires et Périmètre stockent leur défaut comme une liste
 *  VIDE (« Tous », « aucune restriction ») et jugeaient « rempli » sur la
 *  longueur de la liste. Le sélecteur affichait donc une valeur active pendant
 *  que l'étoile la disait absente — deux lectures de la même donnée.
 *
 *  Ce test ouvre le VRAI formulaire de création d'une affaire, API simulée, et
 *  lit la couleur de chaque étoile. Il éprouve aussi l'autre sens : le Titre,
 *  qui n'a pas de défaut, reste rouge tant qu'il est vide — sans quoi un test
 *  qui ne verrait jamais de rouge passerait sur n'importe quoi.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

/** L'étoile du titre de section qui porte ce libellé. */
const etoile = (page: Page, libelle: string) =>
	page.locator('.section-titre-texte', { hasText: libelle }).locator('.requis').first();

test('Nouvelle affaire : une section au défaut actif a son étoile noire', async ({ page }) => {
	await simulerApi(page);
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: /Nouvelle affaire/ }).click();

	//  Sans défaut, vide : rouge. C'est le cas qui prouve que le test sait voir le rouge.
	await expect(etoile(page, 'Titre')).toHaveClass(/requis--vide/);

	//  Défaut actif (« Tous », « aucune restriction ») : pas rouge.
	for (const libelle of ['Destinataires', 'Périmètre']) {
		const e = etoile(page, libelle);
		await expect(e, `${libelle} : pas d'étoile trouvée`).toHaveCount(1);
		await expect(e, `${libelle} : étoile rouge sur une valeur par défaut active`).not.toHaveClass(
			/requis--vide/,
		);
	}
});

test('Nouvelle actualité : « Tous » est actif, l’étoile de Destinataires est noire', async ({
	page,
}) => {
	await simulerApi(page);
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: /Nouvelle affaire/ }).click();
	//  Une actualité est une affaire de catégorie « Actualité », choisie en tête.
	await page
		.getByText(/Information — suivi optionnel/)
		.first()
		.click();

	await expect(etoile(page, 'Titre')).toHaveClass(/requis--vide/);
	for (const libelle of ['Destinataires', 'Périmètre']) {
		const e = etoile(page, libelle);
		await expect(e, `${libelle} : pas d'étoile trouvée`).toHaveCount(1);
		await expect(e, `${libelle} : étoile rouge sur une valeur par défaut active`).not.toHaveClass(
			/requis--vide/,
		);
	}
});
