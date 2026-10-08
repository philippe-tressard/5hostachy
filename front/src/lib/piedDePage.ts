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
 * l'onglet `OngletSite.svelte`.
 */
import { NOM_PLATEFORME } from '$lib/plateforme';

export interface ElementPied {
	code: string;
	/** Le nom de l'élément dans le réglage de l'administration. */
	libelle: string;
	/** Pourquoi l'élément ne se masque pas. S'il est absent, il se masque. */
	verrouille?: string;
}

/** Les éléments du pied de page, dans leur ordre d'affichage. */
export const ELEMENTS_PIED: readonly ElementPied[] = [
	{ code: 'annee', libelle: '© Année' },
	{ code: 'residence', libelle: 'Nom de la résidence' },
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

/** Les codes affichés, dans l'ordre, une fois les masqués retirés. */
export function elementsAffiches(masques: readonly string[]): string[] {
	const retires = new Set(lireMasques(masques.join(',')));
	return ELEMENTS_PIED.map((e) => e.code).filter((c) => !retires.has(c));
}
