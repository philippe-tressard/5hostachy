//  Les états d'une IDÉE — écrits une fois, comme ceux d'un ticket ou d'une
//  publication (`$lib/tickets`, `$lib/publications`).
//
//  Extrait de `routes/(app)/sondages/+page.svelte` le 18/08/2026, en passant le
//  workflow en pastilles (R3, #423). La page en portait **trois** listes : les
//  quatre `<option>` du sélecteur, la liste des filtres avec ses emoji, et une
//  table de badges — la forme exacte de #415, où quatre copies des statuts de
//  ticket avaient divergé. Trois listes d'accord entre elles ne prouvent rien.

/** Les états proposables, dans l'ordre du cycle de vie. */
export const STATUTS_IDEE = [
	{ value: 'ouverte', label: '\u{1F4A1} Ouverte' },
	{ value: 'retenue', label: '✅ Retenue' },
	{ value: 'realisee', label: '\u{1F389} Réalisée' },
	{ value: 'rejetee', label: '❌ Rejetée' },
];

/** La rangée de filtres — les mêmes états, précédés de « Toutes ». Dérivée,
    jamais réécrite : une seconde liste diverge au premier état ajouté. */
export const STATUTS_IDEE_FILTRE = [
	{ val: '', label: 'Toutes' },
	...STATUTS_IDEE.map((s) => ({ val: s.value, label: s.label })),
];

/** Le libellé d'un état, DÉRIVÉ de la liste — jamais une seconde table.

    La carte affichait le code brut (`realisee`, sans accent ni majuscule) là où
    les pastilles de la même carte montraient « 🎉 Réalisée » : deux écritures du
    même état à quelques centimètres l'une de l'autre (18/08/2026). */
export const STATUT_IDEE_LABELS: Record<string, string> = Object.fromEntries(
	STATUTS_IDEE.map((s) => [s.value, s.label]),
);

/** La classe de badge d'un état. */
export const IDEE_BADGE: Record<string, string> = {
	ouverte: 'badge-blue',
	retenue: 'badge-green',
	realisee: 'badge-purple',
	rejetee: 'badge-gray',
};
