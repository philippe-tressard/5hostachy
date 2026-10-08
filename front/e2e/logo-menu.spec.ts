/*
 *  **Le logo de la résidence se lit dans le menu.**
 *
 *  Demandé à l'écran le 08/10/2026, le logo une fois téléversé (#1728) : il
 *  s'affichait à 22 px, la taille d'une icône du menu. Un logo téléversé est
 *  une vignette pleine, et son dessin s'y réduisait à une tache. Il fait
 *  désormais 64 px sur la barre latérale et 30 dans l'en-tête mobile
 *  (`TAILLE_LOGO`, `Nav.svelte`), qui ne fait que 39 px de haut. Ce test passe
 *  sur les deux profils, mesure le logo que le profil AFFICHE, et vérifie qu'il
 *  tient dans sa barre : le lien mobile héritait du rembourrage de la barre
 *  latérale, et le logo en sortait par le haut.
 */
import { expect, simulerApi, test } from './aides';

test('le logo téléversé s’affiche en grand dans le menu, et tient dans sa barre', async ({
	page,
}, info) => {
	await simulerApi(page, (chemin) =>
		chemin === '/api/config' ? { site_nom: 'Résidence témoin', site_logo: 'logo.png' } : undefined,
	);
	await page.goto('/tableau-de-bord');
	//  Cas zéro : c'est bien le logo téléversé qui est rendu, pas l'icône.
	const logo = page.locator('.brand-link:visible img.logo-residence');
	await expect(logo).toHaveCount(1);
	const boite = await logo.boundingBox();
	const attendu = info.project.name === 'mobile' ? 30 : 64;
	expect(boite!.width).toBe(attendu);
	expect(boite!.height).toBe(attendu);
	if (info.project.name === 'mobile') {
		const barre = (await page.locator('.mobile-topbar').boundingBox())!;
		expect(boite!.y, 'le logo sort de l’en-tête par le haut').toBeGreaterThanOrEqual(barre.y);
		expect(boite!.y + boite!.height, 'le logo sort de l’en-tête par le bas').toBeLessThanOrEqual(
			barre.y + barre.height,
		);
	}
});
