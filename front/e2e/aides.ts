/*
 *  Aides partagées des tests de navigateur.
 */
import type { Page } from '@playwright/test';

/**
 * **Attendre que la page soit HYDRATÉE**, et pas seulement affichée.
 *
 * Les écrans sont rendus côté serveur : le formulaire de connexion existe dans
 * le HTML avant que le moindre gestionnaire ne soit posé. Un test qui remplit
 * ce formulaire trop tôt le SOUMET NATIVEMENT — la page se recharge, le
 * gestionnaire `preventDefault` n'a jamais existé, et le test échoue sur un
 * bandeau qui n'apparaîtra jamais. Même chose pour une image injectée avant que
 * la surveillance des images protégées ne soit en place : le test mesurerait
 * alors le moment de l'hydratation, pas la règle qu'il annonce.
 *
 * Le repère est posé par `$lib/imagesProtegees.ts`, depuis le `onMount` du
 * layout racine : quand il est là, le script du layout a tourné. Écrit ici une
 * fois — deux fichiers de test l'attendent, et un sélecteur recopié dans chacun
 * divergerait au premier renommage.
 */
export async function attendreHydratation(page: Page): Promise<void> {
	await page.locator('html[data-images-surveillees="oui"]').waitFor({ timeout: 10000 });
}
