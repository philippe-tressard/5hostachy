<!--
  DiffusionPublication.svelte — ce qu'une actualité ENVOIE : les trois canaux et
  l'affiche de hall. **Section 9 du cadre #430**, et elle seule.

  Née le 18/08/2026 (#433) de la coupure d'`OptionsPublication`, qui portait à la
  fois ce qui décrit une publication (épinglage, urgence, brouillon,
  confidentialité) et ce qui l'envoie, sous un drapeau `complet` réservant le
  second à la création. Le cadre a rendu ce mélange intenable : *les sections 1 à 8
  décrivent l'entité, la 9 est un acte*, et l'édition n'a pas la 9 — parce qu'*une
  correction n'est pas une nouvelle*, et que rejouer un canal à chaque faute de
  frappe rattrapée est l'incident du triple envoi WhatsApp du 14/08/2026.

  Le drapeau a disparu avec la coupure, et c'est le point : tant qu'il existait,
  la question « cet écran est-il complet ? » se reposait à chaque appelant. Elle
  se lit maintenant dans la déclaration — `sectionPresente(PUBLICATION, etat,
  'diffusion')` —, une fois, avec son motif.

  ⚠️ **L'affiche de hall n'est pas un canal de notification** : elle produit un
  PDF punaisé dans un hall, lu sans connexion. Elle reste donc hors de
  `CanauxNotification`, dont le contrat est « qui est prévenu ? ».

  ⚠️ **« Confidentiel » interdit l'affiche de hall**, et la case le montre. La
  valeur arrive en lecture seule : la règle qui la fait retomber vit chez l'hôte
  (`FormulaireActualite`), seul endroit où les sections 2 et 9 se rencontrent — et
  elle est **aussi** tenue côté serveur (`appliquer_confidentialite`), qui seul
  décide.
-->
<script lang="ts">
	import CanauxNotification from './CanauxNotification.svelte';

	export let whatsapp = false;
	export let syndic = false;
	export let cs = false;
	export let annonceHall = false;
	/** Lecture seule : décidée en section 2, elle ferme l'affiche de hall ici. */
	export let confidentiel = false;

	const idAideHall = `aide-hall-${Math.random().toString(36).slice(2, 8)}`;
</script>

<CanauxNotification
	bind:whatsapp
	bind:syndic
	bind:cs
	aideWhatsapp={confidentiel
		? "Le groupe est commun à toute la copropriété : le message ne portera ni le titre ni le contenu, seulement le périmètre concerné et un lien vers l'application."
		: "Le message est publié sur le groupe WhatsApp ; l'image jointe part avec."}
/>

<div class="bloc-hall">
	<label
		class="checkbox-field"
		class:desactivee={confidentiel}
		title={confidentiel
			? "Indisponible : une actualité confidentielle ne peut pas être affichée dans un hall."
			: "Génère l'affiche PDF à afficher dans le hall et l'envoie au CS du périmètre"}
	>
		<input
			type="checkbox"
			bind:checked={annonceHall}
			disabled={confidentiel}
			aria-describedby={confidentiel ? idAideHall : undefined}
		/>
		<span class="ico">&#x1F4C4;</span>
		<span>Créer une annonce Hall</span>
	</label>
</div>

{#if confidentiel}
	<p class="aide" id={idAideHall}>
		&#x1F4C4; L'affiche de hall est indisponible sur une actualité confidentielle : une
		affiche est punaisée dans un hall et lue par n'importe qui, sans connexion. Le message
		WhatsApp, lui, reste possible — il renvoie vers l'application, qui applique la règle.
	</p>
{:else if annonceHall}
	<p class="aide">
		&#x1F4C4; Une affiche PDF sera générée à partir du titre, du contenu, du périmètre et de
		l'image de cette actualité, puis envoyée aux membres du CS du périmètre. Elle sera
		consultable dans <strong>Espace CS → Annonces Hall</strong>. Un brouillon ne déclenche
		rien tant qu'il n'est pas publié.
	</p>
{/if}

<style>
	/*  `:global` parce que `.checkbox-field` est une classe partagée du thème —
	    même raison que dans `CanauxNotification.svelte`. */
	.bloc-hall :global(.checkbox-field) {
		display: flex;
		align-items: center;
		gap: .4rem;
		font-size: .875rem;
		cursor: pointer;
	}
	/*  Une case grisée doit se VOIR grisée, pas seulement refuser le clic. */
	.bloc-hall .desactivee {
		opacity: .5;
		cursor: not-allowed;
	}
	.bloc-hall {
		margin-bottom: 1rem;
	}
	.ico {
		font-size: 1.1em;
		line-height: 1;
	}
	.aide {
		font-size: .78rem;
		color: var(--color-text-muted);
		margin: -.5rem 0 1rem;
		line-height: 1.45;
	}
	@media (max-width: 480px) {
		.bloc-hall :global(.checkbox-field) {
			min-height: 44px;
		}
	}
</style>
