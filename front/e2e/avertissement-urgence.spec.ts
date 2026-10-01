/*
 *  **L'avertissement « Affaires urgentes », replié, tient une ligne serrée.**
 *
 *  Signalé à l'écran le 27/09/2026 : *« prend trop de place, divise par 2 ou 3
 *  l'espace en hauteur »*. Replié, le bandeau faisait ~70 px avec sa marge —
 *  plus que la première carte d'affaire qu'il précède.
 *
 *  Les deux sens sont tenus, comme pour la section pliée (`cible-tactile`) :
 *  compact à la souris, mais 44 px au doigt — sans quoi le texte juridique ne
 *  s'ouvrirait plus au pouce, et rien ne le dirait (`standards/11` §10).
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';

/** Hauteur occupée par le bandeau replié, marge basse comprise. */
async function encombrement(page: Page): Promise<number> {
	await simulerApi(page);
	await page.goto('/tickets');
	const bandeau = page.locator('.urgence-disclaimer');
	await bandeau.waitFor();
	return bandeau.evaluate((el) => {
		const marge = parseFloat(getComputedStyle(el).marginBottom);
		return el.getBoundingClientRect().height + marge;
	});
}

test('à la souris, le bandeau replié occupe moitié moins qu’avant', async ({ page }, info) => {
	test.skip(info.project.name !== 'bureau', 'la densité se mesure au pointeur fin');
	//  ~70 px avant le 27/09/2026 ; la demande était de diviser par 2 ou 3.
	expect(await encombrement(page), 'le bandeau replié a regrossi').toBeLessThanOrEqual(35);
});

test('au doigt, le bandeau replié reste une cible tactile', async ({ page }, info) => {
	test.skip(info.project.name !== 'mobile', 'la règle ne vise que `pointer: coarse`');
	await simulerApi(page);
	await page.goto('/tickets');
	const boite = await page.locator('.urgence-disclaimer-toggle').boundingBox();
	expect(boite, 'le bandeau n’a pas été rendu').not.toBeNull();
	expect(boite!.height, 'hauteur de la cible tactile').toBeGreaterThanOrEqual(44);
});
