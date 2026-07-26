/**
 * Liens profonds — arriver sur l'ÉLÉMENT visé, pas seulement sur sa page.
 *
 * Le fil d'activité, les notifications et les e-mails renvoient vers une page qui
 * contient parfois des centaines d'éléments répartis en onglets. Y arriver sans
 * précision oblige l'utilisateur à chercher ce sur quoi il vient de cliquer — et le
 * 24/07/2026 « Voir l'annonce → » ouvrait l'onglet Sondages, où l'annonce n'est
 * évidemment pas.
 *
 * Convention du projet, à respecter des deux côtés :
 *   - `?onglet=<id>`     → onglet à sélectionner (`/sondages?onglet=annonces`)
 *   - `#<prefixe>-<id>`  → élément à ouvrir et à révéler (`#annonce-42`)
 *
 * Les préfixes sont vérifiés en CI (`api/tests/test_liens_front.py`) : un lien de
 * l'API dont l'ancre n'est produite par aucune page fait échouer le build.
 */

/** Identifiant ciblé par `#<prefixe>-<id>`, ou `null` si l'URL ne vise rien. */
export function cibleDuHash(prefixe: string): number | null {
	if (typeof window === 'undefined') return null;
	const m = window.location.hash.match(new RegExp(`^#${prefixe}-(\\d+)$`));
	return m ? parseInt(m[1], 10) : null;
}

/** Onglet demandé par `?onglet=`, s'il fait partie des valeurs attendues. */
export function ongletDeLUrl<T extends string>(valides: readonly T[]): T | null {
	if (typeof window === 'undefined') return null;
	const v = new URLSearchParams(window.location.search).get('onglet');
	return valides.includes(v as T) ? (v as T) : null;
}

/**
 * Amène l'élément à l'écran et le souligne brièvement.
 *
 * Le délai laisse Svelte rendre l'élément (il vient souvent d'être déplié par
 * l'appelant). La surbrillance est retirée d'elle-même : sur une longue liste, un
 * simple défilement ne dit pas *lequel* des éléments visibles était visé.
 */
export function revelerCible(elementId: string, delaiMs = 100): void {
	if (typeof window === 'undefined') return;
	setTimeout(() => {
		const el = document.getElementById(elementId);
		if (!el) return;
		el.scrollIntoView({ behavior: 'smooth', block: 'start' });
		el.classList.add('cible-lien');
		setTimeout(() => el.classList.remove('cible-lien'), 2500);
	}, delaiMs);
}
