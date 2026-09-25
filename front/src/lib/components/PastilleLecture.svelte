<!--
  La PASTILLE DE LECTURE d'une carte — qui d'autre lit cette affaire
  (lot 1, arbitré le 25/09/2026, maquette « Anneau de lecture »).

  - **Une seule couleur**, celle des badges bleus du site ; les icônes sont
    celles des pastilles de Destinataires.
  - **Court sur la carte** (« Copropriétaires », « CS »), la phrase entière
    dans une bulle qui s'ouvre AU TOUCHER : au doigt il n'y a pas de survol, et
    l'infobulle native ne s'y montre pas (leçon du 07/09/2026). À la souris,
    la même phrase est AUSSI dans le `title` (#1311) : elle ne remplace pas
    la bulle, elle évite le clic.
  - **Rien** quand personne n'est exclu — comme le 🔹 du périmètre par défaut.
  - Elle remplace les badges 🔒 « Confidentielle » et 🛡️ « Conseil syndical » :
    le cadenas s'ajoute à droite quand le périmètre est réservé, et « CS » dit
    le reste. Le 🔹 reste à côté : c'est LUI qui dit lequel.

  Le calcul vit dans `$lib/lecture` — tenu contre la règle du serveur par
  `lint:lecture` et `test_lecture_pastille.py`. Ici, seulement le rendu.
-->
<script lang="ts">
	import ContenuBadge from '$lib/components/ContenuBadge.svelte';
	import { lectureDuTicket } from '$lib/lecture-ticket';
	import { titreLecture } from '$lib/lecture';
	import { perimetresStore } from '$lib/stores/perimetres';
	import { relire } from '$lib/utils';
	import type { Ticket } from '$lib/api';

	export let ticket: Ticket;

	//  `$perimetresStore` : l'arbre dit si le périmètre est restreint, et il
	//  arrive après la carte (#947, voir `BadgePerimetre`).
	$: lecture = relire($perimetresStore, () => lectureDuTicket(ticket));
	$: titre = titreLecture(lecture);
	let ouverte = false;
	const idBulle = `lecture-${Math.random().toString(36).slice(2, 8)}`;
</script>

<svelte:window
	on:click={() => (ouverte = false)}
	on:keydown={(e) => {
		if (e.key === 'Escape') ouverte = false;
	}}
/>

{#if !lecture.parDefaut}
	<span class="pastille-lecture">
		<!--  Le clic ne déplie pas la carte : la pastille est un geste à elle. -->
		<button
			type="button"
			class="badge badge-blue pastille-lecture-bouton"
			aria-expanded={ouverte}
			aria-controls={idBulle}
			aria-label="Qui la lit : {titre}. {lecture.phrase}"
			title="{titre} — {lecture.phrase} {lecture.exclus}"
			on:click|stopPropagation={() => (ouverte = !ouverte)}
			on:keydown|stopPropagation
		>
			<ContenuBadge
				icones={lecture.icones}
				texte={lecture.court}
				icone={lecture.perimetreReserve ? 'lock' : ''}
			/>
		</button>
		<span class="pastille-lecture-bulle" id={idBulle} role="status" hidden={!ouverte}>
			<strong>{titre}</strong>
			{lecture.phrase}
			{lecture.exclus}
		</span>
	</span>
{/if}

<style>
	.pastille-lecture {
		position: relative;
		display: inline-flex;
		min-width: 0;
	}
	.pastille-lecture-bouton {
		border: none;
		cursor: pointer;
		/*  `font-family` et non `font: inherit` : le raccourci réinitialisait la
		    taille et la graisse du `.badge` — la pastille se lisait plus grande
		    que ses voisines (#1308). */
		font-family: inherit;
		line-height: inherit;
		min-width: 0;
		max-width: 100%;
	}
	/*  La bulle reste dans la carte : ancrée à gauche, bornée à la largeur de
	    l'écran moins la gouttière, jamais un défilement horizontal. */
	.pastille-lecture-bulle {
		position: absolute;
		top: calc(100% + 0.3rem);
		left: 0;
		z-index: 5;
		width: max-content;
		max-width: min(18rem, calc(100vw - 2rem));
		padding: 0.5rem 0.65rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface, #fff);
		box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
		font-size: 0.78rem;
		line-height: 1.4;
		color: var(--color-text);
		white-space: normal;
	}
	.pastille-lecture-bulle[hidden] {
		display: none;
	}
	.pastille-lecture-bulle strong {
		display: block;
		margin-bottom: 0.15rem;
	}
</style>
