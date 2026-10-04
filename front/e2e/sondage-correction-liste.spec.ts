/*
 *  **Corriger un sondage depuis la liste montre ses réponses** (#1661).
 *
 *  Trouvé en typant le client de la Communauté : `GET /sondages` ne porte pas les
 *  options. La correction ouverte depuis la liste recevait donc cette ligne, et
 *  affichait deux champs vides à la place des libellés ; ce qu'on y tapait n'était
 *  pas envoyé (le serveur corrige une option par son `id`, que la ligne n'a pas).
 *  Depuis la fiche (`/sondages/[id]`), tout marchait — d'où un défaut que personne
 *  n'avait vu.
 *
 *  Le test ouvre la correction depuis la LISTE, API simulée : les champs portent
 *  les libellés réels, et l'enregistrement envoie les options avec leur `id`.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

const LIGNE = {
	id: 7,
	question: 'Peinture du hall ?',
	description: null,
	cloture_le: null,
	cloture_forcee: false,
	resultats_publics: true,
	//  Le compte simulé (`MEMBRE_CS`, id 1) en est l'auteur : le crayon est offert.
	auteur_id: 1,
	cree_le: '2026-10-01T10:00:00',
	perimetre_cible: ['résidence'],
	public_cible: ['résidents'],
	nb_votants: 0,
	cloture: false,
	archivee: false,
	assiste_ia: false,
};

//  La FICHE : la liste ci-dessus n'a pas `options`, celle-ci les porte.
const FICHE = {
	...LIGNE,
	options: [
		{ id: 31, libelle: 'Beige', ordre: 0, champ_libre: false },
		{ id: 32, libelle: 'Gris perle', ordre: 1, champ_libre: false },
	],
	mon_vote: null,
	commentaires: [],
	resultats_visibles: true,
};

test('la correction depuis la liste préremplit les réponses et les renvoie avec leur id', async ({
	page,
}) => {
	let envoye: { options?: { id: number; libelle: string }[] } | null = null;
	await simulerApi(page, (chemin) => (chemin === '/api/sondages' ? [LIGNE] : undefined));
	//  Enregistré APRÈS `simulerApi` : Playwright applique la route la plus récente.
	await page.route('**/api/sondages/7', (route) => {
		if (route.request().method() === 'PATCH') {
			envoye = route.request().postDataJSON();
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({ id: 7, question: LIGNE.question }),
			});
		}
		return route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify(FICHE),
		});
	});

	await page.goto('/sondages');
	await attendreHydratation(page);
	await page.getByRole('button', { name: 'Modifier ce sondage' }).click();

	const premiere = page.getByLabel('Libellé de la réponse 1');
	const seconde = page.getByLabel('Libellé de la réponse 2');
	await expect(premiere).toHaveValue('Beige');
	await expect(seconde).toHaveValue('Gris perle');

	await seconde.fill('Gris clair');
	await page.getByRole('button', { name: /Enregistrer|Mettre à jour|Corriger/ }).click();
	await expect.poll(() => envoye).not.toBeNull();
	expect(envoye!.options).toEqual([
		{ id: 31, libelle: 'Beige' },
		{ id: 32, libelle: 'Gris clair' },
	]);
});
