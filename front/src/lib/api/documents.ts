//  Documents, fichiers et téléversements : trois clients qui manipulent la
//  même notion et vivaient à 400 lignes d'écart.
import { api, BASE, postFormData } from './client';
import type { Document } from './types';

export const documents = {
	list: (categorieId?: number, contratId?: number) => {
		const params = new URLSearchParams();
		if (categorieId) params.set('categorie_id', String(categorieId));
		if (contratId) params.set('contrat_id', String(contratId));
		const qs = params.toString();
		return api.get<Document[]>(`/documents${qs ? `?${qs}` : ''}`);
	},
	listCategories: () =>
		api.get<{ id: number; code: string; libelle: string }[]>('/documents/categories'),
	/**  Corriger un document existant.
	 *
	 *   🔴 `description` et `perimetre_cible` ajoutés le 08/09/2026 (#852) :
	 *   *« très peu de champs sont éditables »*. Ils ne suffisaient pas côté
	 *   écran — `DocumentUpdate` ne les acceptait pas non plus, et les ouvrir
	 *   d'un seul côté aurait donné des champs qui ne font rien.
	 */
	update: (
		id: number,
		data: {
			titre?: string;
			description?: string;
			perimetre_cible?: string[];
			annee?: number | null;
			date_ag?: string | null;
		},
	) => api.patch<Document>(`/documents/${id}`, data),

	/**  Déposer un document.
	 *
	 *   🔴 **Un objet nommé, plus huit paramètres positionnels** (08/09/2026).
	 *   La signature d'avant était `(titre, categorieId, file, perimetre,
	 *   batimentId, annee, dateAg, perimetreCible)` : trois appels s'y
	 *   alignaient en écrivant `undefined, undefined, undefined` pour atteindre
	 *   le dernier.
	 *
	 *   ⚠️ Ce n'est pas une préférence de style. C'est exactement la forme qui a
	 *   produit le défaut de #470 — un formulaire liait son sélecteur de
	 *   périmètre à la variable d'un AUTRE formulaire, et rien ne levait :
	 *   les types concordaient, `svelte-check` était vert. Un argument nommé se
	 *   trompe moins facilement de place qu'un argument compté.
	 */
	upload: async (options: {
		titre: string;
		categorieId: number;
		file: File;
		/** Ce que le document COUVRE — section 6 du cadre (#852). */
		description?: string;
		/** Le droit de lecture. Distinct du périmètre descriptif ci-dessous. */
		perimetre?: string;
		batimentId?: number;
		annee?: number;
		dateAg?: string;
		/**  De quoi PARLE le document, en codes de périmètre (`["bat:3"]`).
		 *
		 *   Remplace `batimentsIdsJson`, qui parlait en identifiants de lignes
		 *   (#470). ⚠️ Descriptif, jamais un droit : ce sont `perimetre` et
		 *   `batimentId` qui gouvernent la lecture. */
		perimetreCible?: string[];
	}): Promise<Document> => {
		//  `postFormData` écarte lui-même les champs absents : plus de `if (x)`
		//  répété pour chaque champ facultatif.
		return postFormData<Document>('/documents', {
			titre: options.titre,
			description: options.description || undefined,
			categorie_id: String(options.categorieId),
			perimetre: options.perimetre ?? 'résidence',
			batiment_id: options.batimentId ? String(options.batimentId) : undefined,
			annee: options.annee ? String(options.annee) : undefined,
			date_ag: options.dateAg,
			perimetre_cible: options.perimetreCible?.length
				? JSON.stringify(options.perimetreCible)
				: undefined,
			file: options.file,
		});
	},
	uploadForContrat: (titre: string, contratId: number, file: File): Promise<any> =>
		postFormData('/documents', { titre, contrat_id: String(contratId), file }),
	uploadForPublication: (titre: string, publicationId: number, file: File): Promise<any> =>
		postFormData('/documents', { titre, publication_id: String(publicationId), file }),
	listByPublication: (publicationId: number) =>
		api.get<any[]>(`/documents?publication_id=${publicationId}`),
	downloadUrl: (docId: number) => `${BASE}/documents/${docId}/télécharger`,
	delete: (id: number) => api.delete(`/documents/${id}`),
};

export const fichiersApi = {
	/**
	 * Upload un fichier (photo ou document PDF/Word/Excel) destiné à être joint à
	 * un ticket, une affaire ou un commentaire. Ne demande aucun élément parent :
	 * l'URL est connue avant la création, ce qui permet de la passer dans le
	 * payload — et donc de la joindre à l'e-mail envoyé au syndic.
	 * Retourne { url, nom, type }
	 */
	upload: (file: File): Promise<{ url: string; nom: string; type: string }> =>
		postFormData('/uploads/fichier', { file }),
};

async function uploadFile(path: string, file: File): Promise<{ url: string }> {
	return postFormData(path, { file });
}

export function uploadExcel<T = any>(path: string, file: File, remplacer = false): Promise<T> {
	//  Le libellé reste distinct : un import de tableur qui échoue ne se raconte pas
	//  comme un téléversement de pièce jointe. C'est la SEULE des cinq divergences
	//  de libellé qui portait un sens ; les quatre autres disaient la même chose.
	return postFormData<T>(
		`${path}${remplacer ? '?remplacer=true' : ''}`,
		{ file },
		{
			libelleErreur: 'Erreur import',
		},
	);
}

export const uploads = {
	avatar: (file: File) => uploadFile('/uploads/avatar', file),
	residence: (file: File) => uploadFile('/uploads/residence', file),
};
