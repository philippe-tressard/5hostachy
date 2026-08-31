/**
 * Pièces jointes — une seule définition de « qu'est-ce qu'une image », « quel
 * nom afficher » et « quels types accepter ».
 *
 * Ces trois règles étaient recopiées dans les pages : le test d'image huit fois,
 * le nom dérivé de l'URL sept fois, la liste `accept` trois fois. Une pièce
 * jointe ajoutée au mauvais endroit tombait alors dans la mauvaise colonne
 * (`.gif` classé « document », vignette jamais affichée) sans que rien ne le
 * signale.
 *
 * La liste blanche qui FAIT AUTORITÉ est celle du serveur
 * (`api/app/routers/uploads.py`) : celle-ci ne fait que filtrer le sélecteur de
 * fichiers du navigateur, elle ne protège rien. Les deux doivent rester
 * alignées — `api/tests/test_pieces_jointes.py` le vérifie.
 */

/** Formats d'image acceptés par `_save_image` (ALLOWED_MIME côté API). */
export const ACCEPT_PHOTOS = 'image/jpeg,image/png,image/webp,image/gif';

/** Documents acceptés par `POST /uploads/fichier` (ALLOWED_DOC_MIME côté API). */
export const ACCEPT_DOCUMENTS = 'application/pdf,text/plain,.pdf,.doc,.docx,.xls,.xlsx,.txt';

/** Les deux à la fois, pour un sélecteur unique « pièce jointe ». */
export const ACCEPT_FICHIERS = `${ACCEPT_PHOTOS},${ACCEPT_DOCUMENTS}`;

/** Nombre maximum de pièces jointes par objet.
 *
 *  Il était écrit À LA MAIN dans chaque appel de `FichiersUpload` — 5 sur les
 *  tickets, le calendrier et les évolutions, 6 sur les actualités, 2 sur les
 *  petites annonces. Trois limites pour la même notion, qu'aucun écran
 *  n'annonçait de la même façon (16/08/2026).
 *
 *  Porté ici, il se change une fois pour tout le site — et le libellé du
 *  composant l'annonce, donc il ne peut plus mentir. Valeur retenue par
 *  l'utilisateur : la plus disante des trois, élargie à 10.
 */
export const MAX_FICHIERS = 10;

/** Extensions produites par nos propres endpoints d'upload d'image. */
const EXTENSIONS_IMAGE = /\.(jpe?g|png|webp|gif)$/i;

/**
 * Préfixe technique posé par `nom_stocke` (api/app/utils/fichiers.py) :
 * 32 caractères hexadécimaux suivis d'un `_`. Il rend l'URL non devinable mais
 * n'a aucun sens pour un lecteur.
 */
const PREFIXE_UUID = /^[0-9a-f]{32}_/i;

/** Cette URL désigne-t-elle une image affichable en vignette ? */
export function estImage(url: string): boolean {
	return EXTENSIONS_IMAGE.test(url || '');
}

/**
 * Nom lisible d'une pièce jointe, déduit de son URL.
 *
 * Les fichiers téléversés avant le 03/08/2026 sont nommés `{uuid}.pdf` : le nom
 * d'origine n'était pas conservé, il n'y a rien à en tirer. Depuis, ils sont
 * nommés `{uuid}_{nom}.pdf` et le nom réapparaît.
 */
export function nomFichier(url: string): string {
	let base = (url || '').split('/').pop() || url || '';
	try {
		base = decodeURIComponent(base);
	} catch {
		/* URL mal encodée : on garde la forme brute plutôt que d'échouer */
	}
	return base.replace(PREFIXE_UUID, '') || base;
}

/** Pièce jointe telle que la manipulent les formulaires (EvolForm, uploads). */
export interface PieceJointe {
	url: string;
	nom: string;
	type: 'image' | 'document';
}

/**
 * Liste d'URLs stockées → pièces jointes affichables.
 *
 * Trois pages construisaient cet objet à la main pour pré-remplir `EvolForm` en
 * mode édition, chacune avec sa propre copie du test d'image et du nom.
 */
export function fichiersDepuisUrls(urls: string[] | null | undefined): PieceJointe[] {
	return (urls ?? []).map((url) => ({
		url,
		nom: nomFichier(url),
		type: estImage(url) ? ('image' as const) : ('document' as const),
	}));
}

/** Sépare une liste d'URLs en photos (vignettes) et documents (liens). */
export function separerFichiers(urls: string[] | null | undefined): {
	photos: string[];
	documents: string[];
} {
	const liste = urls ?? [];
	return {
		photos: liste.filter(estImage),
		documents: liste.filter((u) => !estImage(u)),
	};
}

/**
 * Ce qu'une carte REPLIÉE doit montrer en vignette, quand l'objet lui-même ne
 * porte rien mais que son Historique, si.
 *
 * ## Pourquoi (18/08/2026, constaté à l'écran)
 *
 * Un événement de calendrier n'a le plus souvent **aucune photo propre** : c'est
 * le suivi qui en apporte — « le technicien est intervenu ce matin, voici les
 * anomalies », avec trois clichés. La carte repliée n'affichait donc rien, là où
 * un ticket illustré montre sa vignette d'un coup d'œil. Signalé ainsi :
 * *« en plié pas de vignette »*.
 *
 * La règle du repli existait déjà dans le produit, dans l'autre sens : ce qu'une
 * entrée d'Historique DIFFUSE porte ses propres pièces, « avec repli sur l'objet
 * si elle n'en a pas » (`flux/tickets.py`). Ici c'est le même principe appliqué à
 * l'aperçu, et il suit la même logique que le fil, qui **date du dernier fait et
 * jamais du premier** : ce qu'on montre d'un objet suivi, c'est où il en est.
 *
 * ⚠️ **La plus RÉCENTE d'abord.** Prendre la première entrée montrerait
 * indéfiniment la photo du jour de l'ouverture, sur un dossier qui a avancé.
 *
 * ⚠️ Cette fonction ne déclenche **aucun chargement** : elle ne sert qu'aux
 * écrans dont l'API livre déjà l'Historique avec l'objet — le calendrier
 * (`EvenementRead.evolutions`). Les tickets chargent leurs évolutions **à la
 * demande**, au dépliage : les réclamer en liste coûterait une requête par carte,
 * et c'est un changement d'API à trancher à part.
 */
export function apercuAvecRepli(
	photos: string[] | null | undefined,
	fichiers: string[] | null | undefined,
	evolutions: { fichiers_urls?: string[] | null }[] | null | undefined,
): { photos: string[]; fichiers: string[] } {
	const propres = { photos: photos ?? [], fichiers: fichiers ?? [] };
	if (propres.photos.length || propres.fichiers.length) return propres;

	//  De la plus récente à la plus ancienne, la première entrée qui porte
	//  quelque chose. `slice()` : `reverse()` mute, et le tableau appartient à
	//  l'appelant — le muter réordonnerait SON fil à l'écran.
	for (const evol of (evolutions ?? []).slice().reverse()) {
		const pieces = separerFichiers(evol.fichiers_urls);
		if (pieces.photos.length || pieces.documents.length) {
			return { photos: pieces.photos, fichiers: pieces.documents };
		}
	}
	return propres;
}

/**
 * Attacher des fichiers à une publication, un par un, dans l'ordre.
 *
 * Les deux chemins de `FormulaireActualite` faisaient la même boucle : celui qui
 * ajoute des documents à une publication existante, et celui qui téléverse ce
 * qui avait été retenu pendant la création (la publication n'ayant pas encore
 * d'identifiant au moment du choix). Extraite le 31/08/2026, sur refus de
 * modularité — et le contrôle désignait bien une duplication, pas une longueur.
 *
 * ⚠️ **Séquentiel, et c'est voulu** : l'API attribue son ordre d'affichage à
 * l'arrivée. Un `Promise.all` les remonterait dans un ordre imprévisible.
 *
 * Elle **laisse remonter** l'erreur : chaque appelant décide s'il la signale ou
 * s'il poursuit — ils n'en font pas la même chose, et c'est légitime.
 */
export interface DocumentAttache {
	id: number;
	titre?: string;
	fichier_nom?: string;
}

export async function attacherAPublication(
	publicationId: number,
	fichiers: Iterable<File>,
): Promise<DocumentAttache[]> {
	const { documents } = await import('$lib/api');
	const crees: DocumentAttache[] = [];
	for (const f of fichiers) {
		crees.push(await documents.uploadForPublication(f.name, publicationId, f));
	}
	return crees;
}
