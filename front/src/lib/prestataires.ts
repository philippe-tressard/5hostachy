/**
 * Le vocabulaire des prestataires et des contrats — **une seule fois**.
 *
 * ## Pourquoi ce module (20/08/2026)
 *
 * La table des types d'équipement vivait dans `prestataires/+page.svelte`, et
 * elle recopiait `TypeEquipement` côté serveur. Relevé du jour :
 *
 * | Écran | Ce qu'il montrait |
 * |---|---|
 * | Prestataires → Contrats | un libellé, pour **15** des **17** valeurs |
 * | Reporting → Prestataires | la valeur BRUTE : `chauffage_collectif` |
 * | Reporting → Renouvellements | la valeur BRUTE, **trois fois** |
 *
 * 🔴 Deux valeurs manquaient à la recopie — `assurance` et `syndic` — et elles
 * ne sont pas anodines : ce sont précisément les deux que la fiche de
 * copropriété DÉSIGNE (#553). Un contrat d'assurance s'affichait donc
 * « assurance », en minuscules, à côté de quinze libellés soignés.
 *
 * Et deux écrans sur trois n'affichaient aucun libellé du tout. Ce n'est pas une
 * faute d'inattention : c'est ce que produit une table qui vit dans UN écran —
 * les autres n'y ont pas accès, alors ils s'en passent.
 *
 * ## Ce que le garde-fou vérifie
 *
 * `api/tests/test_types_equipement.py` compare cette liste à `TypeEquipement`.
 * Il ne compare jamais deux copies l'une à l'autre : l'énumération du serveur
 * est **l'unique arbitre**. Même forme que `test_statuts_tickets.py` (#415), née
 * du même défaut — cinq listes, chacune cohérente avec elle-même, aucune juste.
 */

/**  Un type d'équipement, tel que l'écran le nomme.
 *
 *   ⚠️ `val` doit correspondre EXACTEMENT à `TypeEquipement` côté serveur : c'est
 *   la valeur qui part dans la charge utile. Le libellé, lui, n'est lu que par
 *   des humains. */
export type TypeEquipementOption = { val: string; label: string };

/**  Les 17 types d'équipement, dans l'ordre de l'énumération serveur.
 *
 *   🔴 `assurance` et `syndic` ne sont pas des « équipements », et le nom de
 *   l'énumération est donc un peu court. Ce qu'elle classe réellement, c'est
 *   « de quoi parle ce contrat » — et un contrat d'assurance ou un mandat de
 *   syndic en relèvent. En créer une seconde pour deux valeurs aurait donné deux
 *   nomenclatures à tenir d'accord. */
export const EQUIPEMENTS: readonly TypeEquipementOption[] = [
	{ val: 'ascenseur', label: '\u{1F6D7} Ascenseur' },
	{ val: 'chauffage_collectif', label: '\u{1F525} Chauffage collectif' },
	{ val: 'eau', label: '\u{1F4A7} Eau' },
	{ val: 'electricite', label: '⚡ Électricité' },
	{ val: 'espaces_verts', label: '\u{1F33F} Espaces verts' },
	{ val: 'extincteurs', label: '\u{1F9EF} Extincteurs' },
	{ val: 'interphone_digicode', label: '\u{1F4DE} Interphone/Digicode' },
	{ val: 'nettoyage', label: '\u{1F9F9} Nettoyage' },
	{ val: 'plomberie', label: '\u{1F6BF} Plomberie' },
	{ val: 'pompe', label: '⚙️ Pompe' },
	{ val: 'porte_parking', label: '\u{1F697} Porte parking' },
	{ val: 'serrurerie', label: '\u{1F511} Serrurerie' },
	{ val: 'toiture', label: '\u{1F3E0} Toiture' },
	{ val: 'vmc', label: '\u{1F4A8} VMC' },
	{ val: 'assurance', label: '\u{1F6E1}\u{FE0F} Assurance' },
	{ val: 'syndic', label: '\u{1F4BC} Syndic' },
	{ val: 'autre', label: '\u{1F527} Autre' },
];

/**  Le libellé d'un type d'équipement.
 *
 *   ⚠️ Le repli rend la valeur BRUTE plutôt qu'un tiret : une valeur inconnue
 *   signale une divergence avec le serveur, et l'afficher telle quelle la rend
 *   visible. Un `—` la masquerait, et le garde-fou étant côté tests, l'écran
 *   serait le seul endroit où elle pourrait encore se voir. */
export function equipLabel(val: string | null | undefined): string {
	if (!val) return '—';
	return EQUIPEMENTS.find((e) => e.val === val)?.label ?? val;
}

/**  Les catégories de prestataire, telles que l'écran les propose.
 *
 *   ⚠️ Même contrainte que ci-dessus : `val` correspond à `TypePrestataire`. */
export const TYPES_PRESTATAIRE: readonly { val: string; label: string; desc: string }[] = [
	{ val: 'contrat_recurrent', label: '\u{1F504} Contrat récurrent', desc: 'Entretien, maintenance' },
	{ val: 'ponctuel', label: '\u{1F4CD} Dépannage', desc: 'Interventions ponctuelles' },
	{ val: 'travaux', label: '\u{1F3D7}\u{FE0F} Travaux', desc: 'Interventions importantes' },
	{ val: 'reglementaire', label: '\u{1F4CB} Réglementaire', desc: 'Contrôles obligatoires' },
	{ val: 'etudes_expertise', label: '\u{1F4D0} Études & expertise', desc: 'Diagnostics, maîtrise d’œuvre' },
	{ val: 'gestion', label: '\u{1F3E2} Gestion', desc: 'Syndic, gestion locative' },
];

/**  La fréquence d'un contrat, en une expression courte.
 *
 *   Rend une chaîne vide quand aucune fréquence n'est définie : l'appelant
 *   n'affiche alors pas de pastille, plutôt qu'une pastille vide. */
export function frequenceLabel(c: {
	frequence_type?: string | null;
	frequence_valeur?: number | null;
}): string {
	const n = c.frequence_valeur ?? 0;
	if (c.frequence_type === 'semaines') return `↺ ${n} sem.`;
	if (c.frequence_type === 'mois') return '↺ Mensuel';
	if (c.frequence_type === 'fois_par_an') return `↺ ${n}×/an`;
	if (c.frequence_type === 'ans') return `↺ tous les ${n} an${n > 1 ? 's' : ''}`;
	return '';
}
