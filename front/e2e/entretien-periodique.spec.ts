/*
 *  **Espace CS › Reporting › Entretien périodique** (arbitré le 10/10/2026).
 *
 *  Les visites sous contrat ou à récurrence ont quitté la relance syndic : cette
 *  vue les montre, une ligne par visite de l'année, avec l'état que le SERVEUR
 *  calcule (`utils/entretien_periodique`). L'écran ne fait que le nommer et le
 *  compter — l'API simulée rend donc la forme réelle de
 *  `GET /tickets/entretiens-periodiques`, états compris.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';
import type { EntretienPeriodiqueResponse } from '../src/lib/api';

const VISITE = {
	statut: 'chez_prestataire',
	ferme_le: null,
	prestataire_nom: 'DURAND',
	contrat_libelle: 'Entretien toitures',
};

const REPONSE: EntretienPeriodiqueResponse = {
	exercice: 2026,
	visites: [
		{
			...VISITE,
			id: 47,
			numero: 'TK-E00047',
			titre: 'Toitures — Entretien toitures',
			statut: 'résolu',
			debut: '2026-01-15T00:00:00',
			ferme_le: '2026-01-20T09:00:00',
			etat: 'realisee',
		},
		{
			...VISITE,
			id: 48,
			numero: 'TK-E00048',
			titre: 'Toitures — Entretien toitures',
			debut: '2026-07-15T00:00:00',
			etat: 'non_realisee',
		},
		{
			...VISITE,
			id: 90,
			numero: 'TK-000090',
			titre: 'Portes — Maintenance',
			debut: '2026-12-01T00:00:00',
			etat: 'a_venir',
		},
	],
};

test('chaque visite de l’année dit si elle a été réalisée', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets/entretiens-periodiques') return REPONSE;
		return undefined;
	});
	await page.goto('/espace-cs/reporting?vue=entretien');
	await attendreHydratation(page);

	await expect(page.getByRole('heading', { name: /Entretien périodique — 2026/ })).toBeVisible();
	const lignes = page.locator('.report-table tbody tr');
	await expect(lignes).toHaveCount(3);
	await expect(lignes.nth(0)).toContainText('✅ Réalisée');
	await expect(lignes.nth(0)).toContainText('le 20 janv. 2026');
	await expect(lignes.nth(1)).toContainText('⚠️ Non réalisée');
	await expect(lignes.nth(1)).toContainText('Entretien toitures');
	await expect(lignes.nth(2)).toContainText('⏳ À venir');
	await expect(lignes.nth(1).getByRole('link')).toHaveAttribute('href', '/tickets/48');

	//  Les compteurs : une réalisée, une en retard — signalée —, une à venir.
	//  Le libellé EXACT : « Réalisées » est contenu dans « Non réalisées ».
	const compteur = (libelle: string) =>
		page.locator('.kpi-card').filter({ has: page.getByText(libelle, { exact: true }) });
	await expect(compteur('Réalisées')).toContainText('1');
	await expect(compteur('Non réalisées')).toContainText('1');
	await expect(compteur('Non réalisées')).toHaveClass(/kpi-alert/);
	await expect(compteur('À venir')).toContainText('1');
	await expect(compteur('À planifier')).toContainText('0');
});

test('sans visite cette année, la vue le dit au lieu de rester vide', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets/entretiens-periodiques') return { exercice: 2026, visites: [] };
		return undefined;
	});
	await page.goto('/espace-cs/reporting?vue=entretien');
	await attendreHydratation(page);
	await expect(page.getByText('Aucune visite d’entretien périodique en 2026')).toBeVisible();
});
