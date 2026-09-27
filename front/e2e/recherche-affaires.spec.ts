/*
 *  **La recherche libre de la page Affaires** (27/09/2026, maquette A avec
 *  l'extrait et les Archives de la C).
 *
 *  Le serveur décide de ce qui correspond (`test_recherche_affaires.py`) ; ce
 *  test-ci vérifie ce qu'on LIT : la liste réduite aux affaires trouvées, dans
 *  l'ordre du serveur, « Trouvé dans … » et le passage surligné sur la carte,
 *  les Archives tues puis ajoutées sur demande — au bureau comme au téléphone.
 */
import { expect, test, type Page } from '@playwright/test';
import { simulerApi } from './aides';

const affaire = (id: number, titre: string, archivee = false) => ({
	id,
	numero: `TK-${id}`,
	titre,
	description: 'Rien de particulier',
	categorie: 'panne',
	statut: archivee ? 'résolu' : 'ouvert',
	priorite: 'normale',
	auteur_id: 2,
	auteur_nom: 'Jeanne MARTIN',
	perimetre_cible: ['résidence'],
	photos_urls: [],
	fichiers_urls: [],
	archivee,
	natures: ['activite'],
	cree_le: '2026-09-20T10:00:00',
	mis_a_jour_le: '2026-09-20T10:00:00',
});

const AFFAIRES = [
	affaire(1, 'Porte du hall'),
	affaire(2, 'Tache au plafond'),
	affaire(3, 'Dégât des eaux au parking', true),
];

/** Ce que le serveur répond à « fuite » : la suite de l'affaire 2, puis l'archivée. */
const TROUVEES = [
	{
		ticket_id: 2,
		ou: 'suite',
		date: '2026-09-19T08:00:00',
		auteur: 'Paul DURAND',
		extrait: [
			{ texte: 'Le plombier confirme une ', surligne: false },
			{ texte: 'fuite', surligne: true },
			{ texte: ' sur la colonne', surligne: false },
		],
	},
	{ ticket_id: 3, ou: 'titre', extrait: [] },
];

async function rechercher(page: Page) {
	const demandes: string[] = [];
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return AFFAIRES;
		if (chemin === '/api/tickets/recherche') return TROUVEES;
	});
	page.on('request', (r) => {
		if (r.url().includes('/api/tickets/recherche')) demandes.push(new URL(r.url()).search);
	});
	await page.goto('/tickets');
	//  Cas zéro : sans recherche, les deux affaires actives, pas l'archivée.
	await expect(page.locator('.carte-liste')).toHaveCount(2);
	await page.getByLabel('Recherche', { exact: true }).fill('fuite');
	return demandes;
}

test('la liste ne garde que ce que le serveur a trouvé, et dit où', async ({ page }) => {
	const demandes = await rechercher(page);

	await expect(page.locator('.carte-liste')).toHaveCount(1);
	const carte = page.locator('.carte-liste').first();
	await expect(carte).toContainText('Tache au plafond');
	await expect(carte.locator('.pastille-trouve')).toHaveText('Trouvé dans une suite');
	await expect(carte.locator('mark')).toHaveText('fuite');
	await expect(carte.locator('.origine')).toContainText('Paul DURAND');
	expect(demandes, 'une seule requête après la frappe').toEqual(['?q=fuite']);

	//  L'archivée est signalée, pas montrée — puis ajoutée sur demande.
	const bilan = page.locator('.bilan-recherche');
	await expect(bilan).toContainText('1 affaire');
	await expect(bilan).toContainText('1 autre aux Archives');
	await bilan.getByRole('button', { name: 'Les inclure' }).click();
	await expect(page.locator('.carte-liste')).toHaveCount(2);
	await expect(page.locator('.carte-liste').nth(1).locator('.badge')).toContainText(['Archivée']);
	await expect(page.getByLabel('Inclure les Archives')).toBeChecked();

	//  Effacer rend la liste d'avant.
	await bilan.getByRole('button', { name: 'Effacer la recherche' }).click();
	await expect(page.locator('.carte-liste')).toHaveCount(2);
	await expect(page.locator('.pastille-trouve')).toHaveCount(0);
});

test('la ligne Catégorie a disparu', async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/tickets' ? AFFAIRES : undefined));
	await page.goto('/tickets');
	await expect(page.locator('.carte-liste').first()).toBeVisible();
	await expect(page.getByRole('group', { name: 'Catégorie' })).toHaveCount(0);
	await expect(page.getByRole('group', { name: 'Suivi' })).toBeVisible();
});
