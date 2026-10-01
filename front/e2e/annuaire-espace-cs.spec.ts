/*
 *  **L'annuaire de l'espace CS — conseil syndical et syndic.**
 *
 *  Extrait de `espace-cs/+page.svelte` le 29/09/2026 (#779, modularité) :
 *  `AnnuaireConseil`, `AnnuaireSyndic`, et les rapprochements par le nom dans
 *  `$lib/annuaire-rapprochement`. Un découpage ne change pas un comportement —
 *  ce test le vérifie sur le VRAI écran, API simulée :
 *
 *  • les deux sections s'amorcent seules et rendent leurs membres, avec les
 *    pastilles de rôle HABILLÉES (leur style a changé de fichier : une pastille
 *    nue ne lèverait rien, v2.67.11) ;
 *  • un NOM saisi lie le membre à un inscrit et le localise par le registre
 *    importé, et c'est ce qui PART au serveur ;
 *  • le syndic refuse un membre sans téléphone, sans rien envoyer.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const CS = {
	ag_annee: 2025,
	ag_date: '2025-06-12',
	whatsapp_url: '',
	membres: [
		{
			genre: 'Mme',
			prenom: 'Anne',
			nom: 'Durand',
			batiment_nom: '2',
			etage: 3,
			est_president: true,
		},
	],
};
const SYNDIC = {
	nom_syndic: 'Cabinet Exemple',
	nom_syndic_source: 'saisie',
	membres: [
		{
			genre: 'M.',
			prenom: 'Paul',
			nom: 'Martin',
			fonction: 'Gestionnaire',
			telephone: '0102030405',
			est_principal: true,
		},
	],
};
const INSCRITS = [
	{ id: 42, prenom: 'Luc', nom: 'Bernard', email: 'l@b.fr', telephone: null, batiment_id: 4 },
];
const LOTS = [
	{ id: 9, numero: '41', type: 'appartement', etage: 1, batiment_id: 4, batiment_nom: 'Bât. 4' },
];
const IMPORTS = [
	{ nom_coproprietaire: 'BERNARD Luc', type_raw: 'AP', etage_raw: '1ER', lot_id: 9 },
];

type Envoi = { chemin: string; corps: any };

async function ouvrir(page: Page): Promise<Envoi[]> {
	const envois: Envoi[] = [];
	page.on('request', (r) => {
		const chemin = new URL(r.url()).pathname;
		if (r.method() === 'PUT' && chemin.startsWith('/api/'))
			envois.push({ chemin, corps: r.postDataJSON() });
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/admin/annuaire/cs') return CS;
		if (chemin === '/api/admin/annuaire/syndic') return SYNDIC;
		if (chemin === '/api/admin/utilisateurs') return INSCRITS;
		if (chemin === '/api/lots/admin/tous') return LOTS;
		if (chemin === '/api/lots/admin/imports') return IMPORTS;
		if (chemin === '/api/auth/batiments') return [{ id: 4, numero: '4' }];
	});
	await page.goto('/espace-cs/annuaire');
	await attendreHydratation(page);
	return envois;
}

const section = (page: Page, titre: string) =>
	page.locator('section.annuaire-section', {
		has: page.getByRole('heading', { name: titre, exact: true }),
	});

test('les deux sections rendent leurs membres, pastilles de rôle habillées', async ({ page }) => {
	await ouvrir(page);
	const conseil = section(page, 'Conseil Syndical');
	await expect(conseil).toContainText('AG 2025');
	await expect(conseil).toContainText('DURAND');
	const president = conseil.locator('.summary-role-badge-president');
	await expect(president).toHaveText(/Président/);
	//  Habillée : fond de la teinte d'avertissement, pas le transparent d'une classe nue.
	await expect(president).toHaveCSS('background-color', 'rgb(253, 243, 224)');

	const syndic = section(page, 'Syndic');
	await expect(syndic).toContainText('MARTIN');
	await expect(syndic.locator('.summary-role-badge-principal')).toHaveText(
		/Interlocuteur principal/,
	);
	await expect(syndic.locator('.summary-fonction')).toHaveText('Gestionnaire');
});

test('un nom saisi lie l’inscrit, localise le membre, et c’est ce qui part', async ({ page }) => {
	const envois = await ouvrir(page);
	const conseil = section(page, 'Conseil Syndical');
	await conseil.getByRole('button', { name: /Nouveau membre CS/ }).click();
	const nom = conseil.getByPlaceholder('NOM', { exact: true });
	await nom.fill('Bernard');
	await nom.dispatchEvent('input');
	await expect(conseil.locator('.localisation-info')).toContainText('1');
	await expect(conseil.getByText(/Inscrit lié/).first()).toBeVisible();

	await conseil.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	await expect.poll(() => envois.length).toBe(1);
	expect(envois[0].chemin).toBe('/api/admin/annuaire/cs');
	const ajoute = envois[0].corps.membres.find((m: any) => m.nom === 'Bernard');
	expect(ajoute).toMatchObject({ user_id: 42, batiment_id: 4, batiment_nom: '4', etage: 1 });
});

test('le syndic refuse un membre sans téléphone, et n’envoie rien', async ({ page }) => {
	const envois = await ouvrir(page);
	const syndic = section(page, 'Syndic');
	await syndic.getByRole('button', { name: /Nouveau membre Syndic/ }).click();
	await syndic.getByPlaceholder('NOM', { exact: true }).fill('Petit');
	await syndic.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	await expect(page.getByText('Au moins un téléphone requis')).toBeVisible();
	expect(envois).toHaveLength(0);
});
