/**
 * Le nom de la section des objets archivés — **écrit une seule fois** (#516).
 *
 * ## Pourquoi une constante pour deux mots
 *
 * Le ticket #516 s'ouvrait sur un relevé : six écrans, **trois mots** pour la
 * même notion — « Historique », « Archive », « Archives », plus « Historique des
 * demandes » et « Terminé ». Le pire n'était pas la diversité : c'est
 * qu'« Historique » désignait AUSSI le fil d'un objet (cadre #430), et que les
 * deux coexistaient sur l'écran Tickets.
 *
 * Le mot a été unifié le 19/08. Mais il l'a été **à la main**, écrit en dur dans
 * cinq fichiers : les cinq concordaient parce qu'on venait de les aligner, à un
 * instant où tout coïncide. C'est exactement l'état d'avant le ticket, et rien
 * ne le tenait — le point 4 le disait :
 *
 * > « Un garde-fou : le titre de la section doit venir d'une constante partagée,
 * >   pas d'une chaîne écrite dans chaque page — sinon la divergence revient au
 * >   premier écran ajouté. »
 *
 * ## Pourquoi « Archives » et pas « Historique »
 *
 * | | |
 * |---|---|
 * | **Pas de collision** | « Historique » reste le fil d'un objet (#430). Aucun des deux sens ne bouge |
 * | **Cohérent avec le geste** | le bouton est 📦 Archiver ; la section montre ce qu'on a archivé |
 * | **Dit ce que c'est** | une archive est ce qu'on range sans jeter — « archiver n'est pas supprimer » |
 *
 * ⚠️ « Archivage » a été envisagé et écarté : c'est l'**action**, pas le
 * **contenu**. La section liste des objets.
 *
 * 🔒 Garde-fou : `npm run lint:archives` refuse un titre de section écrit en dur.
 */

/** L'icône, la même partout. 📁 — et non 📦, qui est le geste. */
export const ICONE_ARCHIVES = '\u{1F4C1}';

/** Le titre complet d'une section d'archives. */
export const TITRE_ARCHIVES = `${ICONE_ARCHIVES} Archives`;

/** L'icône du FIL d'un objet. 📋 — le presse-papiers, pas le classeur. */
export const ICONE_HISTORIQUE = '\u{1F4CB}';

/**
 * Le titre du **fil d'un objet** — l'autre notion, celle du cadre #430.
 *
 * 🔴 Les deux constantes vivent dans le même fichier À DESSEIN. C'est leur
 * confusion qui a fondé #516 : « Historique » désignait les deux, et les deux
 * coexistaient sur l'écran Tickets. Les nommer côte à côte est ce qui rend la
 * distinction lisible — un lecteur qui cherche « Archives » voit ici, en une
 * ligne, ce qu'« Historique » désigne et pourquoi ce n'est pas la même chose.
 *
 * | Constante | Ce que c'est | Composant |
 * |---|---|---|
 * | `TITRE_ARCHIVES` | les OBJETS rangés d'un écran | `ArchivesParAnnee` |
 * | `TITRE_HISTORIQUE` | le FIL d'UN objet | `RubriqueHistorique` |
 */
export const TITRE_HISTORIQUE = `${ICONE_HISTORIQUE} Historique`;
