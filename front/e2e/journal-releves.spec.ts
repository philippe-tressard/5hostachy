/*
 *  **Le journal des messages relevés se lit sous la réception des réponses (#1447).**
 *
 *  Le 28/09/2026, un message a été ignoré sans qu'on puisse dire pourquoi. Ce
 *  test rend le VRAI onglet SMTP, API simulée, et lit ce qu'un administrateur
 *  voit : chaque verdict — ignoré compris — avec son motif, le lien vers
 *  l'affaire, et aucune adresse trop longue qui élargirait la page au téléphone.
 *
 *  Le même rendu sert l'historique WhatsApp (`JournalVerdicts`) : le second
 *  test vérifie qu'il n'a rien perdu en changeant de composant.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const ligne = (id: number, decision: string, motif: string, extra = {}) => ({
	id,
	releve_le: `2026-09-28T1${id}:00:00`,
	envoye_le: null,
	expediteur: 'Gestionnaire <gestion@syndic.fr>',
	objet: 'Re: Affaire #TK-121048 - Porte du hall',
	decision,
	motif,
	ticket_id: null,
	affaire: null,
	...extra,
});

const RELEVES = [
	ligne(4, 'ignore', 'ne répond à aucun ticket', {
		//  Sans espace : c'est elle qui élargirait la page si rien ne la coupait.
		expediteur:
			'une.adresse.particulierement.longue.sans.aucune.espace.ni.le.moindre.tiret@domaine.exemple.fr',
		objet: 'absente cette semaine',
	}),
	ligne(3, 'refuse', 'la signature ne couvre qu’une partie du message', {
		ticket_id: 7,
		affaire: 'TK-121048',
	}),
	ligne(2, 'relance', 'réponse à une relance groupée, transmise au conseil syndical'),
	ligne(1, 'accepte', 'ajouté au fil de l’affaire — signé par syndic.fr', {
		ticket_id: 7,
		affaire: 'TK-121048',
	}),
];

test('SMTP : chaque message relevé dit son verdict et pourquoi', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/releves-courriel') return RELEVES;
		return undefined;
	});
	await page.goto('/admin?onglet=smtp');

	const bloc = page.locator('.jv-liste');
	await expect(bloc).toBeVisible();
	const lignes = bloc.locator('.jv-ligne');
	await expect(lignes).toHaveCount(4);

	//  Le plus récent d'abord, tel que le serveur l'a rendu ; l'IGNORÉ dit pourquoi.
	await expect(lignes.nth(0).locator('.badge')).toHaveText('Ignoré');
	await expect(lignes.nth(0)).toContainText('ne répond à aucun ticket');
	await expect(lignes.nth(1).locator('.badge')).toHaveText('Refusé');
	await expect(lignes.nth(1).locator('.badge')).toHaveClass(/badge-orange/);
	await expect(lignes.nth(2).locator('.badge')).toHaveText('Transmis au conseil');
	await expect(lignes.nth(3).locator('.badge')).toHaveClass(/badge-green/);

	//  Une affaire rattachée se rouvre d'un clic ; sans affaire, aucun lien.
	await expect(lignes.nth(3).getByRole('link', { name: 'Affaire #TK-121048' })).toHaveAttribute(
		'href',
		'/tickets/7',
	);
	await expect(lignes.nth(0).getByRole('link')).toHaveCount(0);

	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde, 'défilement horizontal dans l’onglet SMTP').toBe(false);
	//  La page peut ne pas déborder alors qu'une ligne sort de son cadre (le
	//  conteneur coupe) : c'est la LIGNE qu'on mesure — ce contrôle a été vu
	//  passer au vert sans `overflow-wrap` tant qu'il ne regardait que la page.
	const lignesDebordent = await lignes.evaluateAll((els) =>
		els.some((el) => el.scrollWidth > el.clientWidth + 1),
	);
	expect(lignesDebordent, 'une ligne du journal déborde de son cadre').toBe(false);

	await bloc.screenshot({
		path: `test-results/journal-releves-${test.info().project.name}.png`,
	});
});

test('WhatsApp : l’historique des envois garde ses trois issues', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/whatsapp-logs')
			return [
				{
					id: 2,
					label: 'Encombrants',
					message: 'Demain.',
					statut: 'incertain',
					erreur: null,
					envoye_le: '2026-09-28T10:00:00',
				},
				{
					id: 1,
					label: 'Ascenseur',
					message: 'Réparé.',
					statut: 'échec',
					erreur: 'bridge absent',
					envoye_le: '2026-09-27T10:00:00',
				},
			];
		return undefined;
	});
	await page.goto('/admin?onglet=whatsapp');

	const lignes = page.locator('.jv-ligne');
	await expect(lignes).toHaveCount(2);
	await expect(lignes.nth(0).locator('.badge')).toHaveText('⚠️ incertain');
	await expect(lignes.nth(0).locator('.badge')).toHaveClass(/badge-orange/);
	await expect(lignes.nth(1).locator('.badge')).toHaveClass(/badge-red/);
	await expect(lignes.nth(1)).toContainText('bridge absent');
});
