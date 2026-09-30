/*
 *  **La vignette des Destinataires dit ce que la pastille cochée dit** (#1434).
 *
 *  Signalé à l'écran le 28/09/2026 : Nouvelle affaire, catégorie **Panne** —
 *  pastille « Tous » cochée, vignette « Copropriétaires (occupants et
 *  bailleurs) » et « Pas les bailleurs (mandataires), ni les locataires ».
 *
 *  Une Panne a sa propre règle de lecture (`destinataires_par_defaut` au
 *  serveur) : tous les copropriétaires et les locataires du périmètre depuis le
 *  30/09/2026 (hors d'un bâtiment, TOUS la lisaient alors). Les
 *  pastilles la connaissaient ; le calcul de la vignette ne recevait pas la
 *  catégorie et retombait sur le défaut d'une affaire ordinaire. La règle pure
 *  était juste et éprouvée (`lint:lecture`) : c'est son APPEL qui oubliait un
 *  argument — seul un test de l'écran pouvait le voir.
 *
 *  L'autre sens est éprouvé aussi : une Étude & travaux est lue du conseil
 *  seul (29/09/2026), sa vignette le dit — sans quoi un test qui ne verrait
 *  jamais que « Tous » passerait sur une vignette figée.
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

//  Standard du 30/09/2026 (Carnet = Affaires = Kanban) : une Panne sans choix
//  se lit de tous les copropriétaires et des locataires de son périmètre — la
//  vignette le dit, comme les pastilles cochées (#1434 : elles divergeaient).
test('Nouvelle affaire, Panne : copropriétaires et locataires cochés, la vignette le dit', async ({
	page,
}) => {
	await nouvelleAffaire(page, /Ascenseur, chauffage, éclairage/);
	await expect(page.getByRole('radio', { name: /Panne/ })).toBeChecked();

	const s = section(page);
	await expect(s.locator('button.active', { hasText: /Copropriétaires occupants/ })).toHaveCount(1);
	await expect(s.locator('button.active', { hasText: /Copropriétaires bailleurs/ })).toHaveCount(1);
	await expect(s.locator('button.active', { hasText: /^\s*Locataires\s*$/ })).toHaveCount(1);
	await expect(s.locator('button.active')).toHaveCount(3);
	await expect(s.locator('.section-badge, .section-resume').first()).toHaveText(
		/Copropriétaires et locataires/,
	);
});

test('Nouvelle affaire, Étude & travaux : « Conseil syndical » est cochée (29/09/2026)', async ({
	page,
}) => {
	await nouvelleAffaire(page, /Diagnostic, sondage, devis/);
	const s = section(page);
	await expect(s.locator('button.active', { hasText: /Conseil syndical/ })).toHaveCount(1);
	await expect(s.locator('button.active')).toHaveCount(1);
	await expect(s.locator('.section-badge, .section-resume').first()).toHaveText(
		/Conseil syndical seul/,
	);
});

//  …et s'ouvre aux copropriétaires dès l'AG, où ils la votent (30/09/2026) : la
//  présélection suit l'ÉTAT choisi, pas seulement la catégorie.
test('Nouvelle affaire, Étude & travaux mise « À l’AG » : les copropriétaires sont cochés', async ({
	page,
}) => {
	await nouvelleAffaire(page, /Diagnostic, sondage, devis/);
	await page
		.getByRole('button', { name: /À l’AG/ })
		.first()
		.click();
	const s = section(page);
	await expect(s.locator('button.active', { hasText: /Copropriétaires occupants/ })).toHaveCount(1);
	await expect(s.locator('button.active', { hasText: /Copropriétaires bailleurs/ })).toHaveCount(1);
	await expect(s.locator('button.active')).toHaveCount(2);
	await expect(s.locator('.section-badge, .section-resume').first()).toHaveText(
		/Copropriétaires \(occupants et bailleurs\)/,
	);
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

//  Arbitré le 30/09/2026 : le conseil seul crée un Entretien, les
//  copropriétaires — occupants et bailleurs — le lisent (conseil seul avant).
test('Nouvelle affaire, Entretien : les copropriétaires sont cochés', async ({ page }) => {
	await nouvelleAffaire(page, /Visite ou maintenance d’un prestataire/);
	const s = section(page);
	await expect(s.locator('button.active', { hasText: /Copropriétaires occupants/ })).toHaveCount(1);
	await expect(s.locator('button.active', { hasText: /Copropriétaires bailleurs/ })).toHaveCount(1);
	await expect(s.locator('button.active')).toHaveCount(2);
	await expect(s.locator('.section-badge, .section-resume').first()).toHaveText(
		/Copropriétaires \(occupants et bailleurs\)/,
	);
});
