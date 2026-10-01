/*
 *  **La consommation de l'assistant IA se lit dans l'onglet Maintenance (#1383).**
 *
 *  Rien ne comptait les appels à l'assistant, dont un usage automatique. Ce test
 *  rend le VRAI onglet, API simulée, et lit ce qu'un administrateur voit : la
 *  jauge du plafond, le mois avec son coût estimé, et — c'est la promesse qui
 *  compte — un mois sans tarif qui dit « coût non renseigné » au lieu d'un 0 €.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const LIGNE = {
	usage: 'reponse_courriel',
	libelle: 'Mise en forme des réponses par courriel',
	modele: 'gpt-4o-mini',
	appels: 412,
	erreurs: 3,
	refus: 0,
	jetons_entree: 820000,
	jetons_sortie: 164000,
};

const CONSOMMATION = {
	mois_courant: '2026-09',
	plafonds: [
		{ usage: 'reponse_courriel', libelle: LIGNE.libelle, plafond: 1000000, consommes: 984000 },
		{ usage: 'description', libelle: 'Rédaction d’une description', plafond: 0, consommes: 0 },
	],
	mois: [
		{ mois: '2026-09', usages: [{ ...LIGNE, jetons_cache: 512000, cout_usd: '0.2200' }] },
		{ mois: '2026-08', usages: [{ ...LIGNE, jetons_cache: 0, cout_usd: null }] },
	],
};

test('Maintenance : la consommation de l’assistant, son plafond et son coût', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/llm-consommation') return CONSOMMATION;
		return undefined;
	});
	await page.goto('/admin?onglet=maintenance');

	const carte = page.locator('section.config-section', {
		has: page.getByText('Consommation de l’assistant IA', { exact: true }),
	});
	await expect(carte).toBeVisible();

	//  La jauge : seul l'usage plafonné en a une, et elle passe à l'alerte à 98 %.
	await expect(carte.getByRole('progressbar')).toHaveCount(1);
	await expect(carte.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '98');
	await expect(carte.locator('.jauge-alerte')).toHaveCount(1);

	//  Le coût : estimé quand il y a un tarif, TU quand il n'y en a pas.
	await expect(carte.getByText(/0,22\s\$US estimés/)).toBeVisible();
	//  La part lue en cache se dit, quand il y en a une.
	await expect(carte.getByText(/dont 512\s000 en cache/)).toBeVisible();
	await expect(carte.getByText('coût non renseigné')).toHaveCount(1);
	await expect(carte.getByText('3 en échec').first()).toBeVisible();

	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde, 'défilement horizontal dans l’onglet Maintenance').toBe(false);

	await carte.screenshot({
		path: `test-results/consommation-ia-${test.info().project.name}.png`,
	});
});
