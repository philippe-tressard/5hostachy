/**
 * Hooks du navigateur — une erreur d'un chargement ou d'une navigation (#1631).
 *
 * Ces erreurs-là, SvelteKit les rattrape pour afficher sa page d'erreur : elles
 * n'atteignent jamais les écouteurs `error` et `unhandledrejection` posés par
 * `initTelemetry`. Sans ce hook, un écran qui ne se charge plus ne laisserait
 * aucune trace côté serveur — c'est ce que #1631 vient fermer.
 *
 * Une 404 — une adresse inconnue — n'est pas une panne d'écran : elle n'est
 * pas signalée.
 */
import type { HandleClientError } from '@sveltejs/kit';
import { codeErreur, signalerErreur } from '$lib/telemetry';

export const handleError: HandleClientError = ({ error, status }) => {
	if (status !== 404) signalerErreur(codeErreur(error));
};
