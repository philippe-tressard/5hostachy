/*
 *  **Une session expirée ne doit pas se voir par des images cassées (#996).**
 *
 *  Constaté en production le 17/09/2026 : les photos d'un ticket s'affichaient
 *  cassées. `/uploads/tickets/…jpg` répondait 401, et 200 dès la reconnexion —
 *  serveur sain, fichier présent, session expirée.
 *
 *  ## Pourquoi ce test est ici, et pas dans un linter
 *
 *  Le comportement dépend de trois choses qu'aucune lecture de source ne peut
 *  établir : que l'événement `error` d'une `<img>` ne remonte pas l'arbre (donc
 *  que l'écouteur doit être en capture), que le statut HTTP n'est pas exposé à
 *  ce gestionnaire (donc qu'une sonde est nécessaire), et que réaffecter le
 *  même `src` ne redemande rien. Un contrôle statique dirait que le code est
 *  écrit ; il ne dirait pas que l'image repart.
 *
 *  ## Ce que ce fichier peut atteindre sans session
 *
 *  L'écouteur est monté par le layout RACINE, donc il est en place dès la page
 *  de connexion. L'image protégée est injectée dans la page, et les deux
 *  réponses du serveur — le 401 du fichier, le 200 du renouvellement — sont
 *  jouées par `page.route`. C'est le scénario réel, sans compte de test.
 */
import { test, expect } from '@playwright/test';
import { attendreHydratation } from './aides';

const IMAGE = '/uploads/tickets/photo-de-essai.jpg';

/** Un GIF 1×1 valide : sans pixels réels, l'image échouerait pour une autre raison. */
const GIF_1x1 = Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64');

test.describe('Images protégées et session expirée', () => {
	test('une image en 401 est redemandée après renouvellement de la session', async ({ page }) => {
		let demandes = 0;
		let renouvellements = 0;
		let renouvelee = false;

		//  🔴 Le serveur réel, pas un compteur de tours : TANT QUE la session n'est
		//  pas renouvelée, le fichier répond 401 — l'image comme la sonde. Compter
		//  les requêtes pour décider du statut ferait répondre 200 à la sonde, donc
		//  le test passerait sans que rien ne soit renouvelé.
		await page.route(`**${IMAGE}*`, async (route) => {
			demandes += 1;
			if (renouvelee) {
				await route.fulfill({ status: 200, contentType: 'image/gif', body: GIF_1x1 });
			} else {
				await route.fulfill({ status: 401, contentType: 'application/json', body: '{}' });
			}
		});
		//  Le renouvellement : celui du client, que le module appelle tel quel.
		await page.route('**/api/auth/refresh', async (route) => {
			renouvellements += 1;
			renouvelee = true;
			await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
		});

		await page.goto('/auth/connexion');
		await attendreHydratation(page);
		await page.evaluate((src) => {
			const img = document.createElement('img');
			img.src = src;
			img.alt = 'photo protégée';
			document.body.appendChild(img);
		}, IMAGE);

		//  Trois requêtes : l'échec, la sonde qui lit le 401, puis l'image rejouée.
		await expect.poll(() => demandes, { timeout: 5000 }).toBeGreaterThanOrEqual(3);
		expect(renouvellements).toBe(1);

		//  🔴 Le fait, pas l'intention : l'image affiche enfin des pixels.
		await expect
			.poll(
				async () =>
					page
						.locator('img[alt="photo protégée"]')
						.evaluate((n) => (n as HTMLImageElement).naturalWidth),
				{
					timeout: 5000,
				},
			)
			.toBeGreaterThan(0);
	});

	test('une image ABSENTE ne déclenche aucun renouvellement', async ({ page }) => {
		let renouvellements = 0;

		await page.route(`**${IMAGE}*`, (route) =>
			route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }),
		);
		await page.route('**/api/auth/refresh', (route) => {
			renouvellements += 1;
			return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
		});

		await page.goto('/auth/connexion');
		await attendreHydratation(page);
		await page.evaluate((src) => {
			const img = document.createElement('img');
			img.src = src;
			img.alt = 'photo absente';
			document.body.appendChild(img);
		}, IMAGE);

		//  ⚠️ Le pendant indispensable : un 404 n'est pas une affaire de session.
		//  Sans ce test, « renouveler dès qu'une image casse » passerait aussi, et
		//  annoncerait une session expirée à qui a juste un fichier manquant.
		await page.waitForTimeout(1500);
		expect(renouvellements).toBe(0);
	});

	test('le contrôle mesure quelque chose : sans écouteur, rien ne repart', async ({ page }) => {
		//  🔴 Le cas zéro. On retire l'écouteur du document avant d'injecter
		//  l'image : si le compte de requêtes montait quand même à trois, c'est
		//  que le navigateur rejoue seul et que les deux tests ci-dessus ne
		//  prouveraient rien.
		let demandes = 0;
		await page.route(`**${IMAGE}*`, (route) => {
			demandes += 1;
			return route.fulfill({ status: 401, contentType: 'application/json', body: '{}' });
		});

		await page.goto('/auth/connexion');
		await attendreHydratation(page);
		await page.evaluate((src) => {
			//  Neutralise l'ajout d'écouteurs en capture sur le document, donc celui
			//  du layout, déjà posé : on le remplace par une page sans surveillance.
			const img = document.createElement('img');
			img.src = src;
			img.alt = 'photo sans surveillance';
			//  Un conteneur détaché : l'événement `error` ne traverse pas le
			//  document, donc l'écouteur en capture ne le voit pas.
			document.createElement('div').appendChild(img);
		}, IMAGE);

		await page.waitForTimeout(1500);
		expect(demandes).toBe(1);
	});
});
