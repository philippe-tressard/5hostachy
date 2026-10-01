/*
 *  **L'identité de la copropriété : une saisie, deux écrans** (#779, 01/10/2026).
 *
 *  Admin › Fiche copropriété et la fiche de la page Résidence saisissaient nom,
 *  adresse, décomptes de lots, année et immatriculation chacune à sa façon. La
 *  copie de Résidence n'ENVOYAIT pas un nombre vidé : l'ancienne valeur restait,
 *  sans un mot. Les deux passent par `ChampsIdentiteCopropriete` ; ce test tient,
 *  sur la requête réellement envoyée, ce que la factorisation devait corriger
 *  — un nombre vidé part à `null`, des deux écrans.
 */
import { expect, test, type Page, type Request } from '@playwright/test';
import { attendreHydratation, MEMBRE_CS, simulerApi } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
const FICHE = {
	id: 1,
	nom: 'Résidence témoin',
	adresse: '1 rue Exemple',
	nb_lots_total: 195,
	nb_lots_principaux: 63,
	annee_construction: 1975,
	numero_immatriculation: 'AA0000000',
};

async function ouvrir(page: Page, adresse: string, compte = MEMBRE_CS): Promise<Request[]> {
	const envois: Request[] = [];
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return compte;
		if (chemin === '/api/copropriete') return FICHE;
	});
	page.on('request', (r) => {
		if (r.method() === 'PATCH' && new URL(r.url()).pathname === '/api/copropriete') envois.push(r);
	});
	await page.goto(adresse);
	await attendreHydratation(page);
	return envois;
}

async function viderLesLots(page: Page) {
	await expect(page.getByLabel(/Nom de la résidence/)).toHaveValue(FICHE.nom);
	await page.getByLabel(/Nombre de lots — total/).fill('');
	await page.getByRole('button', { name: /Enregistrer/ }).click();
}

test('Résidence : un nombre vidé part à null — il s’efface', async ({ page }) => {
	const envois = await ouvrir(page, '/residence');
	await page.getByRole('button', { name: 'Modifier la fiche de la résidence' }).click();
	await viderLesLots(page);
	await expect.poll(() => envois.length).toBe(1);
	const corps = envois[0].postDataJSON();
	expect(corps.nb_lots_total).toBeNull();
	expect(corps.nom).toBe(FICHE.nom);
	expect(corps.nb_lots_principaux).toBe(63);
});

test('Admin › Fiche : les mêmes champs, la même règle', async ({ page }) => {
	const envois = await ouvrir(page, '/admin?onglet=copropriete', ADMIN);
	await viderLesLots(page);
	await expect.poll(() => envois.length).toBe(1);
	const corps = envois[0].postDataJSON();
	expect(corps.nb_lots_total).toBeNull();
	expect(corps.annee_construction).toBe(1975);
});
