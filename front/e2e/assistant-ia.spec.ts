/*
 *  **Le ✨ à côté du modèle cherche, remplit et enregistre les deux prix (30/09/2026).**
 *
 *  Demandé : « l'icône IA à côté du modèle de tous les use case […] recherche
 *  le prix sur l'opérateur du modèle du use case, remplit les prix et
 *  enregistre ». Ce test rend le VRAI onglet, API simulée, et vérifie ce que
 *  l'administrateur voit : l'icône dans chaque bloc, les TROIS prix en dollars,
 *  la source du chiffre — et que la demande porte
 *  sur l'usage du bloc et son modèle, pas sur l'usage « Tarif ».
 */
import { expect, test, type Locator } from '@playwright/test';
import { MEMBRE_CS, simulerApi } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const usage = (code: string, libelle: string) => ({
	code,
	libelle,
	description: '',
	prompt_defaut: 'Consigne.',
	max_jetons_defaut: 2000,
	cles: Object.fromEntries(
		[
			'actif',
			'modele',
			'prompt',
			'max_jetons',
			'plafond_mois',
			'prix_entree',
			'prix_sortie',
			'prix_cache',
			'effort',
		].map((c) => [c, `llm_${code}_${c}`]),
	),
	efforts: [
		{ val: 'faible', label: 'Faible' },
		{ val: 'moyen', label: 'Moyen' },
		{ val: 'eleve', label: 'Élevé' },
	],
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

/** Le champ d'un prix — par le DÉBUT de son nom : l'aide, dans le même
 *  `<label>`, nomme parfois un autre prix (« …au prix des jetons envoyés »). */
const prix = (bloc: Locator, nom: string) =>
	bloc.getByRole('spinbutton', { name: new RegExp(`^Prix des jetons ${nom} \\(\\$`) });

test('Assistant IA : le ✨ du modèle enregistre les prix des jetons', async ({ page }) => {
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
					prix_entree: '0.2',
					prix_sortie: '1.2',
					prix_cache: '0.02',
					remarque:
						'Grille platform.openai.com/docs/pricing, ligne « gpt-5.6-luna » : envoyés 0,2 $, produits 1,2 $, en cache 0,02 $ par million.',
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
	await bloc.getByRole('button', { name: 'Chercher et enregistrer le tarif de ce modèle' }).click();

	await expect(prix(bloc, 'envoyés')).toHaveValue('0.2');
	await expect(prix(bloc, 'produits')).toHaveValue('1.2');
	await expect(prix(bloc, 'en cache')).toHaveValue('0.02');
	//  L'unité se lit sur le libellé : des dollars, comme la grille.
	await expect(bloc.getByText('Prix des jetons envoyés ($ / million)')).toBeVisible();
	await expect(bloc.getByText(/Tarif enregistré — Grille platform\.openai\.com/)).toBeVisible();
	expect(demande).toEqual({ usage: 'description', modele: 'modele-de-la-description' });

	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde, 'défilement horizontal dans l’onglet Assistant IA').toBe(false);

	await bloc.screenshot({ path: `test-results/assistant-ia-${test.info().project.name}.png` });
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

test('Assistant IA : ouvrir un usage plus bas montre son DÉBUT, pas sa fin', async ({ page }) => {
	//  Signalé le 30/09/2026 : « quand tu ouvres une section, tu te trouves à la
	//  fin de la section ouverte ». Le bloc ouvert au-dessus se replie et remonte
	//  tout ce qui suit ; sans `amenerEnVue`, la fenêtre tombe dans le bas du
	//  bloc qu'on vient d'ouvrir.
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/admin') return CONFIG;
		if (chemin === '/api/config/llm-usages') return USAGES;
		return undefined;
	});
	await page.goto('/admin?onglet=ia');
	const blocs = page.locator('details.bloc-usage');
	await expect(blocs).toHaveCount(USAGES.length);

	await blocs.nth(0).locator('summary').click();
	await expect(blocs.nth(0)).toHaveAttribute('open', '');
	//  Descendre jusqu'au second usage, sous le premier déplié.
	await blocs.nth(1).locator('summary').scrollIntoViewIfNeeded();
	await blocs.nth(1).locator('summary').click();

	await expect(blocs.nth(0)).not.toHaveAttribute('open', '');
	await expect(blocs.nth(1)).toHaveAttribute('open', '');
	//  Le titre du bloc ouvert est dans la fenêtre, sous l'en-tête fixe.
	await expect
		.poll(
			async () => {
				const haut = await blocs
					.nth(1)
					.locator('summary')
					.evaluate((e) => e.getBoundingClientRect().top);
				return haut >= 0 && haut < page.viewportSize()!.height / 2;
			},
			{ message: 'le haut du bloc ouvert n’est pas dans la moitié haute de la fenêtre' },
		)
		.toBe(true);
});

test('Assistant IA : l’effort de raisonnement se choisit par usage et s’enregistre', async ({
	page,
}) => {
	let enregistre: Record<string, string> | null = null;
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/admin') return CONFIG;
		if (chemin === '/api/config/llm-usages') return USAGES;
		return undefined;
	});
	//  Posé APRÈS `simulerApi` : Playwright essaie la dernière route en premier.
	await page.route(
		(url) => url.pathname === '/api/config',
		async (route) => {
			if (route.request().method() === 'PUT') enregistre = route.request().postDataJSON();
			await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
		},
	);
	await page.goto('/admin?onglet=ia');
	const bloc = page.locator('details.bloc-usage', { hasText: 'Rédaction d’une description' });
	await bloc.locator('summary').click();

	await expect(bloc.getByText('Effort de raisonnement')).toBeVisible();
	await bloc.getByText('Faible', { exact: true }).click();
	await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();

	await expect.poll(() => enregistre?.llm_description_effort).toBe('faible');
	//  L'autre usage n'a rien reçu : chacun a le sien.
	expect(enregistre!.llm_tarif_modele_effort ?? '').toBe('');
});
