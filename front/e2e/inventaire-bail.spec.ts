/*
 *  **L'inventaire d'un bail : un formulaire, deux places** (#1539, 02/10/2026).
 *
 *  `InventaireBail` rendait le formulaire d'un objet remis DEUX fois — la
 *  création en tête de l'inventaire, la correction dans la rangée de l'objet —,
 *  douze lignes identiques au titre près. Il l'écrit une fois
 *  (`{#snippet formulaireObjet}`). Ce test tient ce que les deux places
 *  doivent garder :
 *
 *  - la création s'ouvre AU-DESSUS du tableau, à la largeur de saisie ;
 *  - la correction s'ouvre DANS la rangée de l'objet, préremplie, et c'est ce
 *    qu'elle contient qui part au serveur.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const OBJET = {
	id: 3,
	bail_id: 7,
	type: 'cle',
	libelle: 'Clé boîte aux lettres',
	quantite: 2,
	reference: null,
	statut: 'en_possession',
	remis_le: '2026-01-01',
	rendu_le: null,
	notes: null,
};
const BAIL = {
	id: 7,
	lot_id: 1,
	statut: 'actif',
	locataire_id: 55,
	locataire_prenom: 'Paul',
	locataire_nom: 'Durand',
	locataire_email: 'paul@exemple.test',
	date_entree: '2026-01-01',
	objets: [OBJET],
};
const LOTS = [{ id: 1, numero: '12', batiment_nom: 'Bât. 2', type: 'appartement', etage: 2 }];

type Envoi = { quoi: string; corps: unknown };

async function ouvrir(page: Page): Promise<Envoi[]> {
	const envois: Envoi[] = [];
	page.on('request', (r) => {
		const url = new URL(r.url());
		if (url.pathname.startsWith('/api/') && r.method() !== 'GET')
			envois.push({ quoi: `${r.method()} ${url.pathname}`, corps: r.postDataJSON() });
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/lots/mes-lots') return LOTS;
		if (chemin === '/api/bailleur/mes-baux' || chemin === '/api/bailleur/tous-les-baux')
			return [BAIL];
		if (chemin === '/api/bailleur/baux/7/objets/3') return OBJET;
	});
	await page.goto('/mon-lot/location');
	await attendreHydratation(page);
	return envois;
}

test('la création s’ouvre au-dessus du tableau, à la largeur de saisie', async ({ page }) => {
	await ouvrir(page);
	await page.getByRole('button', { name: '+ Ajouter un objet' }).click();
	const boite = page.getByRole('group', { name: 'Nouvel objet remis' });
	await expect(boite).toBeVisible();
	await expect(boite.locator('form')).toHaveClass(/largeur-saisie/);
	//  Hors du tableau : la création n'appartient à aucune rangée.
	await expect(
		page.locator('table').getByRole('group', { name: 'Nouvel objet remis' }),
	).toHaveCount(0);
});

test('la correction s’ouvre dans la rangée, préremplie, et c’est elle qui part', async ({
	page,
}) => {
	const envois = await ouvrir(page);
	await page.getByRole('button', { name: `Corriger ${OBJET.libelle}` }).click();
	const boite = page.locator('tr.ligne-saisie').getByRole('group', { name: 'Corriger l’objet' });
	await expect(boite).toBeVisible();
	await expect(boite.locator('form')).not.toHaveClass(/largeur-saisie/);
	const libelle = boite.getByRole('textbox').first();
	await expect(libelle).toHaveValue(OBJET.libelle);
	await libelle.fill('Clé cave');
	await boite.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	await expect
		.poll(() => envois.map((e) => e.quoi))
		.toContain('PATCH /api/bailleur/baux/7/objets/3');
	expect(envois.find((e) => e.quoi.startsWith('PATCH'))!.corps).toMatchObject({
		libelle: 'Clé cave',
		quantite: 2,
	});
});
