/**
 *  L'astérisque d'un champ obligatoire est COLLÉE à son libellé.
 *
 *  ## 🔴 Pourquoi ce test existe (22/09/2026, signalé à l'écran)
 *
 *  La règle avait été livrée la veille (#1121) et le code l'écrivait bien : rien
 *  ne sépare `{titre}` du composant. Pourtant l'écran affichait
 *  **« PÉRIMÈTRE * »**, « DESCRIPTION * », « SAISI POUR * ».
 *
 *  La cause n'était pas dans les appelants mais **à l'intérieur** du composant :
 *
 *      <span class="requis">
 *        <span aria-hidden="true">*</span>     ← ce saut de ligne EST un espace
 *
 *  Un retour à la ligne entre deux éléments est un nœud de texte blanc, que le
 *  navigateur rend comme une espace. Aucune relecture de code ne le montre —
 *  le code paraît juste, et il l'est au sens de Svelte.
 *
 *  ⚠️ C'est pour cela que ce contrôle est un test de NAVIGATEUR et non un
 *  linter : ce qui est faux ici n'est pas le texte du fichier, c'est ce que le
 *  navigateur en fait. Un contrôle statique aurait dit vert (`standards/04`
 *  §14 : observer la chose, pas son enregistrement).
 *
 *  ## Ce qu'il mesure
 *
 *  L'écran de connexion est **public** : son champ « Email » est obligatoire et
 *  porte l'astérisque. Le texte lu doit donc finir par `EMAIL*` — sans espace,
 *  et en capitales, les deux règles du même lot.
 */
import { expect, test } from '@playwright/test';

import { attendreHydratation } from './aides';

test.describe("L'astérisque des champs obligatoires", () => {
	test('est collée au libellé, sans espace', async ({ page }) => {
		await page.goto('/auth/connexion');
		await attendreHydratation(page);

		const label = page.locator('label[for="email"]');
		await expect(label).toBeVisible();

		//  `innerText` rend le texte TEL QU'AFFICHÉ — capitales comprises, et
		//  espaces tels que le navigateur les a composés. `textContent` rendrait
		//  la source, donc exactement ce que ce test doit refuser de croire.
		//
		//  ⚠️ Le texte de rechange « obligatoire » en est retiré : il est destiné
		//  aux lecteurs d'écran et n'occupe aucune place à l'œil. Le clone est
		//  posé dans le MÊME parent pour hériter des mêmes styles — mesuré hors
		//  contexte, il rendrait autre chose que ce qui s'affiche.
		const affiche = (
			await label.evaluate((n) => {
				const clone = n.cloneNode(true) as HTMLElement;
				clone.querySelectorAll('.sr-only').forEach((e) => e.remove());
				n.after(clone);
				const texte = clone.innerText;
				clone.remove();
				return texte;
			})
		).trim();
		expect(affiche, "le libellé ne porte pas d'astérisque").toContain('*');
		expect(
			affiche,
			`« ${affiche} » — une espace s'est glissée avant l'astérisque (un saut de ligne dans le balisage suffit)`,
		).not.toMatch(/\s\*/);
	});

	test('le mot « obligatoire » est annoncé, la couleur ne suffisant pas', async ({ page }) => {
		await page.goto('/auth/connexion');
		await attendreHydratation(page);

		//  La couleur ne se lit pas au lecteur d'écran, et le rouge seul n'est
		//  jamais une information (`standards/11` §2). Le mot est dans l'arbre
		//  d'accessibilité, hors de l'œil.
		const label = page.locator('label[for="email"]');
		await expect(label.locator('.sr-only')).toHaveText('obligatoire');
	});

	test('elle est ROUGE tant que le champ est vide, et ne l’est plus ensuite', async ({ page }) => {
		await page.goto('/auth/connexion');
		await attendreHydratation(page);

		const etoile = page.locator('label[for="email"] span[class*="requis"]').first();
		const couleur = () => etoile.evaluate((n) => getComputedStyle(n).color);

		const vide = await couleur();
		await page.fill('#email', 'quelqu-un@exemple.fr');
		const rempli = await couleur();

		//  🔴 On ne compare pas à une valeur écrite ici : la charte peut changer
		//  de rouge. Ce qui compte est que l'état du champ CHANGE la couleur —
		//  c'est toute la règle, et elle se mesure sans connaître la palette.
		expect(rempli, 'la couleur ne change pas quand le champ se remplit').not.toBe(vide);
	});
});
