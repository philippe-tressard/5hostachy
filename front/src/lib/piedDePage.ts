/**
 * Le PIED DE PAGE de l'application — ses éléments, et ceux que l'administration
 * peut masquer (Admin › Site, 08/10/2026).
 *
 * ## Ce qui se stocke : les éléments MASQUÉS, jamais les affichés
 *
 * La clé `pied_de_page_masques` liste ce que l'administrateur a retiré. Absente
 * ou vide, tout s'affiche, c'est-à-dire le pied de page d'avant ce réglage. Un
 * élément ajouté plus tard à `ELEMENTS_PIED` paraît donc d'office, au lieu de
 * rester invisible parce qu'aucune instance ne l'avait coché.
 *
 * ## 🔴 Trois éléments ne se masquent pas
 *
 * Ils sont `verrouille`, avec leur raison : `lireMasques` les écarte de la
 * valeur lue, quelle que soit la configuration en base (une saisie directe par
 * l'API compte aussi). Le pied de page n'a donc pas à les tester un par un.
 * Le composant d'affichage est `PiedDePage.svelte`, celui du réglage est
 * `ReglagePiedDePage.svelte` (Admin › Site).
 *
 * ## L'année et le texte libre (arbitrés à l'écran, 08/10/2026)
 *
 * - **L'année** : « © 2026 » l'année de création, « © 2026–2027 » les suivantes.
 *   L'année de création se règle (`pied_de_page_annee_debut`) ; vide, seule
 *   l'année en cours s'affiche — une autre résidence règle la sienne.
 * - **Le texte libre** est un élément comme les autres, qui se masque, mais
 *   dont la PLACE se choisit : il suit l'élément nommé par
 *   `pied_de_page_texte_apres` (vide : en tête). Sans texte, il ne s'affiche pas.
 */
import { NOM_PLATEFORME } from '$lib/plateforme';

export interface ElementPied {
	code: string;
	/** Le nom de l'élément dans le réglage de l'administration. */
	libelle: string;
	/** Pourquoi l'élément ne se masque pas. S'il est absent, il se masque. */
	verrouille?: string;
}

/** Les éléments du pied de page, dans leur ordre d'affichage — le texte libre
 *  y a sa place par défaut, que `pied_de_page_texte_apres` déplace. */
export const ELEMENTS_PIED: readonly ElementPied[] = [
	{ code: 'annee', libelle: '© Année' },
	{ code: 'residence', libelle: 'Nom de la résidence' },
	{ code: 'texte', libelle: 'Texte libre' },
	{ code: 'version', libelle: 'Version' },
	{ code: 'serveur', libelle: 'Serveur (RPi)' },
	{
		code: 'source',
		libelle: `${NOM_PLATEFORME} (code source)`,
		verrouille:
			'la licence AGPL impose d’offrir le code source de la version en service à qui utilise le site',
	},
	{
		code: 'mentions',
		libelle: 'Mentions légales',
		verrouille: 'elles doivent rester accessibles depuis chaque page (LCEN, art. 6)',
	},
	{
		code: 'confidentialite',
		libelle: 'Politique de confidentialité',
		verrouille: 'l’information des personnes doit rester accessible (RGPD, art. 13)',
	},
];

/** La clé de configuration — publique : le pied de page la lit dans `/config`. */
export const CLE_PIED_MASQUES = 'pied_de_page_masques';

const MASQUABLES = new Set(ELEMENTS_PIED.filter((e) => !e.verrouille).map((e) => e.code));

/** Les éléments masquables, ceux que le réglage propose. */
export const ELEMENTS_MASQUABLES = ELEMENTS_PIED.filter((e) => !e.verrouille);

/** Les éléments verrouillés, que le réglage ne propose pas et nomme à part. */
export const ELEMENTS_VERROUILLES = ELEMENTS_PIED.filter((e) => e.verrouille);

/** Valeur stockée → codes masqués. Les codes inconnus ou verrouillés sont ignorés. */
export function lireMasques(valeur: string | undefined | null): string[] {
	return (valeur ?? '')
		.split(',')
		.map((c) => c.trim())
		.filter((c) => MASQUABLES.has(c));
}

/** Codes masqués → valeur stockée, dans l'ordre d'affichage et sans doublon. */
export function ecrireMasques(masques: readonly string[]): string {
	return ELEMENTS_MASQUABLES.filter((e) => masques.includes(e.code))
		.map((e) => e.code)
		.join(',');
}

/** Les quatre clés de configuration du pied de page — publiques : le pied de
 *  page les lit dans `/config`. */
export const CLES_PIED = {
	masques: CLE_PIED_MASQUES,
	anneeDebut: 'pied_de_page_annee_debut',
	texte: 'pied_de_page_texte',
	texteApres: 'pied_de_page_texte_apres',
} as const;

/** Le texte libre ne fait qu'une ligne de pied de page. */
export const TEXTE_PIED_MAX = 120;

/** Le réglage du pied de page, tel que l'administration le saisit. */
export interface ReglagePied {
	masques: string[];
	/** L'année de création ; vide, seule l'année en cours s'affiche. */
	anneeDebut: number | null;
	texte: string;
	/** Le code de l'élément que le texte libre suit ; vide : en tête. */
	texteApres: string;
}

const AUTRES_CODES = ELEMENTS_PIED.map((e) => e.code).filter((c) => c !== 'texte');
/** La place du texte libre quand rien n'est réglé : celle de `ELEMENTS_PIED`. */
const TEXTE_APRES_DEFAUT = ELEMENTS_PIED[ELEMENTS_PIED.findIndex((e) => e.code === 'texte') - 1].code;

/** Une année plausible, ou null — une saisie vide ou fautive ne casse pas le pied de page. */
function lireAnnee(valeur: string | number | null | undefined): number | null {
	const n = Number(String(valeur ?? '').trim());
	return Number.isInteger(n) && n >= 1900 && n <= 9999 ? n : null;
}

/** Configuration stockée → réglage. Tout ce qui est inconnu retombe sur le défaut. */
export function lireReglagePied(cfg: Record<string, string | undefined>): ReglagePied {
	const apres = cfg[CLES_PIED.texteApres] ?? TEXTE_APRES_DEFAUT;
	return {
		masques: lireMasques(cfg[CLES_PIED.masques]),
		anneeDebut: lireAnnee(cfg[CLES_PIED.anneeDebut]),
		texte: (cfg[CLES_PIED.texte] ?? '').trim().slice(0, TEXTE_PIED_MAX),
		texteApres: apres === '' || AUTRES_CODES.includes(apres) ? apres : TEXTE_APRES_DEFAUT,
	};
}

/** Réglage → configuration stockée. */
export function ecrireReglagePied(r: ReglagePied): Record<string, string> {
	return {
		[CLES_PIED.masques]: ecrireMasques(r.masques),
		[CLES_PIED.anneeDebut]: r.anneeDebut === null ? '' : String(lireAnnee(r.anneeDebut) ?? ''),
		[CLES_PIED.texte]: r.texte.trim().slice(0, TEXTE_PIED_MAX),
		[CLES_PIED.texteApres]: r.texteApres,
	};
}

/** « © 2026 » l'année de création (ou sans elle), « © 2026–2027 » ensuite. */
export function mentionAnnee(debut: number | null, courante: number): string {
	return debut !== null && debut < courante ? `© ${debut}–${courante}` : `© ${courante}`;
}

/** Tous les codes, le texte libre à sa place, avant tout masquage — l'ordre
 *  des pastilles du réglage comme celui du pied de page. */
export function ordreComplet(texteApres: string): string[] {
	const ordre = [...AUTRES_CODES];
	ordre.splice(texteApres === '' ? 0 : ordre.indexOf(texteApres) + 1, 0, 'texte');
	return ordre;
}

/** Les codes affichés, dans l'ordre, une fois les masqués retirés — et le texte
 *  libre absent s'il est vide. */
export function elementsAffiches(r: ReglagePied): string[] {
	const retires = new Set(lireMasques(r.masques.join(',')));
	return ordreComplet(r.texteApres).filter(
		(c) => !retires.has(c) && (c !== 'texte' || r.texte.trim() !== ''),
	);
}

/**
 * Le texte libre avance (-1) ou recule (+1) d'un cran parmi les éléments
 * AFFICHÉS : passer derrière un élément masqué ne changerait rien à l'écran.
 * Rend la nouvelle valeur de `texteApres`, inchangée en bout de rangée.
 */
export function deplacerTexte(r: ReglagePied, sens: -1 | 1): string {
	const visibles = elementsAffiches({ ...r, texte: r.texte || ' ' });
	const i = visibles.indexOf('texte');
	const voisin = visibles[i + sens];
	if (i < 0 || voisin === undefined) return r.texteApres;
	if (sens === 1) return voisin;
	//  Avancer : se placer derrière l'élément qui précède le voisin, en tête sinon.
	return visibles[i - 2] ?? '';
}
