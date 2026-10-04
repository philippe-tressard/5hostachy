/**
 * Les écrans que personne n'a ouverts sur une période (#1630).
 *
 * Le tableau de bord de télémétrie montre les pages LES PLUS visitées ; il ne
 * montre pas celles que PERSONNE ne visite — or c'est ce qui sert à décider quoi
 * simplifier, regrouper ou retirer. La liste des écrans se lit dans `pages.ts`
 * (la table unique : page, onglets, sous-onglets), jamais recopiée côté API — le
 * front et l'API ne partagent aucun fichier —, et se soustrait des pages vues
 * (`top_pages`, non bornée : toutes les pages vues y figurent).
 *
 * ## Ce que la comparaison fait, et ne fait pas
 *
 * - **Exacte, après normalisation** : la requête (`?onglet=`), l'ancre et la barre
 *   finale s'enlèvent des deux côtés. Un écran de détail (`/tickets/123`) n'est
 *   pas déclaré dans la table, donc n'y entre pas — et ne rend pas pour autant sa
 *   liste « visitée ».
 * - **L'administration est UN écran** : ses onglets vivent sous `/admin?onglet=…`
 *   et la télémétrie ne collecte pas la requête, donc ils ne se distinguent pas.
 * - **Un écran réservé à un rôle est MARQUÉ**, pas présenté comme mort : il n'est
 *   vu que par peu de comptes (administration, espace CS, onglets `reserve`).
 * - Une page sans route (`href: null` — profil, notifications) n'a rien à
 *   comparer : elle n'est pas dans la liste.
 *
 * Fonctions PURES, sans import : l'auto-test (`scripts/check-ecrans-non-visites.mjs`)
 * lit CE fichier, celui que le site embarque.
 */

/** Ce que la comparaison lit d'une page de `pages.ts` — structurel, pour ne rien importer. */
export interface PageLue {
	id: string;
	href: string | null;
	navLabel: string;
	onglets?: {
		label: string;
		route: string;
		reserve?: string;
		sous?: { route: string }[];
	}[];
}

/** Un écran déclaré, avec le libellé sous lequel on le nomme. */
export interface EcranDeclare {
	route: string;
	libelle: string;
	/** Réservé à un rôle : peu de comptes le voient, il n'est pas « mort » pour autant. */
	reserve: boolean;
}

export interface BilanEcrans {
	/** Les écrans déclarés dont une visite figure dans la période. */
	visites: number;
	total: number;
	nonVisites: EcranDeclare[];
}

/** `/a/b/?x=1#y` → `/a/b` ; la racine reste `/`. */
export function cheminNormalise(chemin: string): string {
	const sans = chemin.split('#')[0].split('?')[0].trim();
	const net = sans.length > 1 ? sans.replace(/\/+$/, '') : sans;
	return net || '/';
}

/** « 🏷️ Badges & télécommandes » → « Badges & télécommandes » : le pictogramme n'a rien à faire dans une liste. */
function sansPictogramme(libelle: string): string {
	return libelle.replace(/^[^\p{L}\p{N}]+/u, '').trim();
}

/**
 * Les écrans de la table, dédoublonnés par route. La page passe avant ses onglets,
 * et le premier nom rencontré fait foi (un onglet de l'administration se replie sur `/admin`).
 *
 * @param idsReservees les pages que seul un rôle ouvre (`pages-roles.ts`).
 */
export function ecransDeclares(
	pages: readonly PageLue[],
	idsReservees: ReadonlySet<string> = new Set(),
): EcranDeclare[] {
	const vus = new Map<string, EcranDeclare>();
	const poser = (route: string, libelle: string, reserve: boolean) => {
		const cle = cheminNormalise(route);
		if (!vus.has(cle)) vus.set(cle, { route: cle, libelle, reserve });
	};
	for (const p of pages) {
		const reservee = idsReservees.has(p.id);
		if (p.href) poser(p.href, p.navLabel, reservee);
		for (const o of p.onglets ?? []) {
			const libelle = `${p.navLabel} › ${sansPictogramme(o.label)}`;
			const reserve = reservee || o.reserve !== undefined;
			poser(o.route, libelle, reserve);
			//  Un sous-onglet n'a pas de libellé dans la table : son dernier segment d'adresse le nomme.
			for (const s of o.sous ?? [])
				poser(s.route, `${libelle} › ${s.route.slice(s.route.lastIndexOf('/') + 1)}`, reserve);
		}
	}
	return [...vus.values()];
}

/** Les écrans déclarés qu'aucune page vue de la période ne désigne. */
export function ecransNonVisites(
	declares: readonly EcranDeclare[],
	pagesVues: readonly { page: string }[],
): BilanEcrans {
	const vues = new Set(pagesVues.map((p) => cheminNormalise(p.page)));
	const nonVisites = declares.filter((e) => !vues.has(e.route));
	return { visites: declares.length - nonVisites.length, total: declares.length, nonVisites };
}
