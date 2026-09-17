<!--
  L'assistant IA de la section Description (#985, 17/09/2026) — retravailler
  le titre et le texte saisis, selon le prompt réglé dans Admin → Assistant IA.

  ## Le geste

  Un bouton ✨ sous l'éditeur, une « précision » facultative (« plus court »,
  « plus formel »), et la PROPOSITION s'affiche sous le champ avec « Appliquer »
  et « Ignorer » : le formulaire ne change qu'à l'application, et rien n'est
  enregistré tant que l'auteur n'enregistre pas. Le geste se rejoue à volonté,
  chaque appel partant du texte COURANT.

  ## Ce que l'écran dit, et ce qu'il ne décide pas

  - Il SIGNALE ce qui change (« Titre modifié », « Description modifiée ») pour
    que l'auteur pense à relire — c'est le SERVEUR qui l'a calculé, sur du
    texte normalisé ; comparer du HTML ici dirait « modifié » à chaque espace.
  - Il ne se montre qu'au conseil syndical et à l'administration (`$isCS`), et
    seulement si le serveur dit l'usage disponible (`stores/assistant`). Le
    droit, lui, est tenu par la route : l'icône masquée n'est qu'un confort.
  - Le titre et la description sont LIÉS (`bind:`) : la section Description
    ne connaît pas le titre, c'est le formulaire qui le lui prête pour ce
    geste — et qui le reçoit corrigé par le même lien.
  - `assiste` passe à vrai à l'application : c'est ce que le formulaire envoie
    en `assiste_ia`, et ce que la carte rend ensuite par `MarqueIA`.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { isCS } from '$lib/stores/auth';
	import { assistantStore, chargerAssistant } from '$lib/stores/assistant';
	import { assistant as assistantApi, type PropositionDescription } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { safeHtml } from '$lib/sanitize';
	import { peutSolliciter, type ContexteAssistant } from '$lib/assistant';
	import { toast } from '$lib/components/Toast.svelte';

	/** L'entité et son contexte — composés par le formulaire (`$lib/assistant`). */
	export let contexte: ContexteAssistant;
	/** Préfixe des `id` : plusieurs sections Description coexistent à l'écran. */
	export let idPrefixe: string;
	/** Le titre de l'objet, prêté par le formulaire. Ignoré si `avecTitre` est faux. */
	export let titre = '';
	export let description = '';
	/** Faux sur une entrée de fil : un commentaire n'a pas de titre à proposer. */
	export let avecTitre = true;
	/** Devient vrai quand une proposition est appliquée — lu par le formulaire. */
	export let assiste = false;

	let precision = '';
	let enCours = false;
	let proposition: PropositionDescription | null = null;

	//  🔴 Visible pour le CS seulement, et seulement si le serveur dit oui. Le
	//  store n'est interrogé QUE pour le CS : la route refuse aux autres.
	$: visible = $isCS && $assistantStore?.description === true;
	$: solliciteable = peutSolliciter(avecTitre ? titre : '', description) && !enCours;
	$: rienChange =
		proposition !== null && !proposition.titre_modifie && !proposition.description_modifiee;

	onMount(() => {
		if ($isCS && $assistantStore === null) void chargerAssistant();
	});

	async function solliciter() {
		if (!solliciteable) return;
		enCours = true;
		try {
			proposition = await assistantApi.description({
				entite: contexte.entite,
				titre: avecTitre ? titre : null,
				description,
				contexte: contexte.contexte,
				precision: precision.trim() || null,
				avec_titre: avecTitre,
			});
		} catch (e) {
			toast('error', messageErreur(e, 'L’assistant n’a pas répondu.'));
		} finally {
			enCours = false;
		}
	}

	function appliquer() {
		if (!proposition) return;
		if (avecTitre && proposition.titre_modifie && proposition.titre) titre = proposition.titre;
		if (proposition.description_modifiee) description = proposition.description;
		if (proposition.titre_modifie || proposition.description_modifiee) assiste = true;
		proposition = null;
	}

	function ignorer() {
		proposition = null;
	}
</script>

{#if visible}
	<div class="assistant">
		<div class="assistant-commande">
			<button
				class="btn btn-outline btn-sm"
				type="button"
				disabled={!solliciteable}
				aria-busy={enCours}
				on:click={solliciter}
			>
				{enCours ? '✨ L’assistant travaille…' : '✨ Retravailler avec l’assistant'}
			</button>
			<label class="field champ-en-ligne assistant-precision">
				Précision
				<input
					id="{idPrefixe}-assistant-precision"
					type="text"
					bind:value={precision}
					maxlength="500"
					placeholder="plus court, plus formel…"
					disabled={enCours}
				/>
			</label>
		</div>
		<p class="aide">
			{#if !solliciteable && !enCours}
				Saisissez un titre ou une description : l’assistant retravaille ce qui est écrit.
			{:else}
				L’assistant propose, vous relisez : rien ne change tant que vous n’appliquez pas. Vous
				pouvez le solliciter plusieurs fois.
			{/if}
		</p>

		{#if proposition}
			<section class="assistant-proposition" aria-label="Proposition de l’assistant">
				<h5 class="assistant-titre">
					Proposition de l’assistant
					{#if proposition.titre_modifie}<span class="badge badge-orange">Titre modifié</span>{/if}
					{#if proposition.description_modifiee}<span class="badge badge-orange"
							>Description modifiée</span
						>{/if}
				</h5>
				{#if rienChange}
					<p class="aide">L’assistant n’a rien changé au texte.</p>
				{:else}
					{#if avecTitre && proposition.titre_modifie && proposition.titre}
						<p class="assistant-titre-propose">{proposition.titre}</p>
					{/if}
					{#if proposition.description_modifiee}
						<div class="rich-content assistant-texte">
							{@html safeHtml(proposition.description)}
						</div>
					{/if}
				{/if}
				<div class="assistant-actions">
					<button class="btn btn-outline btn-sm" type="button" on:click={ignorer}>Ignorer</button>
					{#if !rienChange}
						<button class="btn btn-primary btn-sm" type="button" on:click={appliquer}
							>Appliquer</button
						>
					{/if}
				</div>
			</section>
		{/if}
	</div>
{/if}

<style>
	.assistant {
		margin-top: 0.5rem;
	}
	.assistant-commande {
		display: flex;
		align-items: flex-end;
		gap: 0.6rem;
		flex-wrap: wrap;
	}
	.assistant-precision {
		flex: 1 1 14rem;
		margin: 0;
	}
	/*  La proposition se lit comme un encart : fond de surface, bordure fine,
	    jamais le fond de saisie — ce n'est pas un champ, on ne l'édite pas ici. */
	.assistant-proposition {
		margin-top: 0.6rem;
		padding: 0.7rem 0.85rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}
	.assistant-titre {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-wrap: wrap;
		margin: 0 0 0.5rem;
		font-size: 0.8rem;
		font-weight: 700;
	}
	.assistant-titre-propose {
		margin: 0 0 0.4rem;
		font-weight: 600;
	}
	.assistant-texte {
		font-size: 0.875rem;
		line-height: 1.6;
	}
	.assistant-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		margin-top: 0.6rem;
	}
</style>
