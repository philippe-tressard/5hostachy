/*
 *  **La pastille de filtre RETENUE dit combien d'affaires elle donne** (10/10/2026).
 *
 *  Maquette B (un nombre dans chaque pastille) puis maquette J le même jour,
 *  arbitrée à l'écran : dix vignettes chargeaient la rangée, seule la pastille
 *  retenue garde la sienne. Ce qu'on LIT :
 *
 *  1. la pastille retenue porte le compte de son choix, LES AUTRES FILTRES
 *     RETENUS — et une archivée ne compte jamais ; les autres n'en portent pas ;
 *  2. ce compte est exactement le nombre de cartes de la liste : un compteur
 *     qui ment n'est pas rattrapé par un autre contrôle ;
 *  3. la vignette est la MÊME que celle des Archives, inversée sur l'aplat
 *     (Bleu Seine sur blanc au lieu de blanc sur Bleu Seine).
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const affaire = (id: number, natures: string[], statut: string, archivee = false) => ({
	id,
	numero: `TK-1090${id}`,
	titre: `Affaire ${id}`,
	description: 'Témoin',
	categorie: natures.includes('actualite') ? 'actualite' : 'panne',
	natures,
	statut,
	archivee,
	priorite: 'normale',
	perimetre_cible: [],
	auteur_id: 2,
	auteur_nom: 'Jean-Hervé KERBRAT',
	cree_le: '2026-10-01T10:00:00',
	mis_a_jour_le: '2026-10-01T10:00:00',
	photos_urls: [],
	fichiers_urls: [],
});

const AFFAIRES = [
	affaire(1, ['actualite'], 'ouvert'),
	affaire(2, ['actualite'], 'en_cours'),
	affaire(3, ['activite'], 'ouvert'),
	affaire(4, ['activite'], 'en_cours'),
	affaire(5, ['calendrier'], 'ouvert'),
	//  Archivée : hors de la liste, donc hors de TOUS les comptes.
	affaire(6, ['activite'], 'ouvert', true),
];

async function ouvrir(page: Page) {
	await simulerApi(page, (chemin) => (chemin === '/api/tickets' ? AFFAIRES : undefined));
	await page.goto('/tickets');
	await attendreHydratation(page);
}

const rangee = (page: Page, libelle: string) =>
	page.getByRole('group', { name: libelle, exact: true });
const pastille = (page: Page, libelle: string, nom: RegExp) =>
	rangee(page, libelle).getByRole('button', { name: nom });
const compte = (page: Page, libelle: string, nom: RegExp) =>
	pastille(page, libelle, nom).locator('.compte');

test('seule la pastille retenue compte son choix, les autres filtres retenus', async ({ page }) => {
	await ouvrir(page);

	await expect(compte(page, 'Nature', /^Tous/)).toHaveText('5');
	await expect(compte(page, 'Suivi', /^Tous/)).toHaveText('5');
	for (const nom of [/Actualité/, /Calendrier/, /Affaire/])
		await expect(compte(page, 'Nature', nom)).toHaveCount(0);
	for (const nom of [/Ouvert/, /En cours/]) await expect(compte(page, 'Suivi', nom)).toHaveCount(0);

	//  Retenir une NATURE : sa pastille prend le compte, « Tous » le perd, et le
	//  Suivi retenu recompte avec elle.
	await pastille(page, 'Nature', /Actualité/).click();
	await expect(compte(page, 'Nature', /Actualité/)).toHaveText('2');
	await expect(compte(page, 'Nature', /^Tous/)).toHaveCount(0);
	await expect(compte(page, 'Suivi', /^Tous/)).toHaveText('2');
	await expect(page.locator('[id^="ticket-"]')).toHaveCount(2);

	//  Les deux filtres : chaque pastille retenue annonce la liste.
	await pastille(page, 'Suivi', /Ouvert/).click();
	await expect(compte(page, 'Suivi', /Ouvert/)).toHaveText('1');
	await expect(compte(page, 'Nature', /Actualité/)).toHaveText('1');
	await expect(page.locator('[id^="ticket-"]')).toHaveCount(1);
	await expect(page.locator('.filters .compte')).toHaveCount(2);
});

test('la vignette est celle des Archives, inversée sur la pastille retenue', async ({ page }) => {
	await ouvrir(page);
	const retenue = await compte(page, 'Nature', /^Tous/).evaluate((e) => {
		const s = getComputedStyle(e);
		return { fond: s.backgroundColor, texte: s.color, chiffres: s.fontVariantNumeric };
	});
	expect(retenue.chiffres, 'des chiffres à chasse fixe').toBe('tabular-nums');

	//  Survolée, la pastille retenue garde son texte clair : le survol, plus
	//  spécifique, le rendait sombre sur l'aplat tant que la souris y restait.
	const tous = pastille(page, 'Nature', /^Tous/);
	await tous.hover();
	await expect.poll(() => tous.evaluate((e) => getComputedStyle(e).color)).toBe(retenue.fond);

	//  Le même objet que le bandeau d'Archives — style ET balisage, couleurs
	//  inversées : le fond des Archives est le texte de la pastille retenue.
	await page
		.getByRole('link', { name: /Archives/ })
		.first()
		.click();
	await attendreHydratation(page);
	const archives = page.locator('.compte').first();
	await expect(archives).toHaveText('1');
	const libre = await archives.evaluate((e) => {
		const s = getComputedStyle(e);
		return { fond: s.backgroundColor, texte: s.color };
	});
	expect(retenue.fond, 'retenue : le fond prend le texte des Archives').toBe(libre.texte);
	expect(retenue.texte, 'retenue : le texte prend le fond des Archives').toBe(libre.fond);
});
