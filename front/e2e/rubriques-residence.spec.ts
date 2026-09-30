/*
 *  **Les trois rubriques de documents de la Résidence : une écriture, trois
 *  envois distincts** (#779, 30/09/2026).
 *
 *  Plans, règlement et comptes-rendus d'AG étaient écrits trois fois dans la
 *  page ; ils le sont une fois, dans `RubriqueDocuments`, paramétré. Ce test tient
 *  ce que la factorisation devait CONSERVER, sur la requête réellement envoyée :
 *  chaque rubrique dépose dans SA catégorie, seule l'AG porte année et date
 *  d'assemblée (et ne part pas sans elles), le règlement ne décrit aucun
 *  périmètre. La copie du plan avait déjà divergé une fois (#470).
 */
import { expect, test, type Page, type Request } from '@playwright/test';
import { attendreHydratation, simulerApi } from './aides';

const CATEGORIES = [
	{ id: 11, code: 'plan_residence', nom: 'Plans' },
	{ id: 12, code: 'reglement_copropriete', nom: 'Règlement' },
	{ id: 13, code: 'pv_ag', nom: 'PV d’AG' },
];

async function residence(page: Page): Promise<Request[]> {
	const depots: Request[] = [];
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/documents/categories') return CATEGORIES;
		if (chemin === '/api/copropriete') return { id: 1, nom: 'Résidence témoin' };
	});
	await page.route(
		(url) => url.pathname === '/api/documents',
		(route) => {
			if (route.request().method() !== 'POST') return route.fallback();
			depots.push(route.request());
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({ id: 900 + depots.length, titre: 'Déposé', perimetre_cible: [] }),
			});
		},
	);
	await page.goto('/residence');
	await attendreHydratation(page);
	return depots;
}

/** La rubrique nommée : son « + Ajouter », puis le formulaire (un groupe nommé
 *  par son intitulé), titre et fichier posés. */
async function remplir(page: Page, rubrique: RegExp, intitule: string, titre: string) {
	await page
		.locator('div')
		.filter({ has: page.getByRole('heading', { name: rubrique }) })
		.last()
		.getByRole('button', { name: /Ajouter/ })
		.click();
	const formulaire = page.getByRole('group', { name: intitule });
	await formulaire.getByRole('textbox', { name: /^Titre/ }).fill(titre);
	await formulaire
		.locator('input[type=file]')
		.first()
		.setInputFiles({
			name: 'document.pdf',
			mimeType: 'application/pdf',
			buffer: Buffer.from('%PDF-1.4'),
		});
	return formulaire;
}

/** Les champs d'un envoi multipart, lus dans le corps réellement envoyé. */
function champs(requete: Request): Record<string, string> {
	const corps = requete.postData() ?? '';
	const sortie: Record<string, string> = {};
	for (const m of corps.matchAll(/name="([^"]+)"\r\n\r\n([^\r]*)\r\n/g)) sortie[m[1]] = m[2];
	return sortie;
}

test('le plan part dans SA catégorie, sans année ni date d’AG', async ({ page }) => {
	const depots = await residence(page);
	const section = await remplir(page, /Plans/, 'Ajouter un plan', 'Plan de masse');
	await section.getByRole('button', { name: /Enregistrer/ }).click();
	await expect.poll(() => depots.length).toBe(1);
	const c = champs(depots[0]);
	expect(c.categorie_id).toBe('11');
	expect(c.titre).toBe('Plan de masse');
	expect(c.annee).toBeUndefined();
	expect(c.date_ag).toBeUndefined();
});

test('le règlement part dans SA catégorie, sans périmètre décrit', async ({ page }) => {
	const depots = await residence(page);
	const section = await remplir(
		page,
		/Règlement de copropriété/,
		'Ajouter un règlement',
		'Règlement 2024',
	);
	await section.getByRole('button', { name: /Enregistrer/ }).click();
	await expect.poll(() => depots.length).toBe(1);
	const c = champs(depots[0]);
	expect(c.categorie_id).toBe('12');
	expect(c.perimetre_cible).toBeUndefined();
});

test('le CR d’AG exige année et date, et les envoie', async ({ page }) => {
	const depots = await residence(page);
	const section = await remplir(page, /Comptes-rendus d'AG/, "Ajouter un CR d'AG", 'PV AG 2025');
	const enregistrer = section.getByRole('button', { name: /Enregistrer/ });
	//  Sans année ni date, rien ne part.
	await expect(enregistrer).toBeDisabled();
	await section.locator('#ag-annee').fill('2025');
	await section.locator('#ag-date').fill('2025-06-12');
	await enregistrer.click();
	await expect.poll(() => depots.length).toBe(1);
	const c = champs(depots[0]);
	expect(c.categorie_id).toBe('13');
	expect(c.annee).toBe('2025');
	expect(c.date_ag).toBe('2025-06-12');
});

test('plusieurs fichiers : un document chacun, nommé par son fichier si rien n’est saisi (#1479)', async ({
	page,
}) => {
	const depots = await residence(page);
	await page
		.locator('div')
		.filter({ has: page.getByRole('heading', { name: /Plans/ }) })
		.last()
		.getByRole('button', { name: /Ajouter/ })
		.click();
	const formulaire = page.getByRole('group', { name: 'Ajouter un plan' });
	//  Comme Diagnostics : le titre est facultatif quand chaque fichier a le sien.
	await formulaire
		.locator('input[type=file]')
		.first()
		.setInputFiles([
			{ name: 'plan-rdc.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4') },
			{ name: 'plan-etage.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4') },
		]);
	await formulaire.getByRole('button', { name: /Enregistrer/ }).click();
	await expect.poll(() => depots.length).toBe(2);
	expect(depots.map((d) => champs(d).titre).sort()).toEqual(['plan-etage', 'plan-rdc']);
	expect(depots.every((d) => champs(d).categorie_id === '11')).toBe(true);
});
