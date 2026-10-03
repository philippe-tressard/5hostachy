/*
 *  **Télémétrie : le filtre « avec / sans le gestionnaire du site » et la section
 *  « Indicateurs et fréquentation »** (03/10/2026, signalé à l'écran : « dans la
 *  vue Mois, il y a d'autres utilisateurs et ce filtre n'apparaît pas »).
 *
 *  Le filtre n'est proposé que s'il écarterait quelque chose ; quand il l'est, il
 *  se tient sur la MÊME ligne que les vues. Et quand son absence tient à une
 *  configuration — aucun gestionnaire désigné — l'écran le dit, au lieu de laisser
 *  l'administrateur chercher un filtre qui n'existait pas.
 */
import type { Page } from '@playwright/test';
import {
	attendreHydratation,
	expect,
	MEMBRE_CS,
	simulerApi,
	TABLEAU_TELEMETRIE_VIDE,
	test,
} from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

async function ouvrir(
	page: Page,
	filtre: { propose: boolean; gestionnaire_designe: boolean },
	kpi: Record<string, unknown> = {},
) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/telemetry/dashboard')
			return {
				...TABLEAU_TELEMETRIE_VIDE,
				kpi: { ...TABLEAU_TELEMETRIE_VIDE.kpi, ...kpi },
				filtre_gestionnaire: { ...filtre, applique: 'avec', non_distingue_jusqu_au: null },
			};
	});
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);
}

const SANS = (page: Page) => page.getByRole('checkbox', { name: 'Sans le gestionnaire du site' });

test('proposé : une case, sur la ligne des vues', async ({ page }) => {
	await ouvrir(page, { propose: true, gestionnaire_designe: true });
	await expect(SANS(page)).toBeVisible();
	await expect(SANS(page)).not.toBeChecked();

	//  La même ligne — au bureau : sur un téléphone, la barre passe à la ligne
	//  (socle 11 §10), et c'est voulu.
	if (test.info().project.name !== 'bureau') return;
	const jour = page.getByRole('button', { name: 'Jour', exact: true });
	const [bJour, bSans] = [await jour.boundingBox(), await SANS(page).boundingBox()];
	const milieu = (b: { y: number; height: number } | null) => (b ? b.y + b.height / 2 : NaN);
	expect(Math.abs(milieu(bJour) - milieu(bSans))).toBeLessThan(6);
});

test('non proposé, gestionnaire désigné : rien à écarter, rien à dire', async ({ page }) => {
	await ouvrir(page, { propose: false, gestionnaire_designe: true });
	await expect(SANS(page)).toHaveCount(0);
	await expect(page.getByText('Aucun gestionnaire du site n’est désigné')).toHaveCount(0);
});

test('aucun gestionnaire désigné : l’écran le dit', async ({ page }) => {
	await ouvrir(page, { propose: false, gestionnaire_designe: false });
	await expect(SANS(page)).toHaveCount(0);
	await expect(page.getByText('Aucun gestionnaire du site n’est désigné')).toBeVisible();
});

test('Indicateurs et fréquentation : une seule section, dépliée à l’arrivée', async ({ page }) => {
	await ouvrir(
		page,
		{ propose: false, gestionnaire_designe: true },
		{ vues: 42, utilisateurs: 5, pages: 3 },
	);
	const section = page.locator('details', { hasText: 'Indicateurs et fréquentation' }).first();
	await expect(section).toHaveAttribute('open', '');
	await expect(section.getByText('Pages distinctes visitées')).toBeVisible();
	//  Les deux anciennes sections n'existent plus.
	await expect(page.getByText('📊 Indicateurs', { exact: true })).toHaveCount(0);
	await expect(page.getByText('📈 Fréquentation')).toHaveCount(0);
});
