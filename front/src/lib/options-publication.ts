/**
 * Les QUATRE options qui décrivent une publication — épinglage, urgence,
 * brouillon, confidentialité — déclarées **une seule fois**.
 *
 * ## Pourquoi ce fichier (29/08/2026)
 *
 * Ces quatre notions étaient écrites à **trois** endroits — les cases de
 * `OptionsPublication`, les badges de `CarteActualite`, et le bord rouge que la
 * carte pose pour l'urgence — et elles avaient **déjà divergé** :
 *
 *   • **Épinglage** : 📌 sur la carte (`pin-badge`) et dans
 *     `FormulaireEvenement`, mais **aucun glyphe** sur la case d'actualité, qui
 *     disait « Épingler » tout court. Trois écrans, deux vocabulaires ;
 *   • **Brouillon** : ✏️ — le crayon, qui est **déjà** l'icône « Modifier » de
 *     toutes les barres d'actions du site. Deux notions, un glyphe : c'est
 *     exactement ce que `standards/11` interdit, et cela devenait illisible le
 *     jour où les deux se retrouvaient côte à côte (c'est ce lot).
 *
 * Le glyphe du brouillon passe donc à **📝**, et ✏️ redevient « Modifier » et
 * rien d'autre. Ce n'est pas un changement d'humeur : c'est la levée d'une
 * ambiguïté qui préexistait.
 *
 * ## Deux registres, et il faut les deux
 *
 * Une case à cocher propose un GESTE (« Épingler ») ; un badge et un libellé
 * d'accessibilité énoncent un ÉTAT (« Épinglée »). Écrire l'un pour l'autre
 * donne « Options : épingler, confidentiel », qui ne se lit pas. La table porte
 * donc les deux, et personne n'a à les redériver.
 *
 * ⚠️ **L'ordre du tableau est l'ordre d'affichage**, partout : dans les cases,
 * dans les badges et dans le bouton d'options. Deux écrans qui énuméreraient les
 * mêmes options dans deux ordres se liraient comme deux listes différentes.
 */

/** Les clés sont celles du modèle serveur (`api/app/models/core.py`). */
export type CleOptionPublication = 'epingle' | 'urgente' | 'brouillon' | 'confidentiel';

export interface OptionPublication {
	cle: CleOptionPublication;
	/** Le glyphe, unique à cette notion dans tout le site. */
	glyphe: string;
	/** Le GESTE, pour une case à cocher : « Épingler ». */
	action: string;
	/** L'ÉTAT, pour un badge ou un libellé d'accessibilité : « Épinglée ». */
	etat: string;
	/** Ce que l'option fait, en une phrase — infobulles et aide. */
	aide: string;
}

export const OPTIONS_PUBLICATION: readonly OptionPublication[] = [
	{
		cle: 'epingle',
		glyphe: '\u{1F4CC}',
		action: 'Épingler',
		etat: 'Épinglée',
		aide: 'Maintenue en tête du fil d’activité.',
	},
	{
		cle: 'urgente',
		glyphe: '\u{1F6A8}',
		action: 'Marquer urgente',
		etat: 'Urgente',
		//  L'urgence se rend par un BORD ROUGE sur la carte, jamais par un badge
		//  texte — décision d'affichage antérieure, conservée telle quelle.
		aide: 'Signalée par un bord rouge sur la carte.',
	},
	{
		//  🔴 LA MÊME NOTION DES DEUX CÔTÉS (05/09/2026), arbitrée à l'écran :
		//  « Fusion de ces 2 en 🛡️ Visibilité du ticket au seul conseil syndical ».
		//
		//  Elle s'appelait « Garder en brouillon » sur une actualité et
		//  « Confidentiel » sur un ticket — deux mots, deux glyphes, un seul effet
		//  observable : **seul le conseil syndical le voit**. Deux noms pour une même
		//  notion, c'est deux occasions de croire à deux règles.
		//
		//  ⚠️ La CLÉ reste `brouillon` : c'est la colonne d'une actualité, et la
		//  renommer n'apprendrait rien à personne. Le ticket y branche sa colonne
		//  `confidentiel` — voir la prop `objet` d'`OptionsPublication`.
		cle: 'brouillon',
		glyphe: '\u{1F6E1}️',
		action: 'Visibilité du {objet} au seul conseil syndical',
		etat: 'Conseil syndical',
		aide: 'Seul le conseil syndical le voit ; aucun envoi n’est déclenché.',
	},
	{
		cle: 'confidentiel',
		glyphe: '\u{1F512}',
		action: 'Rendre confidentielle',
		etat: 'Confidentielle',
		aide: 'Visible des seuls résidents du périmètre sélectionné.',
	},
] as const;

/**
 * Le libellé d'action d'une option, pour l'objet qu'elle décrit.
 *
 * Certaines actions nomment l'objet — « Visibilité du **ticket** au seul conseil
 * syndical » — parce que la même case sert deux entités et que « ce truc-là » ne
 * se dit pas. Le gabarit vit dans la table ; le mot vient de l'appelant, seul à
 * savoir ce qu'il rend.
 */
export function actionOption(option: OptionPublication, objet: string): string {
	return option.action.replace('{objet}', objet);
}

/** L'option d'une clé, ou `undefined` — utile pour un rendu piloté par la donnée. */
export function optionPublication(cle: CleOptionPublication): OptionPublication | undefined {
	return OPTIONS_PUBLICATION.find((o) => o.cle === cle);
}

/**
 * Les options ACTIVES d'une publication, dans l'ordre de la table.
 *
 * ⚠️ Le test est `=== true`, et non la véracité de la valeur : l'API peut
 * renvoyer `undefined` pour un champ absent, et `!!undefined` vaut `false` — mais
 * `!!'false'` vaudrait `true` si la valeur arrivait un jour en chaîne. On
 * n'accepte que le booléen vrai.
 */
export function optionsActives(
	pub: Partial<Record<CleOptionPublication, boolean | undefined>>,
): OptionPublication[] {
	return OPTIONS_PUBLICATION.filter((o) => pub[o.cle] === true);
}

/**
 * « Options : épinglée, confidentielle » — le libellé d'accessibilité du bouton.
 *
 * Rend une chaîne vide quand rien n'est actif : l'appelant n'affiche alors pas le
 * bouton, et un `aria-label` vide vaudrait mieux qu'un « Options : » orphelin.
 */
export function libelleOptionsActives(
	pub: Partial<Record<CleOptionPublication, boolean | undefined>>,
): string {
	const actives = optionsActives(pub);
	if (actives.length === 0) return '';
	return `Options : ${actives.map((o) => o.etat.toLocaleLowerCase('fr')).join(', ')}`;
}

/**
 * 🔴 Le motif qui INTERDIT le groupe WhatsApp — vide quand rien ne l'interdit.
 *
 * > « si "Visibilité du ticket au seul conseil syndical" est sélectionné, la
 * > diffusion WhatsApp est interdite » (05/09/2026)
 *
 * Le groupe rassemble **tous les résidents** : un objet qu'on vient de réserver
 * au conseil syndical ne peut pas y être recopié — la case cochée dans l'écran
 * promettrait une confidentialité que le canal annulerait aussitôt.
 *
 * La règle est écrite **une fois, ici**, parce qu'elle vaut pour toute entité
 * portant l'option `brouillon` — actualité comme ticket — et qu'elle se lit
 * dans quatre écrans : *« faire ces évolutions au niveau de l'objet pour ne
 * pas dupliquer le code »*.
 *
 * ⚠️ **Ce n'est pas le contrôle.** Le serveur refuse l'envoi de son côté
 * (`api/tests/test_canaux_notification.py`) : `partager_whatsapp` est un champ
 * du corps de la requête, qui se poste sans passer par l'écran.
 */
export function motifWhatsappInterdit(reserveAuConseil: boolean, objet = 'publication'): string {
	if (!reserveAuConseil) return '';
	const option = optionPublication('brouillon');
	return (
		`${option?.glyphe ?? ''} Le groupe WhatsApp rassemble tous les résidents : ` +
		`impossible d’y partager un ${objet} réservé au conseil syndical.`
	);
}
