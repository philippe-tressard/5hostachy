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
	await expect(pied).toContainText('CoproFirst');
	await expect(pied).not.toContainText('©');
	await expect(pied).not.toContainText(/v\d+\.\d+\.\d+/);
});

test('Admin › Site : la pastille masque l’élément dans l’aperçu', async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await page.goto('/admin?onglet=site');
	const groupe = page.getByRole('group', { name: 'Éléments, dans l’ordre' });
	const apercu = page.getByRole('group', { name: 'Aperçu du pied de page' });
	const annee = groupe.getByRole('button', { name: '© Année', exact: true });

	await expect(annee).toHaveAttribute('aria-pressed', 'true');
	await expect(apercu).toContainText('©');
	//  Un élément verrouillé ne se masque pas — il n'a pas de pastille — mais il se déplace.
	await expect(groupe.getByRole('button', { name: 'Mentions légales', exact: true })).toHaveCount(
		0,
	);
	await expect(groupe.getByRole('button', { name: 'Monter « Mentions légales »' })).toBeEnabled();

	await annee.click();
	await expect(annee).toHaveAttribute('aria-pressed', 'false');
	await expect(apercu).not.toContainText('©');
	await expect(apercu).toContainText('Mentions légales');
});

test('l’ordre, le préfixe du nom et l’année de création se lisent dans le pied de page', async ({
	page,
}) => {
	const courante = new Date().getFullYear();
	await simulerApi(page, (chemin) =>
		chemin === '/api/config'
			? {
					site_nom: '5Hostachy',
					pied_de_page_annee_debut: String(courante - 1),
					pied_de_page_ordre: 'annee,source,version,residence',
					pied_de_page_prefixe_nom: 'Résidence',
				}
			: undefined,
	);
	await page.goto('/tableau-de-bord');
	const elements = page.locator('footer.app-footer > .element');
	await expect(elements.nth(0)).toHaveText(`© ${courante - 1}–${courante}`);
	await expect(elements.nth(1)).toHaveText('CoproConnect');
	await expect(elements.nth(2)).toHaveText(/^v\d+\.\d+\.\d+$/);
	await expect(elements.nth(3)).toHaveText('Résidence 5Hostachy');
	//  Les éléments absents de l'ordre réglé viennent ensuite : rien ne disparaît.
	await expect(page.locator('footer.app-footer')).toContainText('Mentions légales');
});

test('Admin › Site : un élément monte et descend, l’aperçu suit', async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	await page.goto('/admin?onglet=site');
	const groupe = page.getByRole('group', { name: 'Éléments, dans l’ordre' });
	const elements = page.getByRole('group', { name: 'Aperçu du pied de page' }).locator('.element');
	const rang = async () => (await elements.allTextContents()).indexOf('CoproConnect');
	//  L'aperçu se rend après le chargement de la configuration : attendre qu'il y soit.
	await expect
		.poll(rang, { message: 'CoproConnect doit paraître dans l’aperçu' })
		.toBeGreaterThan(0);
	//  Un élément VERROUILLÉ se déplace aussi : CoproConnect monte jusqu'en tête.
	const monter = groupe.getByRole('button', { name: 'Monter « CoproConnect (code source) »' });
	while (await monter.isEnabled()) await monter.click();
	await expect.poll(rang).toBe(0);
	await groupe.getByRole('button', { name: 'Descendre « CoproConnect (code source) »' }).click();
	await expect.poll(rang).toBe(1);
	await page.getByLabel('Texte libre', { exact: true }).fill('Texte du conseil');
	await expect(elements).toContainText(['Texte du conseil']);
});
