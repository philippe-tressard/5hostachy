/*
 *  **« L'envoyer par courriel » demande l'adresse** (03/10/2026, signalé à
 *  l'écran : « envoyé par mail ne demande pas l'email »).
 *
 *  Le clic remplace le bouton par le champ ; le bouton quitte alors le DOM AVANT
 *  que l'événement n'atteigne `clicDehors` (fenêtre), qui ne le retrouvait plus
 *  dans la bulle et la FERMAIT. Le champ n'apparaissait jamais.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

const AFFAIRE = {
	id: 8,
	numero: 'TK-124291',
	titre: 'Bruit nocturne',
	description: 'Musique tard le soir.',
	categorie: 'nuisance',
	statut: 'en_cours',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['résidence'],
	public_cible: null,
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	natures: ['activite'],
	cree_le: '2026-09-20T10:00:00',
	mis_a_jour_le: '2026-09-21T10:00:00',
};

test('« L’envoyer par courriel » ouvre le champ adresse et le garde ouvert', async ({
	page,
	context,
}) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']).catch(() => {});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [AFFAIRE];
		if (chemin === '/api/tickets/8') return AFFAIRE;
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.locator('.carte-liste').first().getByText(AFFAIRE.titre).click();
	await page
		.getByRole('button', { name: /Copier le lien/ })
		.first()
		.click();
	await page.getByRole('button', { name: /L’envoyer par courriel/ }).click();
	await expect(page.getByRole('textbox', { name: 'Adresse du destinataire' })).toBeVisible();
	await expect(page.getByRole('textbox', { name: 'Adresse du destinataire' })).toBeFocused();
});
