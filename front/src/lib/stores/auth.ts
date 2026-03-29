import { writable, derived } from 'svelte/store';
import type { User } from '$lib/api';
import { setActingAs } from '$lib/api';

export const currentUser = writable<User | null>(null);

/** Mandant actif si l'aidant agit en délégation (null = soi-même) */
export const actingAs = writable<{ mandant_id: number; mandant_nom: string } | null>(null);

// Synchroniser le header API quand actingAs change
actingAs.subscribe(($a) => setActingAs($a?.mandant_id ?? null));

export const isActingAsAidant = derived(actingAs, ($a) => $a !== null);

export const isAuthenticated = derived(currentUser, ($u) => $u !== null);

export const isAdmin = derived(currentUser, ($u) => !!$u?.roles?.includes('admin') || $u?.role === 'admin');

export const isCS = derived(
	currentUser,
	($u) =>
		!!$u?.roles?.includes('conseil_syndical') ||
		!!$u?.roles?.includes('admin') ||
		$u?.role === 'conseil_syndical' ||
		$u?.role === 'admin',
);

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

export function setUser(user: User | null) {
	currentUser.set(user);
}
