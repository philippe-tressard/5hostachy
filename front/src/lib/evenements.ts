/**
 * **Le TYPE d'un événement** — les six natures, écrites une fois.
 *
 * ## 🔴 Pourquoi ce module (15/09/2026)
 *
 * Les six types étaient énumérés **deux fois**, dans deux écrans qui ne se
 * voient pas :
 *
 * | Écrit où | Sous quelle forme |
 * |---|---|
 * | `calendrier/+page.svelte` | `{ val: 'travaux', label: '🔨 Travaux' }` — l'emoji **dans** le libellé, plus un `typeLabel()` local pour le relire |
 * | `tableau-de-bord/+page.svelte` | `EV_ICONS = { travaux: '🔨' }` — l'emoji **seul**, sans libellé |
 *
 * Deux écritures, deux formes, et aucune qui se voie depuis l'autre : ajouter un
 * septième type donnait une option au calendrier et **aucune icône** au tableau
 * de bord — un espace vide là où les six autres ont un pictogramme. Rien ne lève.
 *
 * ## La règle déployée, pas une invention
 *
 * C'est exactement ce que `$lib/tickets` fait pour les catégories depuis le
 * 17/08/2026 : **une** liste de `{ value, label, emoji }`, et les tables plates
 * DÉRIVÉES par `parAttributDepuisListe`. Le calendrier a besoin de l'emoji collé
 * au libellé, le tableau de bord de l'emoji seul : deux lectures d'une même
 * déclaration, plus deux déclarations.
 *
 * ⚠️ À ne pas confondre avec les types de **prestataire** (`$lib/prestataires`),
 * qui portent aussi un « Travaux » — sous un autre pictogramme (🏗️) et pour une
 * autre question : ce qu'une entreprise fait, non ce qu'un événement est.
 */
import { parAttributDepuisListe } from '$lib/table-statuts';

export interface TypeEvenement {
	/** Valeur envoyée à l'API — jamais traduite. */
	value: string;
	/** Le mot seul, sans pictogramme. */
	label: string;
	/** Le pictogramme seul, pour une pastille ou une puce de calendrier. */
	emoji: string;
}

//: L'ordre est celui des options : du plus fréquent au fourre-tout, qui ferme
//: la liste. `maintenance_recurrente` suit `maintenance` parce qu'elle s'y lit
//: comme une variante, pas comme une septième nature.
export const TYPES_EVENEMENT: readonly TypeEvenement[] = [
	{ value: 'travaux', label: 'Travaux', emoji: '\u{1F528}' },
	{ value: 'coupure', label: 'Coupure', emoji: '⚡' },
	{ value: 'ag', label: 'AG', emoji: '\u{1F3DB}\u{FE0F}' },
	{ value: 'maintenance', label: 'Maintenance', emoji: '\u{1F527}' },
	{ value: 'maintenance_recurrente', label: 'Maintenance récurrente', emoji: '\u{1F504}' },
	{ value: 'autre', label: 'Autre', emoji: '\u{1F4CC}' },
];

const COLONNE = parAttributDepuisListe(TYPES_EVENEMENT, 'value');

/** Le pictogramme d'un type — c'est ce que portait `EV_ICONS`. */
export const TYPE_EVENEMENT_EMOJI: Record<string, string> = COLONNE.emoji;

/** Le mot seul. */
export const TYPE_EVENEMENT_LABELS: Record<string, string> = COLONNE.label;

//: Options d'un `<select>` ou d'une rangée de boutons — pictogramme compris,
//: exactement comme `STATUT_TICKET_OPTIONS`.
export const TYPE_EVENEMENT_OPTIONS = TYPES_EVENEMENT.map((t) => ({
	val: t.value,
	label: `${t.emoji} ${t.label}`,
}));

/** « 🔨 Travaux ». Valeur brute à défaut — un libellé manquant doit se voir. */
export function typeEvenementLabel(type: string | null | undefined): string {
	const t = TYPES_EVENEMENT.find((x) => x.value === type);
	return t ? `${t.emoji} ${t.label}` : (type ?? '');
}

/** Le pictogramme seul, jamais vide : une puce sans icône se lit comme un trou. */
export function typeEvenementEmoji(type: string | null | undefined): string {
	return TYPE_EVENEMENT_EMOJI[type ?? ''] ?? '\u{1F4CC}';
}
