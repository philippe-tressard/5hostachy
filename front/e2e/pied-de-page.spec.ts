/*
 *  **Le pied de page se règle dans Admin › Site, sauf trois éléments (08/10/2026).**
 *
 *  Demandé : « rends la signature éditable sur la base des éléments
 *  actuellement disponibles », et la version ramenée à « v2.118.1 · RPi1 »,
 *  sans l'empreinte ni la date du build. Ce test rend le VRAI écran, avec l'API
 *  simulée, et vérifie ce qu'on LIT : un élément masqué disparaît, les éléments
 *  verrouillés (code source, mentions légales, confidentialité) restent même
 *  quand la configuration en base demande de les masquer, et l'aperçu de
 *  l'administration suit la pastille avant tout enregistrement.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
//  La version seule — ni empreinte ni date de build accolées.
const VERSION = /^v\d+\.\d+\.\d+$/;

test('sans réglage, le pied de page montre tout, et la version est courte', async ({ page }) => {
	await simulerApi(page);
	await page.goto('/tableau-de-bord');
	const pied = page.locator('footer.app-footer');
	await expect(pied).toContainText(`© ${new Date().getFullYear()}`);
	await expect(pied.getByText(VERSION)).toBeVisible();
	await expect(pied).toContainText('Mentions légales');
	await expect(pied).toContainText('Politique de confidentialité');
});

test('un élément masqué disparaît ; un élément verrouillé reste', async ({ page }) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/config'
			? { pied_de_page_masques: 'annee,version,source,mentions,confidentialite' }
			: undefined,
	);
	await page.goto('/tableau-de-bord');
	const pied = page.locator('footer.app-footer');
	//  Cas zéro : le pied de page est bien rendu avant qu'on y cherche une absence.
	await expect(pied).toContainText('Mentions légales');
	await expect(pied).toContainText('Politique de confidentialité');
	await expect(pied).toContainText('CoproConnect');
	await expect(pied).not.toContainText('©');
	await expect(pied).not.toContainText(/v\d+\.\d+\.\d+/);
});

test('Admin › Site : la pastille masque l’élément dans l’aperçu', async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await page.goto('/admin?onglet=site');
	const groupe = page.getByRole('group', { name: 'Éléments affichés' });
	const apercu = page.getByRole('group', { name: 'Aperçu du pied de page' });
	const annee = groupe.getByRole('button', { name: '© Année' });

	await expect(annee).toHaveAttribute('aria-pressed', 'true');
	await expect(apercu).toContainText('©');
	//  Les éléments verrouillés ne se proposent pas.
	await expect(groupe.getByRole('button', { name: 'Mentions légales' })).toHaveCount(0);

	await annee.click();
	await expect(annee).toHaveAttribute('aria-pressed', 'false');
	await expect(apercu).not.toContainText('©');
	await expect(apercu).toContainText('Mentions légales');
});

test('l’année de création fait « © 2026–… » ; le texte libre suit l’élément choisi', async ({
	page,
}) => {
	const courante = new Date().getFullYear();
	await simulerApi(page, (chemin) =>
		chemin === '/api/config'
			? {
					site_nom: 'Résidence témoin',
					pied_de_page_annee_debut: String(courante - 1),
					pied_de_page_texte: 'Texte du conseil',
					pied_de_page_texte_apres: 'annee',
				}
			: undefined,
	);
	await page.goto('/tableau-de-bord');
	const elements = page.locator('footer.app-footer > .element');
	await expect(elements.nth(0)).toHaveText(`© ${courante - 1}–${courante}`);
	await expect(elements.nth(1)).toHaveText('Texte du conseil');
	await expect(elements.nth(2)).toHaveText('Résidence témoin');
});

test('Admin › Site : le texte libre paraît dans l’aperçu et s’y déplace', async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await page.goto('/admin?onglet=site');
	const apercu = page.getByRole('group', { name: 'Aperçu du pied de page' });
	const elements = apercu.locator('.element');
	await page.getByLabel('Texte libre').fill('Texte du conseil');
	//  Sa place par défaut : juste après le nom de la résidence.
	const rang = async () => (await elements.allTextContents()).indexOf('Texte du conseil');
	const avant = await rang();
	expect(avant, 'le texte libre doit paraître dans l’aperçu').toBeGreaterThan(0);
	await page.getByRole('button', { name: 'Avancer le texte libre' }).click();
	await expect.poll(rang).toBe(avant - 1);
	await page.getByRole('button', { name: 'Reculer le texte libre' }).click();
	await expect.poll(rang).toBe(avant);
});
