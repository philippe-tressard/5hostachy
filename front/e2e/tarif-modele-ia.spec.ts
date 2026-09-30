/*
 *  **Le ✨ à côté du modèle remplit les deux prix d'un usage (30/09/2026).**
 *
 *  Demandé : « un use case IA pour demander la tarification de l'IA concernée,
 *  l'icône IA à côté du modèle de tous les use case, l'IA remplit ces 2
 *  valeurs ». Ce test rend le VRAI onglet, API simulée, et vérifie ce que
 *  l'administrateur voit : l'icône dans chaque bloc, les prix en EUROS alors que
 *  le serveur rend des CENTIMES, la remarque de l'assistant — et que le modèle
 *  interrogé est celui du bloc, pas celui de l'usage « Tarif ».
 */
import { expect, test } from '@playwright/test';
import { MEMBRE_CS, simulerApi } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const usage = (code: string, libelle: string) => ({
	code,
	libelle,
	description: '',
	prompt_defaut: 'Consigne.',
	max_jetons_defaut: 2000,
	cles: Object.fromEntries(
		['actif', 'modele', 'prompt', 'max_jetons', 'plafond_mois', 'prix_entree', 'prix_sortie'].map(
			(c) => [c, `llm_${code}_${c}`],
		),
	),
});

const USAGES = [
	usage('description', 'Rédaction d’une description'),
	usage('tarif_modele', 'Tarif d’un modèle'),
];

const CONFIG = {
	llm_actif: '1',
	llm_fournisseur: 'anthropic',
	llm_api_key: '••••',
	llm_description_actif: '1',
	llm_description_modele: 'modele-de-la-description',
	llm_tarif_modele_actif: '1',
	llm_tarif_modele_modele: 'modele-du-tarif',
};

test('Assistant IA : le ✨ du modèle remplit les prix des jetons', async ({ page }) => {
	let demande: unknown = null;
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/admin') return CONFIG;
		if (chemin === '/api/config/llm-usages') return USAGES;
		return undefined;
	});
	//  Posé APRÈS `simulerApi` : Playwright essaie la dernière route en premier.
	await page.route(
		(url) => url.pathname === '/api/config/llm-tarif',
		async (route) => {
			demande = route.request().postDataJSON();
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({
					prix_entree: 20,
					prix_sortie: 120,
					remarque: '0,22 $ et 1,30 $ au taux de 0,92.',
				}),
			});
		},
	);
	await page.goto('/admin?onglet=ia');

	//  Une icône par bloc — comptée dans le DOM : les blocs arrivent repliés, et
	//  un bouton replié n'a pas de rôle accessible.
	await expect(page.locator('details.bloc-usage .ligne-choix > .btn-icon')).toHaveCount(
		USAGES.length,
	);

	const bloc = page.locator('details.bloc-usage', { hasText: 'Rédaction d’une description' });
	await bloc.locator('summary').click();
	await bloc.getByRole('button', { name: 'Demander à l’assistant le tarif de ce modèle' }).click();

	await expect(bloc.getByLabel('Prix des jetons envoyés')).toHaveValue('0.2');
	await expect(bloc.getByLabel('Prix des jetons produits')).toHaveValue('1.2');
	await expect(bloc.getByText(/Prix proposés par l’assistant — 0,22 \$/)).toBeVisible();
	expect(demande).toEqual({ modele: 'modele-de-la-description' });

	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde, 'défilement horizontal dans l’onglet Assistant IA').toBe(false);

	await bloc.screenshot({ path: `test-results/tarif-modele-ia-${test.info().project.name}.png` });
});

test('Assistant IA : sans l’usage « Tarif » activé, aucune icône ✨ à côté du modèle', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/admin') return { ...CONFIG, llm_tarif_modele_actif: '0' };
		if (chemin === '/api/config/llm-usages') return USAGES;
		return undefined;
	});
	await page.goto('/admin?onglet=ia');
	await expect(page.locator('details.bloc-usage')).toHaveCount(USAGES.length);
	await expect(page.locator('details.bloc-usage .ligne-choix > .btn-icon')).toHaveCount(0);
});
