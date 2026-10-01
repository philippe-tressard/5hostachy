/*
 *  **Un fil de suivi qui n'a pas pu se charger le DIT** (29/09/2026, TK-124285).
 *
 *  Des copropriétaires lisaient une affaire et en voyaient les suites VIDES : la
 *  route du fil refusait (403) et l'écran avalait le refus — `catch {}`. Un fil
 *  vide et un fil illisible se rendaient pareil, et personne ne pouvait le
 *  signaler autrement que par « il n'y a rien ».
 *
 *  La règle du serveur (le fil se lit par qui lit l'affaire) est tenue par
 *  `api/tests/test_recherche_affaires.py`. Ce test tient l'ÉCRAN : quelle que
 *  soit la cause d'un échec, la fiche et la carte le disent.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const AFFAIRE = {
	id: 7,
	numero: 'TK-124285',
	titre: 'Travaux de ravalement',
	description: 'Devis à comparer.',
	categorie: 'etude_travaux',
	statut: 'ouvert',
	priorite: 'normale',
	auteur_id: 2,
	auteur_nom: 'Jeanne MARTIN',
	perimetre_cible: ['résidence'],
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	natures: ['activite'],
	cree_le: '2026-09-20T10:00:00',
	mis_a_jour_le: '2026-09-20T10:00:00',
};

async function filRefuse(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [AFFAIRE];
		if (chemin === '/api/tickets/7') return AFFAIRE;
	});
	//  Enregistrée APRÈS : Playwright essaie la dernière route d'abord.
	await page.route(
		(url) => url.pathname === '/api/tickets/7/evolutions',
		(route) =>
			route.fulfill({
				status: 403,
				contentType: 'application/json',
				body: JSON.stringify({ detail: 'Accès refusé' }),
			}),
	);
}

test('la fiche dit que le fil n’a pas pu être lu', async ({ page }) => {
	await filRefuse(page);
	await page.goto('/tickets/7');
	await attendreHydratation(page);
	await expect(page.locator('.etat-erreur')).toContainText('Accès refusé');
});

test('la carte dépliée le dit aussi', async ({ page }) => {
	await filRefuse(page);
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.locator('.carte-liste').first().getByText('Travaux de ravalement').click();
	await expect(page.locator('.carte-liste .etat-erreur')).toContainText('Accès refusé');
});
