/**
 * `use:portail` — rendre un élément à la RACINE du document (26/09/2026).
 *
 * Une bulle ancrée à un élément de carte (la suite du 🔗) héritait des règles
 * de la rangée où vit son déclencheur : `EnteteCarte` donne 22 px de large à
 * TOUT bouton de sa rangée, et « L'envoyer par courriel » s'y repliait mot à
 * mot. Positionnée en `fixed`, la bulle n'a rien à faire dans ce DOM-là : on
 * l'en sort, et elle ne porte plus que ses propres styles.
 */
export function portail(noeud: HTMLElement) {
	document.body.appendChild(noeud);
	return {
		destroy() {
			noeud.remove();
		},
	};
}
