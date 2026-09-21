/**
 * **Les gestes du site**, nommés une fois — et le mot que chacun remplace.
 *
 * ## 🔴 Pourquoi (#1094, chantier v2.0.0)
 *
 * Les trois gestes sont `Nouveau` · `Modifier` · **`Suite`**. « Commentaire »
 * est abandonné, et l'arbitrage du 20/09/2026 dit pourquoi :
 *
 * > Le cadre #430 avait tranché pour **Évolution** côté modèle, en notant :
 * > *« le cadre parle d'évolutions ; l'écran parle de gestes. "Ajouter une
 * > évolution" ne veut rien dire pour un résident. »* **« Suite » est le mot
 * > d'écran qui manquait**, et il vaut pour les deux objets.
 *
 * Le modèle garde `TicketEvolution` et `EvolForm` : c'est la même distinction
 * que `Ticket` / « Affaire » — le modèle garde son nom, l'écran parle français.
 *
 * ## Une source, parce que la leçon est fraîche
 *
 * « Commenter » était écrit **sept fois** dans les écrans, sous quatre formes
 * (« Commenter », « Commenter ou changer l'état », avec ou sans glyphe). C'est
 * exactement ce qui a produit #1107 : vingt libellés restés au vocabulaire
 * d'avant parce qu'aucun ne lisait de source commune.
 *
 * 🔒 `npm run lint:vocabulaire-ecran` lit `motAbandonne` ici même, comme il lit
 * `motDeCode` dans `entites/` : un geste renommé n'ajoutera qu'une ligne.
 */

/** Un geste de l'écran : ce qu'on lit, et ce qu'il ne doit plus dire. */
export interface GesteDeclare {
	/** Le libellé complet — celui d'un bouton ou d'un titre de boîte. */
	libelle: string;
	/** Sa forme courte, pour une infobulle ou une cible tactile étroite. */
	court: string;
	/**
	 * Le mot d'écran que ce geste REMPLACE, et que plus aucun libellé ne doit
	 * porter. Absent quand le geste n'a jamais changé de nom.
	 */
	motAbandonne?: string;
}

/**
 * **Ajouter une suite** — faire avancer une affaire, ou répondre à une
 * actualité.
 *
 * ⚠️ Le libellé ne dit plus « ou changer l'état », et ce n'est pas une perte :
 * sur une affaire, le bloc s'ouvre avec les **pastilles d'état en tête**
 * (#1095), donc le geste se montre au lieu de s'annoncer. Un libellé qui
 * énumère ce que le formulaire contient se dérive au premier champ ajouté —
 * c'est `project_libelle_qui_enumere_son_contenu`.
 */
export const SUITE: GesteDeclare = {
	libelle: 'Ajouter une suite',
	court: 'Suite',
	motAbandonne: 'Commenter',
};

/** Tous les gestes déclarés — ce que le garde-fou parcourt. */
export const GESTES: readonly GesteDeclare[] = [SUITE];
