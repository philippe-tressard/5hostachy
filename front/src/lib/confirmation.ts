import { mount, unmount } from 'svelte';

import Confirmation from '$lib/components/Confirmation.svelte';

/**
 * Demande confirmation, dans la charte du site. Rend `true` si l'on confirme.
 *
 * ```ts
 * if (!(await confirmer('Archiver cet événement ?'))) return;
 * if (!(await confirmer({ message: '…', libelleConfirmer: 'Supprimer', danger: true })))
 * 	return;
 * ```
 *
 * ⚠️ **La forme COURTE n'est pas un raccourci de confort.** Trente-cinq des
 * quarante appels d'origine ne portent qu'une phrase ; leur imposer un objet
 * aurait fait passer chacun de une ligne à cinq — et un geste de conversion qui
 * quintuple le code est un geste qu'on ne fait pas. Le contrôle de modularité
 * l'a refusé au premier écran converti, ce qui était la bonne réponse.
 *
 * ## Pourquoi un appel IMPÉRATIF et non un composant posé dans la page
 *
 * Quarante sites demandaient confirmation avec `confirm()` natif. Les convertir
 * en composant déclaratif aurait imposé, à chacun, un état d'ouverture, une
 * variable pour l'action en attente, et un gestionnaire — soit quarante fois le
 * même échafaudage, dans quarante écrans qui n'ont rien d'autre en commun.
 * C'est très exactement la duplication que ce lot retire.
 *
 * L'appel garde la forme d'origine : une ligne, une condition, un `return`.
 * Seul l'`await` s'ajoute.
 *
 * ⚠️ **Le composant est monté puis DÉMONTÉ à chaque appel**, et la promesse est
 * résolue une seule fois. Un composant laissé en place accumulerait un nœud par
 * geste, et un second `await` sur la même instance ne rendrait jamais la main.
 *
 * ⚠️ **Côté serveur, il n'y a pas de fenêtre.** Le rendu SSR ne demande rien à
 * personne : la fonction rend `false` — refuser est le comportement sûr, et un
 * `true` par défaut exécuterait le geste sans que quiconque l'ait vu.
 */
export function confirmer(
	options:
		| string
		| {
				titre?: string;
				message: string;
				libelleConfirmer?: string;
				libelleAnnuler?: string;
				danger?: boolean;
		  },
): Promise<boolean> {
	if (typeof options === 'string') options = { message: options };
	if (typeof document === 'undefined') return Promise.resolve(false);
	const opts = options;

	return new Promise((resoudre) => {
		const hote = document.createElement('div');
		document.body.appendChild(hote);
		let rendu = false;
		//  🔴 `mount()`, PAS `new Confirmation(...)` — corrigé le 30/08/2026.
		//
		//  Ce fichier montait le composant avec l'API Svelte 4. Le projet est en
		//  **Svelte 5**, où elle lève :
		//
		//      component_api_invalid_new — Attempted to instantiate
		//      Confirmation.svelte with `new Confirmation`, which is no longer
		//      valid in Svelte 5.
		//
		//  Conséquence : `confirmer()` n'a JAMAIS fonctionné. Les 17 gestes qui en
		//  dépendent — suppressions, archivages — levaient au lieu de demander, et
		//  l'action n'avait pas lieu.
		//
		//  ⚠️ Ce qui l'a rendu invisible : en production, le message est minifié
		//  en « Cannot use 'in' operator to search for 'Symbol($state)' in
		//  undefined » — illisible, et sans rapport apparent avec une boîte de
		//  dialogue. C'est l'utilisateur qui l'a signalé, sur un bouton qui « ne
		//  faisait rien ». Aucun contrôle du dépôt ne pouvait le voir : ils sont
		//  tous statiques, et cette ligne compile parfaitement.
		//
		//  🔒 `lint:api-svelte4` refuse désormais cette forme dans tout le front.
		const composant = mount(Confirmation, {
			target: hote,
			props: {
				titre: opts.titre ?? 'Confirmer',
				message: opts.message,
				libelleConfirmer: opts.libelleConfirmer ?? 'Confirmer',
				libelleAnnuler: opts.libelleAnnuler ?? 'Annuler',
				danger: opts.danger ?? false,
				onReponse: (ok: boolean) => {
					//  Une seule résolution : `Modale` émet `fermer` sur Échap ET sur
					//  le fond, et le bouton répond lui aussi. Sans ce verrou, le
					//  démontage serait tenté deux fois.
					if (rendu) return;
					rendu = true;
					//  `unmount()` remplace `$destroy()`, retiré en Svelte 5.
					unmount(composant);
					hote.remove();
					resoudre(ok);
				},
			},
		});
	});
}

/**
 * Les options d'une suppression DÉFINITIVE — rouge, et qui le dit.
 *
 * 🔴 Vingt-deux des quarante `confirm()` d'origine écrivaient une variante de
 * « Supprimer définitivement X ? Cette action est irréversible. » — même phrase,
 * ponctuation près, dans vingt-deux fichiers. C'est la duplication que ce lot
 * retire, et c'est aussi ce qui la rendait dangereuse : rien ne garantissait que
 * la vingt-troisième dirait « irréversible ».
 *
 * ⚠️ `danger: true` n'est pas décoratif. La boîte native donnait exactement le
 * même aspect à « archiver » — qui se défait — et à « supprimer » — qui ne se
 * défait pas. Le rouge est ce qui rétablit la différence.
 */
export function SUPPRESSION(quoi: string) {
	return {
		titre: 'Supprimer définitivement',
		message: `${quoi}

Cette action est irréversible.`,
		libelleConfirmer: 'Supprimer',
		danger: true,
	};
}
