import { mount, unmount } from 'svelte';
import type { Component } from 'svelte';

/**
 * **Poser une modale et attendre sa réponse** — le mécanisme, écrit une fois.
 *
 * ## Pourquoi ce fichier
 *
 * `confirmer()` montait son composant à la main : créer un hôte, `mount()`,
 * attendre `onReponse`, `unmount()`, retirer l'hôte, résoudre une seule fois.
 * Vingt lignes d'échafaudage, et **quatre pièges** qui ne se voient pas à la
 * relecture. Écrire une deuxième modale impérative (`demander()`) aurait
 * recopié les vingt lignes **et** les quatre pièges :
 *
 * 1. 🔴 `mount()`, **jamais** `new Composant(...)` — le projet est en Svelte 5,
 *    où l'API 4 lève `component_api_invalid_new`. La faute a existé ici : pendant
 *    des semaines, `confirmer()` n'a jamais fonctionné, et dix-sept gestes
 *    levaient au lieu de demander. En production le message était minifié en
 *    « Cannot use 'in' operator… », illisible et sans rapport apparent.
 *    🔒 `lint:api-svelte4` refuse désormais cette forme.
 * 2. **Une seule résolution** : `Modale` émet `fermer` sur Échap ET sur le fond,
 *    et les boutons répondent aussi. Sans verrou, le démontage serait tenté deux
 *    fois.
 * 3. **Monter puis DÉMONTER à chaque appel** : un composant laissé en place
 *    accumulerait un nœud par geste, et un second `await` sur la même instance
 *    ne rendrait jamais la main.
 * 4. **Côté serveur, il n'y a pas de fenêtre.** Le rendu SSR ne demande rien à
 *    personne : on rend la réponse de refus. Un défaut « accepté » exécuterait
 *    le geste sans que quiconque l'ait vu.
 *
 * @param composant  La modale à monter — elle reçoit `onReponse` en plus de ses
 *                   propres props, et l'appelle une fois.
 * @param props      Ses props, `onReponse` exclue.
 * @param refus      Ce qu'on rend quand il n'y a pas de fenêtre (SSR).
 */
export function modaleImperative<R>(
	//  ⚠️ `Component<any>` et non `Component<Record<string, unknown>>` : les props
	//  d'un composant sont en position CONTRAVARIANTE, donc un type de props plus
	//  large n'est pas assignable — `svelte-check` refuse les deux appelants. Ce
	//  fichier ne lit aucune prop, il les transmet ; c'est l'appelant typé
	//  (`confirmer`, `demander`) qui garantit qu'elles correspondent.
	composant: Component<any>,
	props: Record<string, unknown>,
	refus: R,
): Promise<R> {
	if (typeof document === 'undefined') return Promise.resolve(refus);

	return new Promise((resoudre) => {
		const hote = document.createElement('div');
		document.body.appendChild(hote);
		let rendu = false;
		const instance = mount(composant, {
			target: hote,
			props: {
				...props,
				onReponse: (reponse: R) => {
					if (rendu) return;
					rendu = true;
					//  `unmount()` remplace `$destroy()`, retiré en Svelte 5.
					unmount(instance);
					hote.remove();
					resoudre(reponse);
				},
			},
		});
	});
}
