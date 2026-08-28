/**
 * Les imports d'ACCÈS — télécommandes et badges Vigik — décrits, pas recopiés.
 *
 * ## Pourquoi ce fichier existe (27/08/2026, #453)
 *
 * `OngletImportTelecommandes.svelte` (349 l.) et `OngletImportVigik.svelte`
 * (329 l.) étaient **identiques à 87 %** — 263 lignes communes sur 314. Le même
 * écran, le même geste, le même tableau, écrits deux fois : téléverser un fichier
 * Excel, rapprocher automatiquement, corriger les liaisons à la main, résoudre ou
 * ignorer.
 *
 * Ce qui les distinguait n'était **jamais du comportement** — sauf un cas, décrit
 * plus bas — mais des DONNÉES : le jeu d'endpoints, les colonnes du tableau, le
 * vocabulaire (« la télécommande » / « le badge Vigik »), et une tuile de
 * statistique. C'est donc une table, et l'écran devient unique.
 *
 * ## ✅ La divergence que la factorisation a révélée — et qui est comblée
 *
 * `remettreEnAttente` n'existait **que pour les télécommandes**, côté front comme
 * côté serveur : un import Vigik ignoré par erreur était **définitivement perdu**,
 * là où le même geste se rattrape sur une télécommande.
 *
 * Ce n'était pas une décision mais un oubli, resté invisible tant que les deux
 * écrans étaient deux fichiers — chacun paraissait complet. **Comblé le
 * 28/08/2026 (#576)**, en miroir exact de l'endpoint des télécommandes.
 *
 * ⚠️ Le champ est redevenu **OBLIGATOIRE**, et c'est le point : tant qu'il restait
 * optionnel, le mécanisme d'exception survivait à l'exception, et le prochain
 * type d'import pouvait l'omettre sans que rien ne le dise. C'est la leçon de la
 * prop `marge` d'`EntetePage` (`ux-patterns` §13) : *tant que le mécanisme
 * d'exception existe, l'exception se reproduit.*
 */
import { acces as accesApi } from '$lib/api';

/** Une colonne du tableau, propre à un type d'import. */
export interface ColonneImport {
	entete: string;
	/** Lue sur la ligne d'import ; `—` si absente. */
	cle: string;
	/** Rendue en `<code>` — pour une référence ou un numéro de badge. */
	code?: boolean;
}

/** Une case à cocher supplémentaire du formulaire d'édition. */
export interface ChampBooleen {
	cle: string;
	libelle: string;
}

export interface ModeleImportAcces {
	/** Sert au `<title>` et n'apparaît nulle part ailleurs. */
	titre: string;
	/** Ce qu'on crée en résolvant, au singulier avec son article : « le badge Vigik ». */
	objet: string;
	/** Colonnes du fichier Excel, affichées en aide au-dessus du sélecteur. */
	colonnesAttendues: string;
	/** Colonnes propres à ce type, insérées avant « Propriétaire (Excel) ». */
	colonnes: ColonneImport[];
	/** La colonne qui identifie l'objet — sans elle, on ne peut pas résoudre. */
	colonneCle: ColonneImport;
	/** Tuile de statistique propre à ce type, après les cinq communes. */
	statSupplementaire: { cle: string; libelle: string };
	/** Le badge affiché sur une ligne résolue : « ✓ Badge #12 ». */
	badgeResolu: (imp: any) => string;
	/** Libellé de la case « … chez le locataire ». */
	libelleChezLocataire: string;
	/** Cases supplémentaires du formulaire d'édition. */
	champsBooleens: ChampBooleen[];
	/** Décorations du statut — icônes que seul un type porte. */
	decorationsStatut: (imp: any) => { icone: string; titre: string }[];
	api: {
		upload: (file: File, remplacer: boolean) => Promise<any>;
		list: (statut?: string) => Promise<any[]>;
		stats: () => Promise<any>;
		autoMatch: () => Promise<any>;
		patch: (id: number, data: unknown) => Promise<any>;
		resoudre: (id: number) => Promise<any>;
		ignorer: (id: number) => Promise<any>;
		/**  Rattrape un import ignoré par erreur. OBLIGATOIRE depuis #576 : les
		 *   deux objets ont le même cycle d'import, donc les mêmes gestes. */
		remettreEnAttente: (id: number) => Promise<any>;
	};
}

export const IMPORT_TELECOMMANDES: ModeleImportAcces = {
	titre: 'Import Télécommandes',
	objet: 'la télécommande',
	colonnesAttendues: 'Copropriétaire | Locataire | Télécommandes',
	colonnes: [],
	colonneCle: { entete: 'Référence', cle: 'reference', code: true },
	statSupplementaire: { cle: 'avec_reference', libelle: 'Avec réf.' },
	badgeResolu: (imp) => `✓ TC #${imp.telecommande_id}`,
	libelleChezLocataire: 'TC chez le locataire',
	champsBooleens: [{ cle: 'refuse_par_locataire', libelle: 'Locataire a refusé' }],
	decorationsStatut: (imp) => {
		const d = [];
		if (imp.refuse_par_locataire) d.push({ icone: '\u{1F6B7}', titre: 'Locataire a refusé' });
		else if (imp.chez_locataire) d.push({ icone: '\u{1F464}', titre: 'TC chez le locataire' });
		return d;
	},
	api: {
		upload: accesApi.uploadImportTC,
		list: accesApi.listImportsTC,
		stats: accesApi.statsImportsTC,
		autoMatch: accesApi.autoMatchImportsTC,
		patch: accesApi.patchImportTC,
		resoudre: accesApi.resoudreImportTC,
		ignorer: accesApi.ignorerImportTC,
		remettreEnAttente: accesApi.remettreEnAttenteImportTC,
	},
};

export const IMPORT_VIGIK: ModeleImportAcces = {
	titre: 'Import Vigik',
	objet: 'le badge Vigik',
	colonnesAttendues: 'BATIMENT | APPARTEMENT | NOM DU COPROPRIÉTAIRE | NOM LOCATAIRE | N° CLÉS',
	colonnes: [
		{ entete: 'Bât.', cle: 'batiment_raw' },
		{ entete: 'Appt.', cle: 'appartement_raw' },
	],
	colonneCle: { entete: 'Code', cle: 'code', code: true },
	statSupplementaire: { cle: 'avec_lot', libelle: 'Lot auto-lié' },
	badgeResolu: (imp) => `✓ Badge #${imp.vigik_id}`,
	libelleChezLocataire: 'Vigik chez le locataire',
	champsBooleens: [],
	decorationsStatut: () => [],
	api: {
		upload: accesApi.uploadImportVigik,
		list: accesApi.listImportsVigik,
		stats: accesApi.statsImportsVigik,
		autoMatch: accesApi.autoMatchImportsVigik,
		patch: accesApi.patchImportVigik,
		resoudre: accesApi.resoudreImportVigik,
		ignorer: accesApi.ignorerImportVigik,
		//  ✅ Divergence COMBLÉE le 28/08/2026 (#576) : l'endpoint existe désormais,
		//  en miroir exact de celui des télécommandes. Les deux objets ont le même
		//  cycle d'import, donc les mêmes gestes — l'asymétrie venait de l'ordre
		//  dans lequel les deux écrans ont été écrits, pas d'un arbitrage.
		remettreEnAttente: accesApi.remettreEnAttenteImportVigik,
	},
};

/** Les cinq statuts, communs aux deux types. */
export const STATUT_BADGE: Record<string, string> = {
	en_attente: 'badge-orange',
	proprietaire_lie: 'badge-blue',
	resolu: 'badge-green',
	ignore: 'badge-gray',
};

export const STATUT_LABEL: Record<string, string> = {
	en_attente: 'En attente',
	proprietaire_lie: 'Proprio lié',
	resolu: 'Résolu',
	ignore: 'Ignoré',
};
