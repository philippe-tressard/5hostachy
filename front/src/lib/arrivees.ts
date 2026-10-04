/**
 * **L'arrivée par une notification** (#1634) — l'étiquette `src` d'un lien de
 * courriel ou du groupe WhatsApp, lue à l'arrivée puis retirée de l'adresse.
 *
 * Le serveur l'écrit, une fois pour tous les modèles, là où chaque message se
 * compose (`api/app/utils/arrivees_notification.py`) : `courriel:<code du
 * modèle>` ou `whatsapp`, jamais une donnée personnelle, jamais sur un lien à
 * usage unique. Ici, la vue de la page d'arrivée la porte en `detail`, par
 * `trackEvent` — donc sous le refus du profil —, puis l'adresse affichée la
 * perd : un lien recopié depuis la barre ne la propage pas.
 *
 * ⚠️ Le paramètre, les deux canaux et la forme d'un code sont tenus à la main
 * avec `PARAMETRE_SOURCE` et `MOTIF_SOURCE` côté API : aucun fichier partagé.
 */
import { replaceState } from '$app/navigation';
import { page } from '$app/state';

export const PARAMETRE_SOURCE = 'src';
const MOTIF_SOURCE = /^(courriel|whatsapp)(:[a-z0-9_]{1,40})?$/;

/** L'étiquette si elle a la forme attendue, sinon rien. PUR. */
export function sourceValide(brut: string | null): string | undefined {
	return brut !== null && MOTIF_SOURCE.test(brut) ? brut : undefined;
}

/** Une arrivée par onglet chargé : une adresse reconstruite plus tard ne la recompte pas. */
let lue = false;

/**
 * L'étiquette de l'adresse courante, RETIRÉE de l'adresse affichée — à appeler
 * par `afterNavigate`. Une étiquette mal formée est retirée aussi, mais ne part pas.
 */
export function lireSourceArrivee(): string | undefined {
	if (lue || typeof window === 'undefined') return undefined;
	const url = new URL(window.location.href);
	if (!url.searchParams.has(PARAMETRE_SOURCE)) return undefined;
	lue = true;
	const source = sourceValide(url.searchParams.get(PARAMETRE_SOURCE));
	url.searchParams.delete(PARAMETRE_SOURCE);
	//  Au tour suivant : à l'arrivée (`enter`), le routeur appelle `afterNavigate`
	//  AVANT de se dire prêt, et `replaceState` refuserait.
	queueMicrotask(() => replaceState(url, page.state));
	return source;
}
