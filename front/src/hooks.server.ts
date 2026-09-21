import type { Handle } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
	//  L'authentification est portée par des cookies `HttpOnly` que ce hook
	//  n'inspecte pas : il laisse passer, et c'est voulu.
	//
	//  🔴 Il a longtemps affirmé que « la protection des routes se fait dans
	//  +page.server.ts de chaque section ». C'était FAUX : deux fichiers
	//  seulement en portent une (`routes/` et `prestataires/`), et elle n'y sert
	//  qu'à éviter deux appels d'API à un visiteur manifestement déconnecté.
	//
	//  La protection réelle est ailleurs, et à trois niveaux :
	//    • `(app)/+layout.svelte` — la garde centrale, qui charge l'utilisateur
	//      et renvoie à la mire en conservant la page demandée ;
	//    • les gardes d'écran, qui attendent `$authResolue` avant de refuser
	//      sur un rôle (`check-gardes-auth.mjs`) ;
	//    • **l'API**, seule à décider pour de bon : un écran masqué n'est pas
	//      un accès refusé (`standards/03` §1).
	//
	//  ⚠️ Un commentaire qui décrit une protection inexistante est pire qu'un
	//  silence : il se lit comme une garantie (#1083, 22/09/2026).
	return resolve(event);
};
