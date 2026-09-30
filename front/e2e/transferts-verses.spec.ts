/*
 *  **Un transfert de courriel versé par erreur se défait depuis l'affaire** (#1482).
 *
 *  Demandé le 30/09/2026 : annuler en une fois, réaffecter à une autre affaire,
 *  ou en faire une nouvelle. La règle est au serveur
 *  (`api/tests/test_versement_transfert.py`) ; ce test-ci vérifie ce que l'écran
 *  en MONTRE — API simulée, compte CS :
 *
 *  - aucun bloc quand il n'y a rien à défaire ;
 *  - un transfert bloqué dit pourquoi, et ne propose aucun geste ;
 *  - « Annuler » demande confirmation, puis appelle la bonne route ;
 *  - « Déplacer » ne propose ni l'affaire ouverte, ni une affaire close.
 */
import { expect, test, type Page } from '@playwright/test';
import { simulerApi } from './aides';

const AFFAIRE = {
	id: 7,
	numero: 'TK-109008',
	titre: 'Portillon bloqué',
	description: 'Mail reçu de Jean Dupont…',
	categorie: 'etude_travaux',
	statut: 'en_cours',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	cree_le: '2026-09-29T10:00:00',
	mis_a_jour_le: '2026-09-29T10:00:00',
	perimetre_cible: [],
	photos_urls: [],
	fichiers_urls: [],
};
const DEFAISABLE = {
	id: 11,
	cree_le: '2026-09-30T12:05:00',
	transfere_par_nom: 'CS Témoin',
	suites: 3,
	affaire_creee: false,
	bloque: null,
	peut_deplacer: true,
};
const BLOQUE = {
	...DEFAISABLE,
	id: 10,
	suites: 1,
	bloque: "une suite a été écrite par quelqu'un d'autre depuis ce transfert",
};
const CHOIX = [
	{ id: 7, numero: 'TK-109008', titre: 'Portillon bloqué', statut: 'en_cours' },
	{ id: 8, numero: 'TK-200001', titre: 'Portail du parking', statut: 'ouvert' },
	{ id: 9, numero: 'TK-200002', titre: 'Portillon ancien', statut: 'résolu' },
];

async function simuler(page: Page, transferts: unknown[]) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets/7') return AFFAIRE;
		if (chemin === '/api/tickets/7/transferts') return transferts;
		if (chemin === '/api/tickets/choix') return CHOIX;
	});
}

test('rien à défaire : aucun bloc', async ({ page }) => {
	await simuler(page, []);
	await page.goto('/tickets/7');
	await expect(page.locator('h1', { hasText: 'Portillon bloqué' })).toBeVisible();
	await expect(page.getByText('Transferts de courriel')).toHaveCount(0);
});

test('un transfert se défait d’un geste, un transfert bloqué dit pourquoi', async ({ page }) => {
	await simuler(page, [DEFAISABLE, BLOQUE]);
	const appels: string[] = [];
	//  Déclarée APRÈS `simulerApi` : Playwright essaie d'abord la dernière route.
	await page.route(
		(url) => url.pathname.startsWith('/api/tickets/7/transferts/'),
		(route) => {
			appels.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({ ticket_id: 7, numero: 'TK-109008' }),
			});
		},
	);

	await page.goto('/tickets/7');
	const bloc = page.locator('section.transferts');
	await expect(bloc.getByText('Transferts de courriel')).toBeVisible();
	const [premier, second] = [bloc.locator('.transfert').nth(0), bloc.locator('.transfert').nth(1)];
	await expect(premier).toContainText('3 suites');
	await expect(second).toContainText('Ne peut plus être défait');
	await expect(second.getByRole('button')).toHaveCount(0);

	await bloc.screenshot({
		path: `test-results/transferts-verses-${test.info().project.name}.png`,
	});

	//  Déplacer : ni l'affaire ouverte, ni une affaire close.
	await premier.getByRole('button', { name: /Déplacer vers une autre affaire/ }).click();
	await premier.getByLabel('Vers l’affaire').focus();
	const propositions = premier.locator('.proposition');
	await expect(propositions).toHaveCount(1);
	await expect(propositions).toContainText('TK-200001');
	await bloc.screenshot({
		path: `test-results/transferts-deplacer-${test.info().project.name}.png`,
	});

	//  Annuler : une confirmation, puis la route du geste.
	await premier.getByRole('button', { name: 'Annuler le transfert' }).click();
	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('quitteront cette affaire');
	await boite.getByRole('button', { name: 'Annuler le transfert' }).click();
	await expect.poll(() => appels).toEqual(['POST /api/tickets/7/transferts/11/annuler']);
});
