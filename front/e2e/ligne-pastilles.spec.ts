/*
 *  **Une affaire a la même dernière ligne sur sa carte et dans le fil.**
 *
 *  Arbitré à l'écran le 27/09/2026 : la ligne de la carte d'affaire fait la
 *  norme — catégorie, état, 🔹 périmètre, qui la lit, ⚡ urgence, marqueurs,
 *  #numéro, ✍️ auteur, ✨ IA — et le fil la rend à l'identique, sans 📌 (il a son
 *  bandeau « Épinglé »). Elles différaient sur neuf points.
 *
 *  `lint:pastilles` vérifie que les cartes passent par `PastillesAffaire` ; ce
 *  test-ci vérifie ce qu'on LIT : les deux écrans sont rendus avec la même
 *  affaire (API simulée, compte CS) et leurs lignes comparées.
 */
import { expect, test, type Page } from '@playwright/test';
import { simulerApi } from './aides';

const LIGNE = {
	numero: 'TK-109008',
	categorie: 'panne',
	statut: 'en_cours',
	priorite: 'haute',
	debut: null,
	perimetre_cible: ['bat:1'],
	public_cible: null,
	reserve_perimetre: false,
	confidentiel: false,
	epingle: true,
	assiste_ia: true,
};
const AUTEUR = 'Wend-Pouiré ROUAMBA';
const AFFAIRE = {
	...LIGNE,
	id: 7,
	titre: 'Porte du hall',
	description: 'Elle ne ferme plus',
	auteur_id: 2,
	auteur_nom: AUTEUR,
	cree_le: '2026-09-26T10:00:00',
	mis_a_jour_le: '2026-09-26T10:00:00',
	photos_urls: [],
	fichiers_urls: [],
};
const FLUX = {
	items: [
		{
			id: 'tk_7',
			type: 'ticket_ouvert',
			date: '2026-09-26T10:00:00',
			titre: 'Porte du hall',
			detail: 'Elle ne ferme plus',
			badges: ['#TK-109008', 'Panne', 'urgent'],
			icon: '🛠️',
			meta: { ticket_id: 7, perimetre_codes: ['bat:1'], auteur: AUTEUR, affaire: LIGNE },
		},
	],
	sante: {},
};

const simuler = (page: Page) =>
	simulerApi(page, (chemin) => {
		if (chemin === '/api/flux') return FLUX;
		if (chemin === '/api/tickets') return [AFFAIRE];
	});

/** Le texte d'une ligne, espaces normalisés. */
const texte = async (page: Page, selecteur: string) =>
	(await page.locator(selecteur).first().innerText()).replace(/\s+/g, ' ').trim();

test('le fil rend la ligne de la carte d’affaire, sans 📌', async ({ page }) => {
	await simuler(page);

	await page.goto('/tickets');
	const carte = await texte(page, '.carte-liste .ec-tags');
	//  Cas zéro : la ligne de référence porte bien ce qu'on compare.
	expect(carte, 'la carte d’affaire n’a pas rendu sa ligne').toContain('#TK-109008');
	expect(carte).toContain('⚡ Urgente');
	expect(carte).toContain(`✍️ ${AUTEUR}`);

	await page.goto('/tableau-de-bord');
	const fil = await texte(page, '.flux-badges');
	expect(fil).toBe(
		carte
			.replace(/📌 Épinglée ?/, '')
			.replace(/\s+/g, ' ')
			.trim(),
	);
});
