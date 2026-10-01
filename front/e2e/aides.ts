/*
 *  Aides partagées des tests de navigateur.
 */
import { test, type Page } from '@playwright/test';

/**
 * **Attendre que la page soit HYDRATÉE**, et pas seulement affichée.
 *
 * Les écrans sont rendus côté serveur : le formulaire de connexion existe dans
 * le HTML avant que le moindre gestionnaire ne soit posé. Un test qui remplit
 * ce formulaire trop tôt le SOUMET NATIVEMENT — la page se recharge, le
 * gestionnaire `preventDefault` n'a jamais existé, et le test échoue sur un
 * bandeau qui n'apparaîtra jamais. Même chose pour une image injectée avant que
 * la surveillance des images protégées ne soit en place : le test mesurerait
 * alors le moment de l'hydratation, pas la règle qu'il annonce.
 *
 * Le repère est posé par `$lib/imagesProtegees.ts`, depuis le `onMount` du
 * layout racine : quand il est là, le script du layout a tourné. Écrit ici une
 * fois — deux fichiers de test l'attendent, et un sélecteur recopié dans chacun
 * divergerait au premier renommage.
 */
export async function attendreHydratation(page: Page): Promise<void> {
	const debut = Date.now();
	try {
		await page.locator('html[data-images-surveillees="oui"]').waitFor({ timeout: 10000 });
	} finally {
		//  La durée est notée réussite OU échec (#1475) : un dépassement sous la
		//  charge d'un rejeu complet ne se diagnostique qu'en le comparant aux
		//  durées des tests verts du même rejeu. Bilan : `e2e/rapport-hydratation.ts`.
		test
			.info()
			.annotations.push({ type: TYPE_HYDRATATION, description: String(Date.now() - debut) });
	}
}

/** Le type de l'annotation que lit `rapport-hydratation.ts` — écrit une fois. */
export const TYPE_HYDRATATION = 'hydratation-ms';

/**
 * Un membre du conseil syndical — le compte simulé des écrans authentifiés.
 *
 * Le CS voit tout : un test qui le prend ne saute aucun onglet réservé.
 */
export const MEMBRE_CS = {
	id: 1,
	nom: 'Témoin',
	prenom: 'CS',
	email: 'temoin@exemple.test',
	statut: 'copropriétaire_résident',
	role: 'conseil_syndical',
	roles: ['conseil_syndical'],
	actif: true,
};

/**
 * **Rendre un écran authentifié avec l'API simulée.**
 *
 * Tout est derrière une connexion : un test qui chercherait l'écran sans compte
 * serait sauté, donc faux vert (`cible-tactile.spec.ts`). On rend le VRAI écran,
 * avec `MEMBRE_CS` pour `/api/auth/me`, un objet vide pour la configuration, et
 * une liste vide pour le reste — sauf ce que `reponses` rend pour un chemin.
 *
 * ⚠️ Le CHEMIN doit commencer par `/api/` : un motif `/api/` n'importe où
 * intercepte aussi le module source `/src/lib/api/…`, et la page tombe en 500.
 * Écrit ici une fois : trois tests le recopiaient, avec son piège.
 */
export async function simulerApi(
	page: Page,
	reponses: (chemin: string) => unknown = () => undefined,
): Promise<void> {
	await page.route(
		(url) => url.pathname.startsWith('/api/'),
		(route) => {
			const chemin = new URL(route.request().url()).pathname;
			let corps = reponses(chemin);
			if (corps === undefined) {
				if (chemin === '/api/auth/me') corps = MEMBRE_CS;
				else if (/config|pages|parametres|sante|epingles/.test(chemin)) corps = {};
				else corps = [];
			}
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify(corps),
			});
		},
	);
}
