/**
 * L'ORDRE des pages — extrait de `pages.ts` le 16/09/2026.
 *
 * Le garde-fou de modularité a refusé que `pages.ts` franchisse 500 lignes, et
 * il avait raison : ce fichier-là porte la TABLE des pages, celui-ci porte les
 * règles qui l'ordonnent. Elles sont génériques — aucune ne connaît une page
 * particulière — et c'est ce qui rend l'extraction franche plutôt que cosmétique.
 *
 * ⚠️ `pages.ts` les réexporte : aucun appelant n'a eu à changer, et
 * `npm run lint:cles-listes` continue de les exercer par leur module d'origine.
 */
/**
 * Range des pages selon un ordre enregistré (`pages_order`), en reléguant toujours
 * en fin celles qui n'ont pas d'entrée de menu.
 *
 * Sans cette dernière règle, un ordre enregistré AVANT #401 — qui nommait encore
 * `profil` et `notifications` — les replaçait à leur position stockée, tandis que
 * `delegations`, absente de cet ordre puisqu'elle n'était pas proposée, tombait en
 * dernier : une page ordonnable s'affichait sous deux pages qui ne le sont pas
 * (constaté en production le 17/08/2026). Le premier déplacement réécrivait l'ordre
 * et corrigeait l'affichage — donc cela se serait résorbé exactement quand personne
 * n'en aurait plus eu besoin.
 *
 * Écrit ici plutôt que dans l'écran d'administration : c'est la table qui sait
 * qu'une page sans route ne s'ordonne pas, et `admin/+page.svelte` est au-dessus du
 * plafond de modularité — le contrôle a refusé qu'il grossisse, et il avait raison.
 */
export function ordonnerPages<T extends { id: string; href: string | null }>(
	pages: T[],
	idsEnregistres: string[],
): T[] {
	const parId = new Map(pages.map((p) => [p.id, p]));
	//  🔴 UN IDENTIFIANT RÉPÉTÉ NE DOIT JAMAIS RENDRE LA PAGE DEUX FOIS (16/09/2026).
	//
	//  `pages_order` est une donnée, pas du code : elle vit en base, s'édite depuis
	//  l'écran « Descriptif pages », et rien ne garantit qu'elle est saine. Quand
	//  elle portait deux fois le même identifiant, la liste rendue contenait deux
	//  fois la même page — et le `{#each … (pg.id)}` qui l'affiche levait
	//  `each_key_duplicate`, une erreur FATALE et non rattrapable de Svelte.
	//
	//  Ce que ça donnait à l'écran : l'onglet basculait, le contenu restait celui
	//  d'avant, et plus AUCUNE mise à jour ne passait ensuite — sur toutes les
	//  pages, le composant racine étant mort. Seule la fermeture de la fenêtre en
	//  sortait. Constaté deux fois en production, et pris pour un « figeage du
	//  site » alors que le serveur répondait en moins de 200 ms.
	//
	//  ⚠️ Le doublon se PROPAGEAIT : `movePage` réécrit `pages_order` à partir de
	//  cette liste, donc le premier déplacement enregistrait le doublon en base.
	const vus = new Set<string>();
	const ordonnees: T[] = [];
	for (const id of idsEnregistres) {
		const page = parId.get(id);
		if (!page || page.href === null || vus.has(id)) continue;
		vus.add(id);
		ordonnees.push(page);
	}
	const placees = new Set(ordonnees);
	//  🔴 La sortie est garantie sans id répété, quelle que soit l'ENTRÉE.
	//
	//  Dédoublonner le seul `idsEnregistres` ne suffisait pas : les pages reçues
	//  sont reconstruites à partir de `page_config_<id>`, du JSON stocké en base,
	//  et `{...saved}` en rapportait l'`id` ENREGISTRÉ. Deux configurations
	//  portant le même id produisaient donc deux pages homonymes que cette
	//  fonction recopiait fidèlement — et le `{#each … (pg.id)}` en mourait.
	//
	//  On ne garde donc pas une garantie sur ce qu'on reçoit, mais sur ce qu'on
	//  rend : c'est la seule qui tienne quand l'entrée vient d'une donnée.
	const rendus = new Set<string>();
	return [
		...ordonnees,
		...pages.filter((p) => p.href !== null && !placees.has(p)),
		...pages.filter((p) => p.href === null),
	].filter((p) => (rendus.has(p.id) ? false : (rendus.add(p.id), true)));
}

/**
 * Les identifiants répétés d'un ordre enregistré — pour le DIRE, pas pour le taire.
 *
 * Même raison que les identifiants inconnus signalés par `Nav` depuis #401 : une
 * donnée incohérente qu'on corrige en silence est un défaut qu'on ne cherchera
 * jamais. `ordonnerPages` la rend inoffensive ; ceci la rend visible.
 */
export function identifiantsRepetes(idsEnregistres: string[]): string[] {
	const vus = new Set<string>();
	const repetes = new Set<string>();
	for (const id of idsEnregistres) {
		if (vus.has(id)) repetes.add(id);
		vus.add(id);
	}
	return [...repetes];
}
