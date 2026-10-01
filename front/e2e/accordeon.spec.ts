/*
 *  **Déplier un bloc replie les autres — partout (30/09/2026).**
 *
 *  Demandé : « quand on déplie une section ça replie les autres (c'est une
 *  bonne pratique qui doit s'appliquer sans exception) », arbitré « partout,
 *  formulaires compris ». `scripts/check-accordeon.mjs` éprouve l'état et les
 *  groupes sans navigateur ; ce test éprouve ce que seul un écran montre :
 *
 *  1. les sections d'un VRAI formulaire (nouvelle affaire, API simulée) —
 *     et l'exception arbitrée : une section dont la valeur a changé reste
 *     ouverte ;
 *  2. les `<details>` natifs, que le layout coordonne par un seul écouteur —
 *     sans replier celui qui contient le bloc qu'on ouvre.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

test('Nouvelle affaire : déplier une section replie celle qu’on avait dépliée', async ({
	page,
}) => {
	await simulerApi(page);
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: /Nouvelle affaire/ }).click();

	//  Une section se lit PLIÉE à sa ligne de résumé (`button.section-pliee`) :
	//  toutes en ont une, alors que le bouton « Replier » manque aux sections
	//  dont le titre est un `<label for>`.
	const pliees = page.locator('button.section-pliee');
	await expect(pliees.nth(1), 'il faut deux sections pliables').toBeVisible();
	const titre = async (n: number) =>
		(await pliees.nth(n).locator('.section-titre-texte').textContent())!.trim();
	const premiere = await titre(0);
	const seconde = await titre(1);
	const ligne = (t: string) =>
		page.locator('button.section-pliee', {
			has: page.locator('.section-titre-texte', { hasText: new RegExp(`^${t}`) }),
		});

	await ligne(premiere).click();
	await expect(ligne(premiere), `${premiere} ne s'est pas dépliée`).toHaveCount(0);

	//  La seconde s'ouvre, la première se replie — elle n'a pas changé de valeur.
	await ligne(seconde).click();
	await expect(ligne(seconde), `${seconde} ne s'est pas dépliée`).toHaveCount(0);
	await expect(ligne(premiere), `${premiere} aurait dû se replier`).toHaveCount(1);
});

test('Les <details> natifs : un seul ouvert, sauf celui qui contient', async ({ page }) => {
	await simulerApi(page);
	await page.goto('/tickets');
	await attendreHydratation(page);
	//  Des `<details>` témoins, posés APRÈS l'hydratation : c'est l'écouteur du
	//  layout qu'on éprouve, pas un composant.
	await page.evaluate(() => {
		const zone = document.createElement('div');
		zone.innerHTML = `
			<details id="a"><summary>A</summary>contenu A</details>
			<details id="b"><summary>B</summary>contenu B
				<details id="b1"><summary>B1</summary>contenu B1</details>
			</details>`;
		document.body.appendChild(zone);
	});
	const ouvert = (id: string) =>
		page.locator(`#${id}`).evaluate((d) => (d as HTMLDetailsElement).open);

	await page.locator('#a > summary').click();
	await expect.poll(() => ouvert('a')).toBe(true);

	await page.locator('#b > summary').click();
	await expect.poll(() => ouvert('b')).toBe(true);
	await expect.poll(() => ouvert('a'), 'A aurait dû se replier').toBe(false);

	//  Ouvrir un bloc DANS B ne replie pas B.
	await page.locator('#b1 > summary').click();
	await expect.poll(() => ouvert('b1')).toBe(true);
	await expect.poll(() => ouvert('b'), 'B contient B1 : il reste ouvert').toBe(true);
});
