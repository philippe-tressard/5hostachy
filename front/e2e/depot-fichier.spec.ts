/*
 *  **Déposer un fichier : un seul sélecteur, et il se touche au doigt.**
 *
 *  Relevé le 27/09/2026 (#1329), sur l'écran Résidence :
 *
 *  - `FormulaireDocument` (plans, règlement, CR d'AG, diagnostics) gardait un
 *    `<input type="file">` NU — le « Parcourir… » du navigateur, à côté du
 *    bouton 📎 et des pastilles de tous les autres dépôts ;
 *  - le bouton 📎 de `FichiersUpload`, lui, mesurait **21 px** de haut sur un
 *    téléphone : sous la cible tactile de 44 px (`standards/11` §10) que le
 *    site pose pourtant sur `.btn-icon`, `.form-actions .btn` et les sections
 *    pliées. Il sert sur TOUS les dépôts de fichiers et de photos.
 *
 *  ## Pourquoi l'API est simulée
 *
 *  L'écran est derrière une connexion : un test qui chercherait le bouton sur
 *  une page publique serait sauté, donc faux vert (`cible-tactile.spec.ts`).
 *  On rend donc le VRAI écran avec un compte du conseil syndical simulé — ce
 *  que mesure le test est le composant réel, dans le formulaire réel.
 *
 *  ⚠️ Les deux assertions de taille sont opposées, comme dans
 *  `cible-tactile.spec.ts` : 44 px au doigt, et rien de changé à la souris.
 */
import { expect, test, type Page } from '@playwright/test';

const MEMBRE_CS = {
	id: 1,
	nom: 'Témoin',
	prenom: 'CS',
	email: 'temoin@exemple.test',
	statut: 'copropriétaire_résident',
	role: 'conseil_syndical',
	roles: ['conseil_syndical'],
	actif: true,
};

/** Rend l'écran Résidence et ouvre « Ajouter un plan ». */
async function ouvrirAjoutPlan(page: Page) {
	//  ⚠️ Le CHEMIN commence par `/api/` : un motif `/api/` n'importe où intercepte
	//  aussi le module source `/src/lib/api/…`, et la page tombe en 500.
	await page.route(
		(url) => url.pathname.startsWith('/api/'),
		(route) => {
			const u = route.request().url();
			let corps: unknown = [];
			if (/\/auth\/me/.test(u)) corps = MEMBRE_CS;
			else if (/\/documents\/categories/.test(u))
				corps = [{ id: 1, code: 'plan_residence', nom: 'Plans' }];
			else if (/\/copropriete(\?|$)/.test(u)) corps = { id: 1, nom: 'Résidence témoin' };
			else if (/config|pages|parametres|sante/.test(u)) corps = {};
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify(corps),
			});
		},
	);
	await page.goto('/residence');
	const plans = page
		.locator('section, div')
		.filter({ has: page.getByRole('heading', { name: /Plans/ }) })
		.last();
	await plans
		.getByRole('button', { name: /Ajouter/ })
		.first()
		.click();
	const depot = page.locator('.fichiers-upload').first();
	//  Cas zéro : sans le composant, aucune mesure ne prouverait rien.
	await expect(depot, 'le formulaire de plan ne porte pas FichiersUpload').toBeVisible();
	return depot;
}

test('un document se dépose par FichiersUpload, jamais par le sélecteur du navigateur', async ({
	page,
}) => {
	const depot = await ouvrirAjoutPlan(page);
	await expect(depot.locator('.fichiers-ajout')).toContainText('Ajouter');
	await expect(page.locator('input[type=file]:visible')).toHaveCount(0);
});

test('au doigt, le bouton 📎 fait au moins 44 px de haut', async ({ page }, info) => {
	test.skip(info.project.name !== 'mobile', 'la règle ne vise que `pointer: coarse`');
	const depot = await ouvrirAjoutPlan(page);
	const boite = await depot.locator('.fichiers-ajout').boundingBox();
	expect(boite, 'le bouton d’ajout n’a pas été rendu').not.toBeNull();
	expect(boite!.height, 'hauteur de la cible tactile').toBeGreaterThanOrEqual(44);
});

test('à la souris, le bouton 📎 garde sa taille', async ({ page }, info) => {
	test.skip(info.project.name !== 'bureau', 'le pendant : rien ne change au pointeur fin');
	const depot = await ouvrirAjoutPlan(page);
	const boite = await depot.locator('.fichiers-ajout').boundingBox();
	expect(boite, 'le bouton d’ajout n’a pas été rendu').not.toBeNull();
	expect(boite!.height, 'la règle tactile déborde sur le bureau').toBeLessThan(44);
});
