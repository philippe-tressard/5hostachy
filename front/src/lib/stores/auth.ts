import { writable, derived } from 'svelte/store';
import type { User } from '$lib/api';
import { setActingAs } from '$lib/api';
import {
	estBailleur,
	estCoproprietaire,
	estGestionnaire,
	estLocataire,
	estResident,
} from '$lib/roles';

export const currentUser = writable<User | null>(null);

/** Mandant actif si l'aidant agit en délégation (null = soi-même) */
export const actingAs = writable<{ mandant_id: number; mandant_nom: string } | null>(null);

// Synchroniser le header API quand actingAs change
actingAs.subscribe(($a) => setActingAs($a?.mandant_id ?? null));

export const isActingAsAidant = derived(actingAs, ($a) => $a !== null);

export const isAuthenticated = derived(currentUser, ($u) => $u !== null);

/**
 * Le pendant front de `Utilisateur.has_role` (`api/app/models/core.py`).
 *
 * Il n'en existait **aucun** : chaque store dérivé recomposait à la main la même
 * cascade `roles.includes(x) || role === x`, et chaque écran recomposait par
 * dessus sa propre condition de visibilité. Rien n'obligeait ces écritures à
 * rester d'accord entre elles, ni avec le serveur — c'est ce qu'a montré la
 * rangée de raccourcis du tableau de bord, où la règle « qui voit l'Espace CS »
 * était écrite une fois dans la page et une fois dans le calcul de son compteur
 * (#399).
 *
 * ⚠️ C'est une fonction, pas un store : elle se teste, se compose, et sert aussi
 * bien dans un `$:` que dans une table de configuration (`$lib/raccourcis.ts`).
 * Elle ne décide de **rien** côté serveur — le front n'est jamais le gardien
 * d'un droit, il n'en est que le reflet.
 */
export function aRole(user: User | null, ...roles: string[]): boolean {
	if (!user) return false;
	const portes: string[] = user.roles?.length ? user.roles : user.role ? [user.role] : [];
	return roles.some((r) => portes.includes(r));
}

export const isAdmin = derived(currentUser, ($u) => aRole($u, 'admin'));

export const isCS = derived(currentUser, ($u) => aRole($u, 'conseil_syndical', 'admin'));

// Vrai si l'utilisateur a au moins un rôle résidentiel (propriétaire, résident, ou aidant avec délégation active)
export const hasResidentRole = derived(currentUser, ($u) => {
	const roles: string[] = $u?.roles ?? ($u?.role ? [$u.role] : []);
	return roles.includes('propriétaire') || roles.includes('résident') || $u?.statut === 'aidant';
});

// Vrai si l'utilisateur a le rôle propriétaire
export const isProprio = derived(currentUser, ($u) => {
	const roles: string[] = $u?.roles ?? ($u?.role ? [$u.role] : []);
	return roles.includes('propriétaire');
});

// Vrai si l'utilisateur n'est QUE admin (sans rôle résidentiel ni CS)
export const isAdminOnly = derived(currentUser, ($u) => {
	const roles: string[] = $u?.roles ?? ($u?.role ? [$u.role] : []);
	const hasRes = roles.includes('propriétaire') || roles.includes('résident');
	const hasCS = roles.includes('conseil_syndical');
	const hasAdm = roles.includes('admin');
	return hasAdm && !hasRes && !hasCS;
});

// ─────────────────────────────────────────────────────────────────────────────
//  Ce que l'utilisateur COURANT est — des dérivées, pas des recopies
// ─────────────────────────────────────────────────────────────────────────────
//
//  🔴 Les écrans réinventaient ces dérivées, une par une :
//
//      $: isLocataire = $currentUser?.statut === 'locataire';
//
//  …écrit tel quel dans SIX fichiers (`OngletAcces`, `AccesConnexes`,
//  `calendrier`, `mon-lot`, `residence`, `tableau-de-bord`), alors que
//  `isCS`, `isAdmin` et `isProprio` vivaient ICI depuis toujours. La règle la
//  plus déployée existait ; ces écrans ne la suivaient pas.
//
//  ⚠️ Et `mon-lot` définissait sa propre `isLocataire` tout en recomposant le
//  test deux lignes plus loin : une duplication n'a pas besoin de traverser le
//  dépôt pour diverger.
//
//  🔒 La QUESTION est posée par `$lib/roles` (`estLocataire`…), pour qu'elle
//  serve aussi à une personne qui n'est pas l'utilisateur courant — un membre
//  de l'annuaire du conseil syndical. Ici on ne fait que l'appliquer au
//  courant. Deux endroits, deux rôles, une seule écriture de la règle.
//
//  ⚠️ Ces dérivées disent ce qu'on AFFICHE, jamais ce qu'on autorise : les
//  droits sont tranchés par le serveur (`auth/deps`).

export const isLocataire = derived(currentUser, estLocataire);
export const isBailleur = derived(currentUser, estBailleur);
export const isResident = derived(currentUser, estResident);
/** Copropriétaire, qu'il habite son lot ou le loue. */
export const isCoproprietaire = derived(currentUser, estCoproprietaire);
/** Syndic ou mandataire — il gère, il n'habite pas. */
export const isGestionnaire = derived(currentUser, estGestionnaire);

/**
 * L'état d'authentification est-il RÉSOLU ?
 *
 * Faux tant que `authApi.me()` n'a pas répondu — succès comme échec. À ne pas
 * confondre avec `isAuthenticated`, qui vaut faux dans **deux** cas très
 * différents : « pas connecté » et « on ne sait pas encore ».
 *
 * Cette distinction n'existait pas, et un garde d'accès la confondait :
 * `admin/+layout.svelte` testait `$isAdmin` dans son `onMount`, en même temps que
 * `(app)/+layout.svelte` chargeait l'utilisateur. Le garde décidait donc toujours
 * sur une valeur encore vide, et **toute adresse `/admin/**` ouverte directement
 * — lien partagé, favori, F5 — renvoyait au tableau de bord, y compris pour un
 * administrateur.** En navigation interne l'utilisateur était déjà chargé, d'où un
 * défaut invisible depuis toujours (trouvé le 12/08/2026 en vérifiant
 * `/admin/patrimoine` dans un navigateur).
 *
 * Un garde doit attendre de SAVOIR avant de refuser : ne rien rendre pendant
 * l'attente, refuser sur un « non » avéré, jamais sur un « pas encore ».
 */
export const authResolue = writable(false);

export function setUser(user: User | null) {
	currentUser.set(user);
	authResolue.set(true);
}

/** L'authentification a répondu, sans utilisateur (visiteur non connecté). */
export function marquerAuthResolue() {
	authResolue.set(true);
}
