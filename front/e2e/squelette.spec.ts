/*
 *  **Le squelette du site, vu par un navigateur.**
 *
 *  Ce qui est vérifié ici ne l'était par AUCUN contrôle. `lint:evitement` lit la
 *  source et prouve que le lien est écrit ; il ne peut pas dire lequel des
 *  éléments prend le focus au premier Tab. C'est la distinction du socle —
 *  vérifier le COMPORTEMENT, jamais l'artefact (`standards/04`).
 *
 *  ## 🔴 Ce que ce fichier peut atteindre
 *
 *  Sans session, seuls les écrans publics existent : `/auth/*`, les mentions
 *  légales, la politique de confidentialité. **Le lien d'évitement n'y est pas**,
 *  et c'est voulu : son ancre `#contenu` est le `<main>` du squelette `(app)`,
 *  qui n'existe pas ici — un lien d'évitement pointant vers une ancre absente
 *  serait pire qu'aucun lien (`routes/+layout.svelte`).
 *
 *  Ce qui SE vérifie ici, en revanche, est la moitié qui a réellement cassé :
 *  #802 avait pour défaut que **les bandeaux flottants volaient le premier Tab**.
 *  Cela se constate sur n'importe quelle page, connexion comprise — ce sont les
 *  mêmes `Toast` et `MajDisponible`, montés par le layout racine.
 *
 *  Couvrir le lien lui-même demande une session : voir `e2e/README.md`.
 */
import { test, expect } from '@playwright/test';

test.describe('Squelette et accessibilité au clavier', () => {
	test('la racine mène à la page de connexion', async ({ page }) => {
		await page.goto('/');
		await expect(page).toHaveURL(/[/]auth[/]connexion/);
	});

	test('le premier Tab entre dans la PAGE, jamais dans un bandeau flottant', async ({ page }) => {
		await page.goto('/auth/connexion');
		await page.keyboard.press('Tab');

		//  🔴 Le défaut de #802 : `Toast` et `MajDisponible` sont en `position:
		//  fixed`, donc leur place à l'écran ne dit rien de leur place dans le DOM
		//  — et c'est le DOM qui décide de l'ordre du clavier. Montés AVANT le
		//  contenu, ils captaient le premier Tab, et seulement quand une mise à
		//  jour était disponible : le défaut intermittent qu'on ne reproduit
		//  jamais au moment où on le cherche.
		const cible = page.locator(':focus');
		await expect(cible).toBeVisible();
		await expect(cible).toHaveAttribute('id', 'email');
	});

	test('la page déclare sa langue', async ({ page }) => {
		await page.goto('/auth/connexion');
		await expect(page.locator('html')).toHaveAttribute('lang', 'fr');
	});

	test('un seul <h1> par page', async ({ page }) => {
		await page.goto('/auth/connexion');
		//  Un second `<h1>` casse la structure annoncée par un lecteur d'écran, et
		//  aucun linter du projet ne compte les titres à l'exécution.
		await expect(page.locator('h1')).toHaveCount(1);
	});

	//  🔴 La responsivité est une exigence permanente (`standards/11` §10), et le
	//  débordement horizontal est le défaut qu'on ne voit JAMAIS sur un écran
	//  large. Mesuré, pas supposé — et sur les deux profils, bureau et mobile.
	for (const chemin of ['/auth/connexion', '/mentions-legales', '/politique-de-confidentialite']) {
		test(`le corps ne défile pas horizontalement — ${chemin}`, async ({ page }) => {
			await page.goto(chemin);
			const deborde = await page.evaluate(
				() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
			);
			expect(deborde).toBe(false);
		});
	}

	test('aucune erreur de SCRIPT au chargement', async ({ page }) => {
		const erreurs: string[] = [];
		page.on('pageerror', (e) => erreurs.push(String(e)));
		page.on('console', (m) => {
			if (m.type() !== 'error') return;
			//  ⚠️ Les échecs de CHARGEMENT DE RESSOURCE sont écartés, et il faut le
			//  dire : `vite dev` proxifie `/api` vers `localhost:8000`, que ces
			//  tests ne démarrent pas. Sans ce filtre, le test échouerait pour une
			//  raison qui n'a rien à voir avec la page — et un test qui échoue
			//  pour de mauvaises raisons finit désarmé.
			//
			//  🔴 Ce qui reste couvert est ce qui compte : une exception JavaScript
			//  ou un `console.error` écrit par l'application.
			if (/Failed to load resource/i.test(m.text())) return;
			erreurs.push(m.text());
		});
		await page.goto('/auth/connexion');
		await page.waitForLoadState('networkidle');
		expect(erreurs).toEqual([]);
	});
});
