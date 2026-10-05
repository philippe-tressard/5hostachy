/*
 *  **Espace CS › Comptes & accès : une demande de badge s'affiche (#1679).**
 *
 *  Trouvé en typant le client (#1572) : l'écran lisait `cmd.lot.batiment.nom`,
 *  `cmd.proprietaire`, `cmd.lot.reference` et `cmd.type_acces` — des champs que
 *  `GET /admin/commandes-acces` n'a jamais rendus. Dès qu'une commande
 *  attendait, le rendu de l'onglet levait une exception ; la conversion
 *  `as unknown as PendingAcces[]` le taisait au compilateur.
 *
 *  L'API simulée rend ici la forme RÉELLE du serveur — la ligne
 *  `commande_acces`, plus ce que la route y ajoute pour la rendre lisible
 *  (`demandeur_nom`, `lot`, `batiment`). Une forme inventée pour l'écran
 *  ferait passer le test sur un défaut qui reste en production.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

const COMMANDE = {
	id: 5,
	user_id: 7,
	lot_id: 12,
	type: 'telecommande',
	quantite: 2,
	motif: null,
	statut: 'en_attente',
	traite_par_id: null,
	motif_refus: null,
	cree_le: '2026-09-30T10:00:00',
	traite_le: null,
	demandeur_nom: 'Anne DURAND',
	lot: 'Parking 12',
	batiment: 'Bât. 4',
};

test('une demande d’accès en attente s’affiche, lisible', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/admin/commandes-acces') return [COMMANDE];
		return undefined;
	});
	await page.goto('/espace-cs');
	await attendreHydratation(page);

	const section = page.locator('section', {
		has: page.getByRole('heading', { name: /Demandes d'accès/ }),
	});
	const ligne = section.locator('.pending-row');
	await expect(ligne).toHaveCount(1);
	await expect(ligne).toContainText('Anne DURAND');
	await expect(ligne).toContainText('Bât. 4 · Parking 12');
	await expect(ligne).toContainText('Télécommande parking');
	await expect(ligne).toContainText('2');
	await expect(page.locator('.kpi-card', { hasText: "Demande(s) d'accès" })).toContainText('1');
});
