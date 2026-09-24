/**
 *  Le mot de la gouttière de nature TIENT dans sa bande (#1220).
 *
 *  ## 🔴 Pourquoi ce test existe (24/09/2026)
 *
 *  La gouttière teintée d'une carte d'Affaires (v2.39.0) écrivait le mot de sa
 *  nature à la verticale. Sur une carte d'une ou deux lignes, « CALENDRIER »
 *  était plus long que la carte : il en dépassait. Trois alternatives ont été
 *  maquettées ; la C est choisie à l'écran — le mot à l'HORIZONTALE, en petites
 *  capitales, sous l'icône, la bande un peu élargie.
 *
 *  Le risque qu'elle prend est l'inverse : un mot trop LARGE pour la bande.
 *  Ce test le mesure pour chaque nature, avec la police que le navigateur
 *  applique réellement au pseudo-élément — un calcul à la main dans le CSS ne
 *  verrait pas une police de repli plus large (`standards/04` §14).
 *
 *  ⚠️ Les cartes sont derrière une connexion : le témoin est posé dans une page
 *  publique, et les libellés viennent du serveur de développement
 *  (`$lib/tickets-categories`), jamais recopiés ici.
 */
import { expect, test } from '@playwright/test';

import { attendreHydratation } from './aides';

test('le mot de chaque nature tient, à plat, dans la gouttière', async ({ page }, info) => {
	await page.goto('/auth/connexion');
	await attendreHydratation(page);

	const mesures = await page.evaluate(async () => {
		const { NATURES, attributsNature } = await import('/src/lib/tickets-categories.ts');
		const temoin = document.createElement('div');
		temoin.className = 'carte-liste';
		temoin.textContent = 'Témoin';
		document.body.append(temoin);
		const ctx = document.createElement('canvas').getContext('2d')!;
		const sortie = [];
		for (const n of NATURES) {
			for (const [k, v] of Object.entries(attributsNature({ natures: [n.val] }))) {
				temoin.setAttribute(k, v as string);
			}
			const mot = getComputedStyle(temoin, '::after');
			const bande = getComputedStyle(temoin, '::before');
			ctx.font = `${mot.fontWeight} ${mot.fontSize} ${mot.fontFamily}`;
			const texte = mot.textTransform === 'uppercase' ? n.libelle.toUpperCase() : n.libelle;
			const espacement = parseFloat(mot.letterSpacing) || 0;
			sortie.push({
				nature: n.val,
				affiche: mot.display !== 'none',
				ecriture: mot.writingMode,
				largeurMot: ctx.measureText(texte).width + espacement * texte.length,
				largeurBande: parseFloat(bande.width),
			});
		}
		temoin.remove();
		return sortie;
	});

	expect(mesures).toHaveLength(3);
	//  Au pouce, la gouttière ne garde que l'icône (`normes.css`) : le mot y est
	//  absent EXPRÈS. Sur le bureau, un mot absent serait une régression.
	if (info.project.name === 'bureau') {
		expect(
			mesures.every((m) => m.affiche),
			'le mot a disparu de la gouttière',
		).toBe(true);
	}
	for (const m of mesures) {
		if (!m.affiche) continue;
		expect(m.ecriture, `${m.nature} : le mot n'est pas écrit à plat`).toBe('horizontal-tb');
		expect(
			m.largeurMot,
			`${m.nature} : ${m.largeurMot.toFixed(1)} px de mot pour ${m.largeurBande} px de bande`,
		).toBeLessThanOrEqual(m.largeurBande - 4);
	}
});
