/*
 *  **Télémétrie : les arrivées par notification** (#1634).
 *
 *  Le lien d'un courriel ou du groupe WhatsApp porte `src=courriel:<modèle>` ou
 *  `src=whatsapp`. À l'arrivée, la vue de la page l'emporte en `detail`, puis
 *  l'adresse affichée la perd. Une étiquette mal formée est retirée aussi, mais
 *  ne part pas : rien d'autre qu'un canal et un code ne quitte le navigateur.
 */
import {
	attendreHydratation,
	deplierSectionTelemetrie,
	type Evenement,
	expect,
	lotsEnvoyes,
	MEMBRE_CS,
	simulerApi,
	TABLEAU_TELEMETRIE_VIDE,
	test,
	viderLaFile,
} from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
const etiquetees = (recus: Evenement[]) =>
	recus.filter((e) => e.action === 'view' && e.detail).map((e) => [e.page, e.detail]);

test('l’étiquette part avec la vue, une fois, puis quitte l’adresse', async ({ page }) => {
	await simulerApi(page);
	const recus = await lotsEnvoyes(page);
	await page.goto('/tickets?nature=&src=courriel:ticket_nouveau#liste');
	await attendreHydratation(page);

	await expect.poll(() => new URL(page.url()).searchParams.has('src')).toBe(false);
	//  Le reste de l'adresse ne bouge pas.
	expect(new URL(page.url()).hash).toBe('#liste');

	await viderLaFile(page);
	await expect.poll(() => etiquetees(recus)).toEqual([['/tickets', 'courriel:ticket_nouveau']]);
});

test('un lien vers l’accueil garde son étiquette jusqu’au tableau de bord', async ({ page }) => {
	//  La racine trie (connexion ou tableau de bord) : sans elle, l'arrivée par
	//  « Accéder à l'application » ne se compterait jamais.
	await simulerApi(page);
	const recus = await lotsEnvoyes(page);
	await page.goto('/?src=courriel:compte_valide');
	await page.waitForURL(/\/tableau-de-bord/);
	await attendreHydratation(page);

	await expect.poll(() => new URL(page.url()).searchParams.has('src')).toBe(false);
	await viderLaFile(page);
	await expect
		.poll(() => etiquetees(recus))
		.toEqual([['/tableau-de-bord', 'courriel:compte_valide']]);
});

test('une étiquette mal formée est retirée et ne part pas', async ({ page }) => {
	await simulerApi(page);
	const recus = await lotsEnvoyes(page);
	await page.goto('/tickets?src=anne.dupont%40exemple.test');
	await attendreHydratation(page);

	await expect.poll(() => new URL(page.url()).searchParams.has('src')).toBe(false);
	await viderLaFile(page);
	await expect.poll(() => recus.length).toBeGreaterThan(0);
	expect(etiquetees(recus)).toEqual([]);
});

test('le panneau rend chaque canal et ses envois', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/telemetry/dashboard')
			return {
				...TABLEAU_TELEMETRIE_VIDE,
				arrivees: [
					{
						canal: 'courriel',
						modele: 'ticket_nouveau',
						libelle: 'Nouvelle affaire',
						arrivees: 3,
						comptes: 2,
						envois: 2,
					},
					{ canal: 'whatsapp', modele: null, libelle: null, arrivees: 1, comptes: 0, envois: 1 },
					{
						canal: 'courriel',
						modele: 'sondage_nouveau',
						libelle: null,
						arrivees: 0,
						comptes: 0,
						envois: 4,
					},
				],
			};
	});
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);
	const section = await deplierSectionTelemetrie(page, 'Arrivées par notification');

	await expect(
		section.getByRole('row', { name: /Courriel\s+Nouvelle affaire\s+3\s+2\s+2/ }),
	).toBeVisible();
	await expect(
		section.getByRole('row', { name: /WhatsApp\s+Groupe de la résidence\s+1\s+0\s+1/ }),
	).toBeVisible();
	//  Envoyé, jamais suivi : la ligne existe, à zéro.
	await expect(section.getByRole('row', { name: /sondage_nouveau\s+0\s+0\s+4/ })).toBeVisible();
});
