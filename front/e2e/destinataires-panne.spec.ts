/*
 *  **La vignette des Destinataires dit ce que la pastille cochée dit** (#1434).
 *
 *  Signalé à l'écran le 28/09/2026 : Nouvelle affaire, catégorie **Panne** —
 *  pastille « Tous » cochée, vignette « Copropriétaires (occupants et
 *  bailleurs) » et « Pas les bailleurs (mandataires), ni les locataires ».
 *
 *  Une Panne a sa propre règle de lecture (`destinataires_par_defaut` au
 *  serveur) : hors d'un bâtiment, TOUS la lisent, locataires compris. Les
 *  pastilles la connaissaient ; le calcul de la vignette ne recevait pas la
 *  catégorie et retombait sur le défaut d'une affaire ordinaire. La règle pure
 *  était juste et éprouvée (`lint:lecture`) : c'est son APPEL qui oubliait un
 *  argument — seul un test de l'écran pouvait le voir.
 *
 *  L'autre sens est éprouvé aussi : une Étude & travaux reste lue par les
 *  copropriétaires seuls, sa vignette le dit — sans quoi un test qui ne verrait
 *  jamais « Copropriétaires » passerait sur une vignette figée à « Tous ».
 *
 *  Depuis #1436 (28/09/2026), CHAQUE catégorie a son défaut : une Nuisance
 *  présélectionne « Résident concerné », un Entretien « Conseil syndical ». La
 *  table est éprouvée contre le serveur (`lint:lecture`) ; ici, que l'ÉCRAN la
 *  suit — pastille cochée et vignette d'accord — et qu'on la quitte d'un clic.
 */
import { expect, test, type Page } from '@playwright/test';
import { attendreHydratation, simulerApi } from './aides';

/** La section Destinataires du formulaire. */
const section = (page: Page) =>
	page.locator('section.section-formulaire', {
		has: page.locator('.section-titre-texte', { hasText: 'Destinataires' }),
	});

async function nouvelleAffaire(page: Page, description: RegExp) {
	await simulerApi(page);
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.getByRole('button', { name: /Nouvelle affaire/ }).click();
	//  Le bouton radio est masqué sous sa vignette : on clique ce qu'on voit.
	await page.getByText(description).first().click();
}

test('Nouvelle affaire, Panne : la vignette dit « Tous », comme la pastille cochée', async ({
	page,
}) => {
	await nouvelleAffaire(page, /Ascenseur, chauffage, éclairage/);
	await expect(page.getByRole('radio', { name: /Panne/ })).toBeChecked();

	const s = section(page);
	await expect(s.locator('button.active', { hasText: /^\s*Tous\s*$/ })).toHaveCount(1);
	await expect(s.locator('.section-badge, .section-resume').first()).toHaveText(/Tous/);
	await expect(s.locator('.section-badge, .section-resume').first()).not.toHaveText(
		/Copropriétaires/,
	);
});

test('Nouvelle affaire, Étude & travaux : la vignette dit « Copropriétaires », comme les pastilles', async ({
	page,
}) => {
	await nouvelleAffaire(page, /Diagnostic, sondage, devis/);
	const s = section(page);
	await expect(s.locator('button.active', { hasText: /^\s*Tous\s*$/ })).toHaveCount(0);
	await expect(s.locator('.section-badge, .section-resume').first()).toHaveText(/Copropriétaires/);
});

test('Nouvelle affaire, Nuisance : « Résident concerné » est cochée, et la vignette le dit (#1436)', async ({
	page,
}) => {
	await nouvelleAffaire(page, /Bruit, odeurs, stationnement/);
	const s = section(page);
	const concerne = s.locator('button', { hasText: /Résident concerné/ });
	await expect(concerne).toHaveClass(/active/);
	await expect(s.locator('button.active')).toHaveCount(1);
	await expect(s.locator('.section-badge, .section-resume').first()).toHaveText(
		/Résident concerné/,
	);

	//  On le quitte en choisissant un autre destinataire ; on y revient d'un clic.
	await s.locator('button', { hasText: /^\s*Locataires\s*$/ }).click();
	await expect(concerne).not.toHaveClass(/active/);
	await expect(s.locator('.section-badge, .section-resume').first()).toHaveText(/Locataires/);
	await concerne.click();
	await expect(concerne).toHaveClass(/active/);
	await expect(s.locator('button.active')).toHaveCount(1);
});

test('Nouvelle affaire, Entretien : « Conseil syndical » est cochée (#1436)', async ({ page }) => {
	await nouvelleAffaire(page, /Visite ou maintenance d’un prestataire/);
	const s = section(page);
	await expect(s.locator('button.active', { hasText: /Conseil syndical/ })).toHaveCount(1);
	await expect(s.locator('button.active')).toHaveCount(1);
	await expect(s.locator('.section-badge, .section-resume').first()).toHaveText(
		/Conseil syndical seul/,
	);
});
