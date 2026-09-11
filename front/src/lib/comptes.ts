/**
 * Valider un compte en attente — le geste, et ce qu'il rend compte.
 *
 * ## Pourquoi ce module (12/09/2026, #889)
 *
 * Le geste était écrit **deux fois** : `admin` et `espace-cs`. Les deux appellent
 * `traiterCompte` puis, si l'on coche « Nouvel Arrivant », `accueilArrivant`.
 * Elles avaient déjà divergé, et pas sur un détail :
 *
 * | | `admin` | `espace-cs` |
 * |---|---|---|
 * | lots résolus automatiquement | annoncés | **tus** |
 * | copropriétaire aidé introuvable | averti | **tu** |
 * | aucun lot trouvé pour un copropriétaire | averti | **tu** |
 * | message d'accueil | « (bienvenue, consignes, demandes syndic/CS) » | « Actions d'accueil envoyées » |
 *
 * L'endpoint rend pourtant le même `auto_match` aux deux. Le conseil syndical
 * validait donc des comptes sans jamais savoir qu'un copropriétaire aidé n'avait
 * pas été retrouvé — l'information existait, elle n'était pas lue.
 *
 * 🔴 `standards/02` §4 bis : quand deux implémentations coexistent, on retient
 * **la plus disante**. C'est elle qui est ici, et les deux écrans l'obtiennent.
 */
import { admin as adminApi, ApiError } from '$lib/api';
import { nomAffiche } from '$lib/noms';

/** Un message à afficher, et le ton sur lequel le dire. */
export interface Annonce {
	ton: 'success' | 'warning' | 'error';
	texte: string;
}

/**
 * Ce que le serveur vient de faire, traduit en une phrase.
 *
 * ⚠️ Séparée de l'appel réseau pour être vérifiable sans rien monter : c'est la
 * partie qui porte les six cas, donc celle qui peut se tromper.
 */
export function annonceValidation(reponse: any, utilisateur: any): Annonce {
	const auto = reponse?.auto_match;
	const aide = auto?.aide_match;
	if (aide?.aide_trouve) {
		const parts = [`Compte activé — aidé(e) : ${aide.aide_nom}`];
		if (aide.lots > 0) parts.push(`${aide.lots} lot(s)`);
		if (aide.tc > 0) parts.push(`${aide.tc} TC`);
		if (aide.vigik > 0) parts.push(`${aide.vigik} vigik`);
		if (aide.delegation) parts.push('délégation créée');
		return { ton: 'success', texte: parts.join(' — ') };
	}
	if (aide && !aide.aide_trouve) {
		const nom = nomAffiche(utilisateur?.prenom_aide, utilisateur?.nom_aide);
		return {
			ton: 'warning',
			texte: `Compte activé — ⚠️ Copropriétaire aidé(e) « ${nom} » non trouvé(e). Affectation manuelle requise.`,
		};
	}
	const resolus = auto?.lots_resolus ?? 0;
	if (resolus > 0) {
		return {
			ton: 'success',
			texte: `Compte activé — ${resolus} lot(s) résolu(s) automatiquement.`,
		};
	}
	const trouves = auto?.lots ?? 0;
	if (trouves > 0) {
		return { ton: 'success', texte: `Compte activé — ${trouves} lot(s) trouvé(s) dans l'import.` };
	}
	//  ⚠️ Un AVERTISSEMENT, pas un succès : un copropriétaire sans lot ne pourra
	//  rien consulter. Le silence de l'espace CS sur ce cas est le défaut que ce
	//  module supprime.
	if (utilisateur?.statut?.startsWith('copropriétaire')) {
		return { ton: 'warning', texte: "Compte activé — ⚠️ Aucun lot trouvé dans l'import." };
	}
	return { ton: 'success', texte: 'Compte activé.' };
}

/** Ce que l'accueil d'un nouvel arrivant déclenche — dit en toutes lettres. */
export const ANNONCE_ACCUEIL =
	"Actions d'accueil envoyées (bienvenue, consignes, demandes syndic/CS).";

export interface ValidationDemandee {
	nouvelArrivant: boolean;
	batiment: string;
	ancienResident: string;
}

/**
 * Valide le compte, puis déclenche l'accueil si demandé.
 *
 * Rend les annonces à afficher, dans l'ordre — l'appelant les passe au toast.
 * Lève `ApiError` : c'est l'écran qui sait comment le dire.
 *
 * ⚠️ L'accueil part APRÈS la validation et jamais avant : il écrit au syndic et
 * au conseil syndical au sujet d'un compte qui doit exister.
 */
export async function validerCompte(
	utilisateur: any,
	demande: ValidationDemandee,
): Promise<Annonce[]> {
	const reponse = await adminApi.traiterCompte(utilisateur.id, { action: 'valider' });
	const annonces: Annonce[] = [annonceValidation(reponse, utilisateur)];
	if (demande.nouvelArrivant) {
		await adminApi.accueilArrivant(utilisateur.id, {
			batiment: demande.batiment || null,
			ancien_resident: demande.ancienResident || null,
		});
		annonces.push({ ton: 'success', texte: ANNONCE_ACCUEIL });
	}
	return annonces;
}

/** Le message d'une erreur d'API, ou un repli — les deux écrans l'écrivaient. */
export function messageErreur(e: unknown): string {
	return e instanceof ApiError ? e.message : ((e as any)?.message ?? 'Erreur');
}
