<script lang="ts">
	import { onMount } from 'svelte';

	// Bandeau « nouvelle version disponible ».
	//
	// Pourquoi (26/07/2026) : l'application est une PWA dont le service worker met
	// l'app shell en cache. Le contrôle de mise à jour n'a lieu qu'au chargement de
	// la page — un onglet laissé ouvert sert donc indéfiniment la version chargée le
	// matin. Constaté le jour de la MEP v2.23.0 : le footer annonçait encore
	// `v2.22.8-050e91c` une heure après le déploiement, sur un onglet resté ouvert.
	// Ce n'était pas qu'un affichage trompeur : v2.23.0 était un correctif de
	// sécurité, et le client continuait à exécuter le code d'avant.
	//
	// Deux manques comblés ici : personne n'était averti, et rien ne cherchait la
	// mise à jour. Le rechargement reste déclenché par l'utilisateur — un reload
	// imposé en pleine saisie ferait perdre un formulaire en cours.
	const INTERVALLE_MS = 30 * 60 * 1000;

	let disponible = false;
	let rechargement = false;
	let appliquer: ((reloadPage?: boolean) => Promise<void>) | null = null;

	function recharger() {
		if (!appliquer) return;
		rechargement = true;
		// Active le service worker en attente ; la page se recharge ensuite d'elle-même
		void appliquer();
	}

	onMount(() => {
		let annule = false;
		let arreter: (() => void) | undefined;

		// Import dynamique : le module virtuel n'existe qu'au build (stub inerte en
		// `vite dev`), et rien ne doit s'exécuter côté serveur au rendu SSR.
		import('virtual:pwa-register').then(({ registerSW }) => {
			if (annule) return;

			appliquer = registerSW({
				immediate: true,
				onNeedRefresh() {
					disponible = true;
				},
				onRegisteredSW(_url, registration) {
					if (!registration) return;

					const verifier = () => {
						// Hors ligne, `update()` échoue sans rien apprendre
						if (navigator.onLine) void registration.update();
					};
					const minuteur = setInterval(verifier, INTERVALLE_MS);

					// Cas principal : l'onglet a passé la nuit en arrière-plan
					const auRetour = () => {
						if (document.visibilityState === 'visible') verifier();
					};
					document.addEventListener('visibilitychange', auRetour);

					arreter = () => {
						clearInterval(minuteur);
						document.removeEventListener('visibilitychange', auRetour);
					};
				},
			});
		});

		return () => {
			annule = true;
			arreter?.();
		};
	});
</script>

{#if disponible}
	<div class="maj-bandeau" role="status" aria-live="polite">
		<span class="maj-texte">Une nouvelle version de l'application est disponible.</span>
		<div class="maj-actions">
			<button type="button" class="btn btn-sm btn-outline" on:click={() => (disponible = false)}>
				Plus tard
			</button>
			<button
				type="button"
				class="btn btn-sm btn-primary"
				disabled={rechargement}
				on:click={recharger}
			>
				{rechargement ? 'Rechargement…' : 'Recharger'}
			</button>
		</div>
	</div>
{/if}

<style>
	.maj-bandeau {
		position: fixed;
		bottom: 1rem;
		left: 50%;
		transform: translateX(-50%);
		z-index: 9998; /* juste sous les toasts (9999) */
		display: flex;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
		justify-content: center;
		max-width: min(560px, calc(100vw - 2rem));
		padding: .75rem 1rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-left: 4px solid var(--color-primary);
		border-radius: var(--radius);
		box-shadow: var(--shadow);
		font-size: .875rem;
		color: var(--color-text);
	}

	.maj-texte { flex: 1 1 auto; }

	.maj-actions {
		display: flex;
		gap: .5rem;
		flex: 0 0 auto;
	}
</style>
