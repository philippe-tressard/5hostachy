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
	update: (id: number, data: { titre?: string; annee?: number | null; date_ag?: string | null }) =>
		api.patch<Document>(`/documents/${id}`, data),
	upload: async (
		titre: string,
		categorieId: number,
		file: File,
		perimetre = 'résidence',
		batimentId?: number,
		annee?: number,
		dateAg?: string,
		/**  De quoi PARLE le document, en codes de périmètre (`["bat:3"]`).
		 *
		 *   Remplace `batimentsIdsJson`, qui parlait en identifiants de lignes
		 *   (#470). ⚠️ Descriptif, jamais un droit : ce sont `perimetre` et
		 *   `batimentId` qui gouvernent la lecture. */
		perimetreCible?: string[],
	): Promise<Document> => {
		//  `postFormData` écarte lui-même les champs absents : plus de `if (x)`
		//  répété pour chaque champ facultatif.
		return postFormData<Document>('/documents', {
			titre,
			categorie_id: String(categorieId),
			perimetre,
			batiment_id: batimentId ? String(batimentId) : undefined,
			annee: annee ? String(annee) : undefined,
			date_ag: dateAg,
			perimetre_cible: perimetreCible?.length ? JSON.stringify(perimetreCible) : undefined,
			file,
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
