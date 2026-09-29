/*
 *  **La démarche « Nouvel arrivant » du profil, et la demande en attente.**
 *
 *  Extraites de `profil/+page.svelte` le 29/09/2026 (#779, modularité) :
 *  `DemarcheArrivant` et `EncartAvertissement`. Un découpage ne change pas un
 *  comportement — ce test le vérifie sur le VRAI écran, API simulée : ce qui
 *  part au serveur, la section qui se retire une fois la réponse donnée, les
 *  bâtiments lus dans la copropriété (le repli « Bât. 1 à 4 » écrit en dur a
 *  été retiré), et le bandeau d'une demande en attente.
 */
import { expect, test, type Page } from '@playwright/test';
import { attendreHydratation, simulerApi } from './aides';

type Envoi = { methode: string; chemin: string; corps: unknown };

async function ouvrir(
	page: Page,
	reponses: (chemin: string) => unknown = () => undefined,
): Promise<Envoi[]> {
	const envois: Envoi[] = [];
	page.on('request', (r) => {
		const chemin = new URL(r.url()).pathname;
		if (['POST', 'PATCH'].includes(r.method()) && chemin.startsWith('/api/')) {
			envois.push({ methode: r.method(), chemin, corps: r.postDataJSON() });
		}
	});
	await simulerApi(page, reponses);
	await page.goto('/profil');
	await attendreHydratation(page);
	return envois;
}

const section = (page: Page) =>
	page.locator('section', { has: page.getByRole('heading', { name: 'Démarche Nouvel Arrivant' }) });

test('« Je suis déjà résident » enregistre le choix et retire la section', async ({ page }) => {
	const envois = await ouvrir(page, (chemin) => {
		if (chemin === '/api/auth/batiments') return [{ id: 7, numero: '7' }];
	});
	await expect(section(page)).toBeVisible();
	await section(page).getByRole('button', { name: 'Je suis déjà résident' }).click();

	await expect(section(page)).toHaveCount(0);
	expect(envois).toContainEqual({
		methode: 'PATCH',
		chemin: '/api/auth/me',
		corps: { demarche_arrivant: 'deja_resident' },
	});
});

test('« nouvel arrivant » exige l’ancien résident, puis déclare le bâtiment choisi', async ({
	page,
}) => {
	const envois = await ouvrir(page, (chemin) => {
		if (chemin === '/api/auth/batiments')
			return [
				{ id: 7, numero: '7' },
				{ id: 9, numero: '9' },
			];
	});
	const bloc = section(page);
	await bloc.getByLabel('Bâtiment concerné').selectOption('9');

	//  Sans nom ni « Je ne sais pas » : rien ne part.
	await bloc.getByRole('button', { name: 'Je suis un nouvel arrivant' }).click();
	await expect(bloc).toBeVisible();
	expect(envois.filter((e) => e.chemin === '/api/admin/me/accueil-arrivant')).toHaveLength(0);

	await bloc.getByLabel('Je ne sais pas').check();
	await bloc.getByRole('button', { name: 'Je suis un nouvel arrivant' }).click();
	await expect(section(page)).toHaveCount(0);
	expect(envois).toContainEqual({
		methode: 'POST',
		chemin: '/api/admin/me/accueil-arrivant',
		corps: { batiment: 'Bât. 9', ancien_resident: null, ancien_resident_inconnu: true },
	});
});

test('sans liste de bâtiments, aucun bâtiment n’est inventé', async ({ page }) => {
	//  Le repli « Bât. 1 à 4 » ne jouait QUE sur une liste vide — celle d'un
	//  chargement en échec. C'étaient les bâtiments de cette résidence-ci.
	await ouvrir(page, (chemin) => {
		if (chemin === '/api/auth/batiments') return [];
	});
	const options = section(page).getByLabel('Bâtiment concerné').locator('option');
	await expect(options).toHaveText(['— Sélectionner —']);
});

test('une demande en attente s’affiche dans l’encart d’avertissement', async ({ page }) => {
	await ouvrir(page, (chemin) => {
		if (chemin === '/api/auth/me/demandes-modification')
			return [
				{
					id: 1,
					statut_demande: 'en_attente',
					statut_souhaite: null,
					batiment_nom_souhaite: 'Bât. 3',
					cree_le: '2026-09-28T10:00:00',
				},
			];
	});
	const encart = page.locator('.encart-avertissement', { hasText: 'Demande en attente' });
	await expect(encart).toContainText('déménagement vers Bât. 3');
	//  La charte d'avertissement : son fond, et son texte (#1455) — jamais le
	//  blanc par défaut ni la couleur de texte ordinaire.
	await expect(encart).toHaveCSS('background-color', 'rgb(253, 243, 224)');
	await expect(encart).toHaveCSS('color', 'rgb(123, 88, 21)');
});
