/*
 *  **L'encart d'avertissement a UNE allure (#1455).**
 *
 *  Il était recopié dans sept écrans, chacun avec sa marge, son rayon et sa
 *  taille ; `lint:encart-avertissement` refuse désormais une copie. Ce test
 *  regarde l'autre moitié : que l'encart RENDU porte bien la charte — fond et
 *  filet d'avertissement, texte en `--color-warning-texte`, jamais l'ambre de
 *  `--color-warning` — dans sa forme resserrée, sous un champ.
 *
 *  L'écran est public (connexion) : aucune API à simuler. Le verrouillage des
 *  majuscules se déclare sur l'événement, comme le navigateur le fait.
 */
import { attendreHydratation, expect, test } from './aides';

//  Les jetons de `socle.css`, tels que le navigateur les calcule.
const FOND = 'rgb(253, 243, 224)'; //  --color-warning-fond
const FILET = 'rgb(223, 203, 165)'; // --color-warning-bordure
const TEXTE = 'rgb(123, 88, 21)'; //   --color-warning-texte

test('sous un champ, l’encart resserré porte la charte d’avertissement', async ({ page }) => {
	await page.goto('/auth/connexion');
	await attendreHydratation(page);
	const champ = page.locator('input[type="password"]').first();
	await champ.focus();
	await champ.dispatchEvent('keydown', { key: 'A', modifierCapsLock: true });

	const encart = page.locator('.encart-avertissement', { hasText: 'Verr. Maj.' });
	await expect(encart).toBeVisible();
	await expect(encart).toHaveClass(/compact/);
	await expect(encart).toHaveCSS('background-color', FOND);
	await expect(encart).toHaveCSS('border-top-color', FILET);
	await expect(encart).toHaveCSS('color', TEXTE);
	//  Toujours annoncé : il avertit d'une frappe en cours.
	await expect(encart).toHaveAttribute('role', 'alert');
});
