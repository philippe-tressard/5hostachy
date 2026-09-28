/*
 *  **« Sous contrat » se LIT sur les contrats, il ne se saisit pas (#1444).**
 *
 *  « 🔄 Contrat récurrent » et « Dépannage » étaient des CATÉGORIES de
 *  prestataire. Elles disaient le cadre d'une intervention, pas le métier de
 *  l'entreprise : Otis entretient l'ascenseur sous contrat et le dépanne hors
 *  contrat. Elles sont fondues en « Maintenance & dépannage », et le cadre se
 *  déduit des contrats actifs de la fiche — une pastille sur la carte, un
 *  filtre au-dessus de la liste.
 *
 *  Ce que le test tient, et qu'aucun test unitaire ne verrait : la pastille
 *  suit les CONTRATS servis (et non un champ de la fiche), et le filtre trie
 *  les cartes réellement rendues.
 */
import { expect, test, type Page } from '@playwright/test';
import { simulerApi } from './aides';

const OTIS = {
	id: 1,
	nom: 'Otis',
	specialite: 'ascenseur',
	type_prestataire: 'maintenance_depannage',
	actif: true,
};
const PLOMBIER = {
	id: 2,
	nom: 'Plomberie Martin',
	specialite: 'plomberie',
	type_prestataire: 'maintenance_depannage',
	actif: true,
};
const CONTRAT_OTIS = {
	id: 10,
	prestataire_id: 1,
	copropriete_id: 1,
	type_equipement: 'ascenseur',
	libelle: 'Ascenseur',
	date_debut: '2025-01-01',
	perimetre_cible: ['résidence'],
	actif: true,
};

async function ouvrirAnnuaire(page: Page, baseURL: string | undefined) {
	//  ⚠️ `/prestataires` a une garde SERVEUR (`+page.server.ts`) : sans cookie de
	//  session, elle renvoie vers la connexion avant que l'API simulée ne serve
	//  quoi que ce soit. Elle n'en regarde que la PRÉSENCE — la valeur est un
	//  témoin, que l'API simulée ne lit jamais.
	await page.context().addCookies([{ name: 'access_token', value: 'temoin', url: baseURL }]);
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/prestataires') return [OTIS, PLOMBIER];
		if (chemin === '/api/prestataires/contrats') return [CONTRAT_OTIS];
	});
	await page.goto('/prestataires');
	//  Cas zéro : sans les deux cartes, les assertions suivantes ne prouvent rien.
	await expect(page.locator('#presta-1')).toBeVisible();
	await expect(page.locator('#presta-2')).toBeVisible();
}

test('la carte dit « Sous contrat » d’après ses contrats, et seulement alors', async ({
	page,
	baseURL,
}) => {
	await ouvrirAnnuaire(page, baseURL);
	await expect(page.locator('#presta-1')).toContainText('Sous contrat (1)');
	await expect(page.locator('#presta-2')).not.toContainText('Sous contrat');
	//  La catégorie dit le métier, la même pour les deux.
	await expect(page.locator('#presta-1')).toContainText('Maintenance & dépannage');
	await expect(page.locator('#presta-2')).toContainText('Maintenance & dépannage');
});

test('le filtre sépare les prestataires sous contrat des autres', async ({ page, baseURL }) => {
	await ouvrirAnnuaire(page, baseURL);
	const filtre = page.getByRole('group', { name: 'Filtrer par contrat' });

	await filtre.getByRole('button', { name: /Sous contrat/ }).click();
	await expect(page.locator('#presta-1')).toBeVisible();
	await expect(page.locator('#presta-2')).toHaveCount(0);

	await filtre.getByRole('button', { name: 'Sans contrat' }).click();
	await expect(page.locator('#presta-2')).toBeVisible();
	await expect(page.locator('#presta-1')).toHaveCount(0);
});
