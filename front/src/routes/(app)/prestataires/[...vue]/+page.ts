//  L'onglet vit dans le CHEMIN, pas dans un paramètre : c'est ce `load` qui le
//  résout, et lui seul. Le composant reçoit un onglet déjà validé — il n'a plus à
//  lire l'URL, ni à se demander quoi faire d'une valeur inconnue.
//
//  Le segment est un reste (`[...vue]`) et non un paramètre simple : la gestion
//  locative porte un sous-onglet (`/mon-lot/location/archives`), donc la
//  profondeur varie. Un chemin non déclaré rend une 404, pas le premier onglet.
import { resoudreOnglet } from '$lib/deepLink';

export const load = ({ url }) => resoudreOnglet('prestataires', url);
