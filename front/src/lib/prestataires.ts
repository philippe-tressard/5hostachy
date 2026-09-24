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

/**  Ce qui classe un CONTRAT sans être un équipement sur lequel on intervient.
 *   Même liste côté serveur : `utils/intervenant.HORS_EQUIPEMENT`
 *   (`test_types_equipement.py` les compare). */
export const HORS_EQUIPEMENT: readonly string[] = ['assurance', 'syndic'];

/**  Les équipements qu'une AFFAIRE peut désigner (#1097) : la table des
 *   contrats, moins ce qui n'est pas un équipement. Dérivée, jamais recopiée. */
export const EQUIPEMENTS_AFFAIRE: readonly TypeEquipementOption[] = EQUIPEMENTS.filter(
	(e) => !HORS_EQUIPEMENT.includes(e.val),
);

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
	{
		val: 'contrat_recurrent',
		label: '\u{1F504} Contrat récurrent',
		desc: 'Entretien, maintenance',
	},
	{ val: 'ponctuel', label: '\u{1F4CD} Dépannage', desc: 'Interventions ponctuelles' },
	{ val: 'travaux', label: '\u{1F3D7}\u{FE0F} Travaux', desc: 'Interventions importantes' },
	{ val: 'reglementaire', label: '\u{1F4CB} Réglementaire', desc: 'Contrôles obligatoires' },
	{
		val: 'etudes_expertise',
		label: '\u{1F4D0} Études & expertise',
		desc: 'Diagnostics, maîtrise d’œuvre',
	},
	{ val: 'gestion', label: '\u{1F3E2} Gestion', desc: 'Syndic, gestion locative' },
];

/**  Les unités de fréquence — celles du contrat, qui fixe le rythme d'un
 *   prestataire (#1092, 23/09/2026). `nombre` : le libellé du nombre à saisir,
 *   absent quand il n'y en a pas (« mensuelle »). Lues par `ChampFrequence`,
 *   et côté serveur par `utils/intervenant.FREQUENCES` — mêmes valeurs. */
export const FREQUENCES: readonly { val: string; label: string; nombre?: string }[] = [
	{ val: 'semaines', label: 'Toutes les X semaines', nombre: 'Toutes les … sem.' },
	{ val: 'mois', label: 'Mensuelle' },
	{ val: 'fois_par_an', label: 'X fois par an', nombre: '… fois/an' },
	{ val: 'ans', label: 'Tous les X ans', nombre: 'Tous les … ans' },
];

/**  L'intervenant d'une affaire, tel que la fiche l'affiche : « Otis · ↺ Mensuel ».
 *   Vide sans intervenant — la ligne ne s'affiche pas (#1092, lot 5). */
export function intervenantAffiche(t: {
	prestataire_nom?: string | null;
	frequence_type?: string | null;
	frequence_valeur?: number | null;
}): string {
	if (!t.prestataire_nom) return '';
	const rythme = frequenceLabel(t);
	return rythme ? `${t.prestataire_nom} · ${rythme}` : t.prestataire_nom;
}

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

/**
 * **La forme du formulaire d'un contrat** — vierge, ou repris d'un existant.
 *
 * ## 🔴 Pourquoi ici (15/09/2026)
 *
 * Les **treize mêmes clés** étaient énumérées **trois fois** dans
 * `prestataires/+page.svelte` : la déclaration, `resetContratForm()` et
 * `startEditContrat()`. Ce n'est pas trois fois la même ligne, c'est trois fois
 * la même **structure** — et ajouter un champ demandait de le poser aux trois
 * endroits.
 *
 * ⚠️ Un champ posé sur deux des trois donne un formulaire qui enregistre à la
 * création et oublie à l'édition — ou l'inverse, selon l'endroit manqué. Et
 * **en silence** : une clé absente d'un objet JavaScript ne lève rien.
 *
 * C'est le même défaut que le calendrier portait le matin même, avec deux
 * écritures au lieu de trois (`$lib/evenement-formulaire`).
 */
export interface FormulaireContratData {
	copropriete_id: number;
	/**  Le PÉRIMÈTRE remplace `batiment_id`, qui n'était rempli par aucun champ
	 *   (10/09/2026). Le serveur en dérive le bâtiment. */
	perimetre_cible: string[];
	prestataire_id: string;
	type_equipement: string;
	libelle: string;
	numero_contrat: string;
	date_debut: string;
	duree_initiale_valeur: string | number;
	duree_initiale_unite: string;
	frequence_type: string;
	frequence_valeur: string | number;
	prochaine_visite: string;
	notes: string;
}

/**
 * Un formulaire de contrat VIERGE.
 *
 * :param perimetreDefaut: la liste par défaut, passée par l'appelant — elle vient
 *   de l'arborescence administrée (`$lib/perimetres`), que ce module n'a pas à
 *   connaître.
 */
export function contratVierge(perimetreDefaut: string[]): FormulaireContratData {
	return {
		copropriete_id: 1,
		perimetre_cible: perimetreDefaut,
		prestataire_id: '',
		type_equipement: 'autre',
		libelle: '',
		numero_contrat: '',
		//  La date du jour : un contrat se saisit le jour où on le reçoit, et
		//  corriger une date pré-remplie coûte moins que la saisir.
		date_debut: new Date().toISOString().slice(0, 10),
		duree_initiale_valeur: '',
		duree_initiale_unite: 'mois',
		frequence_type: '',
		frequence_valeur: '',
		prochaine_visite: '',
		notes: '',
	};
}

/**
 * Le formulaire d'un contrat EXISTANT, pour le corriger.
 *
 * :param typeEquipement: résolu par l'appelant, qui seul a la liste des
 *   prestataires sous la main — le type se déduit du prestataire quand le
 *   contrat ne le porte pas.
 */
export function contratDepuis(
	c: Record<string, any>,
	perimetreDefaut: string[],
	typeEquipement: string,
): FormulaireContratData {
	return {
		copropriete_id: c.copropriete_id,
		//  ⚠️ Une liste VIDE retombe sur le défaut : un contrat sans périmètre
		//  enregistré ne doit pas ouvrir le formulaire sur une rangée muette.
		perimetre_cible: c.perimetre_cible?.length ? c.perimetre_cible : perimetreDefaut,
		prestataire_id: String(c.prestataire_id ?? ''),
		type_equipement: typeEquipement,
		libelle: c.libelle,
		numero_contrat: c.numero_contrat ?? '',
		date_debut: c.date_debut,
		duree_initiale_valeur: c.duree_initiale_valeur ?? '',
		duree_initiale_unite: c.duree_initiale_unite ?? 'mois',
		frequence_type: c.frequence_type ?? '',
		frequence_valeur: c.frequence_valeur ?? '',
		prochaine_visite: c.prochaine_visite ?? '',
		notes: c.notes ?? '',
	};
}
