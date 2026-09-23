//  L'onglet vit dans le CHEMIN (`/tickets/kanban`, `/tickets/archives`) :
//  `reroute` envoie ces adresses à cette page, et ce `load` le résout (#1092).
import { resoudreOnglet } from '$lib/deepLink';

export const load = ({ url }) => resoudreOnglet('mes-demandes', url);
