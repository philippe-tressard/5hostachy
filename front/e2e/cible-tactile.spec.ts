/**
 *  Les cibles tactiles font 44 × 44 px au doigt (`standards/11` §10).
 *
 *  🔴 Relevé le 08/09/2026 : les cent dix boutons icône du site mesuraient
 *  22 × 22 px (`font-size: .9rem` + `padding: .25rem`), ou 32 × 32 pour ceux de
 *  la barre d'actions. Le socle en donne la raison — *« une icône de 16 px reste
 *  cliquable à la souris et **inatteignable au pouce** »* — et ce ne sont pas
 *  des boutons anodins : ✏️ et 🗑️ voisinent dans la même rangée. Rater le
 *  premier de trois pixels ouvre une suppression.
 *
 *  ## ⚠️ Pourquoi ces tests injectent leur propre bouton
 *
 *  Ma première rédaction cherchait un `btn-icon*` sur une page publique. **Les
 *  quatre cas ont été SAUTÉS** : il n'y en a aucun — tous les écrans qui en
 *  portent sont derrière une connexion. Un test qui se saute intégralement est
 *  un faux vert, et il aurait fait croire la règle vérifiée.
 *
 *  Le bouton est donc posé dans la page **après** que ses feuilles de style sont
 *  chargées, et mesuré. Ce qu'on vérifie reste le COMPORTEMENT du CSS réel dans
 *  un vrai navigateur — pas la présence d'une règle dans un fichier
 *  (`standards/04` §14). Ce que ça ne prouve pas : qu'un écran donné l'applique
 *  bien, ce que seule une session pourrait montrer.
 *
 *  ⚠️ Les deux assertions sont **opposées**, et c'est volontaire : la règle est
 *  conditionnée à `pointer: coarse`, donc elle ne doit RIEN changer à la souris.
 *  Sans le second cas, élargir la cible pour tout le monde passerait au vert et
 *  détruirait la densité des rangées d'actions au bureau.
 */
import { expect, test } from '@playwright/test';

//  Une page publique quelconque : on ne s'intéresse qu'à ses feuilles de style.
const PAGE = '/auth/connexion';

/** Pose un bouton icône dans la page et rend sa boîte mesurée. */
async function mesurerBoutonIcone(page: import('@playwright/test').Page) {
	await page.goto(PAGE);
	await page.evaluate(() => {
		const b = document.createElement('button');
		b.className = 'btn-icon';
		b.id = 'temoin-tactile';
		b.textContent = '✏️';
		document.body.appendChild(b);
	});
	const boite = await page.locator('#temoin-tactile').boundingBox();
	//  Cas zéro : sans témoin mesurable, le test ne prouverait rien.
	expect(boite, 'le bouton témoin n’a pas été rendu').not.toBeNull();
	return boite!;
}

test('au doigt, un bouton icône fait au moins 44 × 44 px', async ({ page }, info) => {
	test.skip(info.project.name !== 'mobile', 'la règle ne vise que `pointer: coarse`');
	const boite = await mesurerBoutonIcone(page);
	expect(boite.width, 'largeur de la cible tactile').toBeGreaterThanOrEqual(44);
	expect(boite.height, 'hauteur de la cible tactile').toBeGreaterThanOrEqual(44);
});

test('à la souris, la densité des rangées d’actions est intacte', async ({ page }, info) => {
	test.skip(info.project.name !== 'bureau', 'le pendant : rien ne change au pointeur fin');
	const boite = await mesurerBoutonIcone(page);
	expect(
		boite.height,
		'la règle tactile déborde sur le bureau : la densité des rangées d’actions change',
	).toBeLessThan(44);
});
