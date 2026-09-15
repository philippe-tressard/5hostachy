/**
 * **La forme du formulaire d'un événement** — vierge, ou repris d'un existant.
 *
 * ## 🔴 Pourquoi ce module (15/09/2026)
 *
 * Les deux constructeurs vivaient dans `calendrier/+page.svelte` et énuméraient
 * **les mêmes quatorze clés** : `formulaireVierge()` pour la création,
 * l'affectation de `startEdit()` pour la correction. Ce n'est pas deux fois la
 * même ligne, c'est deux fois la même **structure** — et ajouter un champ
 * demandait de le poser aux deux endroits.
 *
 * C'est exactement le piège rencontré en ajoutant « Saisi pour » : le champ posé
 * d'un seul côté aurait donné un formulaire qui enregistre à la création et
 * oublie à l'édition — ou l'inverse, selon l'endroit oublié. Silencieusement,
 * puisqu'une clé absente ne lève rien.
 *
 * ⚠️ **Toutes les clés sont présentes dans les deux cas**, y compris vides.
 * `calendrier/+page.svelte` compose sa charge utile par `{ ...form }` : une clé
 * absente ne part pas, et le serveur lit la PRÉSENCE des champs pour décider
 * d'écrire (`exclude_unset`). Une structure à trous produirait donc des
 * corrections qui ne corrigent rien, sans message.
 */
import { champsSaisiPour } from '$lib/saisi-pour';

/** Le formulaire d'un événement — la structure, une seule fois. */
export interface FormulaireEvenementData {
	titre: string;
	description: string;
	type: string;
	lieu: string;
	debut: string;
	/** Écarté de la charge utile : il est recomposé dans `debut` à l'envoi. */
	debut_heure: string;
	fin: string;
	statut_kanban: string;
	prestataire_id: string;
	frequence_type: string;
	frequence_valeur: string;
	affichable: boolean;
	epingle: boolean;
	reserve_cs: boolean;
	partager_whatsapp: boolean;
	envoyer_syndic: boolean;
	envoyer_cs: boolean;
	saisi_pour_user_id: number | null;
	saisi_pour_nom: string;
	saisi_pour_email: string;
}

/**
 * Un formulaire VIERGE.
 *
 * ⚠️ Les valeurs sont posées explicitement, jamais laissées à `undefined` :
 * c'est ce qui donne à `form` un type inféré complet. Une clé ajoutée plus tard
 * par affectation n'existerait pas dans ce type, et **tous** ses usages
 * passeraient en erreur TypeScript.
 */
export function evenementVierge(debut = ''): FormulaireEvenementData {
	return {
		titre: '',
		description: '',
		type: 'autre',
		lieu: '',
		debut,
		debut_heure: '',
		fin: '',
		statut_kanban: '',
		prestataire_id: '',
		frequence_type: '',
		frequence_valeur: '',
		affichable: true,
		epingle: false,
		reserve_cs: false,
		partager_whatsapp: false,
		envoyer_syndic: false,
		envoyer_cs: false,
		...champsSaisiPour(null),
	};
}

/**
 * Le formulaire d'un événement EXISTANT, pour le corriger.
 *
 * ⚠️ Les dates sont découpées ici et pas à l'écran : `debut` garde le jour,
 * `debut_heure` l'heure, et l'envoi les recompose. Trois écritures de ce
 * découpage coexistaient avant que le formulaire ne soit extrait.
 */
export function evenementDepuis(ev: Record<string, unknown>): FormulaireEvenementData {
	const debut = (ev.debut as string | undefined) ?? '';
	return {
		titre: (ev.titre as string) ?? '',
		description: (ev.description as string | null) ?? '',
		type: (ev.type as string) ?? 'autre',
		lieu: (ev.lieu as string | null) ?? '',
		debut: debut.slice(0, 10),
		debut_heure: debut.slice(11, 16),
		fin: ((ev.fin as string | null) ?? '').slice(0, 16),
		statut_kanban: (ev.statut_kanban as string | null) ?? '',
		prestataire_id: ev.prestataire_id ? String(ev.prestataire_id) : '',
		frequence_type: (ev.frequence_type as string | null) ?? '',
		frequence_valeur: ev.frequence_valeur ? String(ev.frequence_valeur) : '',
		affichable: (ev.affichable as boolean | undefined) ?? true,
		epingle: (ev.epingle as boolean | undefined) ?? false,
		reserve_cs: (ev.reserve_cs as boolean | undefined) ?? false,
		partager_whatsapp: (ev.partager_whatsapp as boolean | undefined) ?? false,
		envoyer_syndic: (ev.envoyer_syndic as boolean | undefined) ?? false,
		envoyer_cs: (ev.envoyer_cs as boolean | undefined) ?? false,
		...champsSaisiPour(ev),
	};
}
