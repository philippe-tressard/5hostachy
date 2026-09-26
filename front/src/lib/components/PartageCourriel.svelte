<!--
  « L'envoyer par courriel » — la SUITE du toast « Lien copié » (#1357).

  Option E des maquettes du 26/09/2026 : le clic sur 🔗 garde son effet (le lien
  est copié), et le message de confirmation propose l'envoi. Le lien d'abord,
  le champ ensuite : qui ne veut que copier ne voit rien de plus.

  Ce qui part, et à qui, est décidé par le serveur (`routers/tickets/partage`) :
  titre, numéro et lien, à qui peut LIRE l'affaire, sous plafond. L'écran ne
  valide l'adresse que pour dire tout de suite ce qui manque.
-->
<script lang="ts">
	import { createEventDispatcher, tick } from 'svelte';
	import { tickets as ticketsApi } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';

	/** L'affaire transmise. */
	export let ticketId: number;
	/** Le bouton 🔗 qui a ouvert le message : Échap lui rend le focus. */
	export let retour: HTMLElement | null = null;

	const dispatch = createEventDispatcher<{ fermer: void }>();
	let ouvert = false;
	let email = '';
	let erreur = '';
	let envoye = '';
	let enCours = false;
	let champ: HTMLInputElement;

	const complete = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim());

	async function ouvrir() {
		ouvert = true;
		await tick();
		champ?.focus();
	}

	async function envoyer() {
		if (!complete(email)) {
			erreur = 'Cette adresse n’est pas complète : il manque l’@ ou le domaine.';
			champ?.focus();
			return;
		}
		enCours = true;
		erreur = '';
		try {
			await ticketsApi.partager(ticketId, email.trim());
			envoye = `Envoyé à ${email.trim()}`;
		} catch (e) {
			erreur = messageErreur(e, 'L’envoi n’a pas abouti.');
		} finally {
			enCours = false;
		}
	}

	function clavier(e: KeyboardEvent) {
		if (e.key !== 'Escape') return;
		dispatch('fermer');
		retour?.focus();
	}
</script>

<div class="partage">
	{#if envoye}
		<p class="envoye" role="status">✓ {envoye}</p>
	{:else if !ouvert}
		<button type="button" class="lien-suite" on:click={ouvrir} on:keydown={clavier}
			>✉️ L’envoyer par courriel</button
		>
	{:else}
		<form class="formulaire" on:submit|preventDefault={envoyer} novalidate>
			<!--  `.field` porte la peau du champ et son focus (`champs.css`). -->
			<div class="field">
				<input
					bind:this={champ}
					type="email"
					bind:value={email}
					on:input={() => (erreur = '')}
					placeholder="prenom.nom@exemple.fr"
					autocomplete="email"
					aria-label="Adresse du destinataire"
					aria-invalid={!!erreur}
					on:keydown={clavier}
				/>
			</div>
			<button type="submit" class="btn btn-primary btn-sm" disabled={enCours}>
				{enCours ? 'Envoi…' : 'Envoyer'}
			</button>
		</form>
		{#if erreur}<p class="erreur" role="alert">{erreur}</p>{/if}
	{/if}
</div>

<style>
	.partage {
		margin-top: 0.4rem;
	}
	.lien-suite {
		border: 0;
		background: none;
		padding: 0.35rem 0;
		min-height: 36px;
		font: inherit;
		font-weight: 700;
		color: inherit;
		text-decoration: underline;
		text-underline-offset: 3px;
		cursor: pointer;
	}
	.formulaire {
		display: flex;
		gap: 0.4rem;
	}
	.formulaire .field {
		flex: 1;
		min-width: 0;
		margin: 0;
	}
	.erreur {
		margin: 0.3rem 0 0;
		color: var(--color-danger);
	}
	.envoye {
		margin: 0.2rem 0 0;
		font-weight: 600;
	}
	/*  Presser répond tout de suite (`emil-design-eng`) — sans bouger au doigt
	    ni animer quand l'appareil le demande. */
	.lien-suite:active {
		transform: scale(0.97);
	}
	@media (prefers-reduced-motion: reduce) {
		.lien-suite:active {
			transform: none;
		}
	}
</style>
