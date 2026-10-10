/**
 *  Les icônes d'action AU TRAIT — une décision de LISTE, pas de bouton.
 *
 *  ## Pourquoi (10/10/2026, maquette B « Gouttière »)
 *
 *  Sur une carte d'affaire, six émojis d'action de six couleurs : la couleur ne
 *  hiérarchisait plus rien. La maquette retenue les dessine au trait, en gris,
 *  Bleu Seine au survol — pour les AFFAIRES SEULEMENT (arbitré : les autres
 *  cartes du site gardent leurs émojis).
 *
 *  Les boutons sont partagés (`BoutonLien` sert toutes les cartes du site,
 *  `BoutonOptions` les annonces) : leur passer une prop de forme demanderait de
 *  la relayer à travers chaque carte. La LISTE pose donc un contexte, et
 *  `IconeAction` le lit : ce qui est rendu sous `ListeTickets` est au trait, le
 *  reste ne change pas. Un seul endroit décide, aucun bouton ne le recopie.
 */
import { getContext, setContext } from 'svelte';

const CLE = Symbol('actions-au-trait');

/** À appeler dans le composant de LISTE dont les cartes dessinent leurs actions au trait. */
export function poserActionsAuTrait(): void {
	setContext(CLE, true);
}

/** Vrai sous une liste qui l'a posé ; faux partout ailleurs. */
export function actionsAuTrait(): boolean {
	return getContext<boolean | undefined>(CLE) ?? false;
}
