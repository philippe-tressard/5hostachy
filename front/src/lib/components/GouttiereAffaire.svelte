<!--
  GouttiereAffaire.svelte — la colonne de gauche d'une carte d'affaire : QUAND,
  puis QUOI.

  ## Pourquoi (10/10/2026, maquette B « Gouttière », choisie parmi cinq)

  Demandé : une liste des affaires « plus premium et aérée, sans perdre aucune
  information ». La liste se parcourt par le temps : la date, rangée en bout de
  dernière ligne, obligeait l'œil à zigzaguer d'une carte à l'autre. Elle monte
  en tête d'une colonne, le jour en grand ; la nature — Actualité, Calendrier,
  Affaire — se lit dessous. Tout ce qui SITUE une affaire est à gauche, tout ce
  qui se LIT est à droite.

  Elle remplace la gouttière teintée du 24/09/2026, qui ne portait que la nature
  et la disait par deux pseudo-éléments (`data-nature-icone`, `-libelle`). Un
  texte rendu en `content: attr()` ne se sélectionne pas et ne se compose pas :
  la date ne pouvait pas y entrer. La TEINTE reste portée par la carte
  (`[data-nature]`, `styles/normes.css`) : ce composant la lit, il ne la décide pas.

  🔴 La date est celle que la carte affichait — `mis_a_jour_le`, sinon
  `cree_le` — et la carte NE la passe plus à `EnteteCarte` : deux dates sur une
  carte en feraient deux faits. C'est l'arbitrage n° 4 de `ux-patterns` (« date
  à droite ») qui cède ici, pour les cartes d'affaire seulement.

  Au téléphone (≤ 480 px) la colonne prendrait la place du titre : elle devient
  une LIGNE d'en-tête — « 5 oct. 2026 · CAL. » —, posée au-dessus du titre.
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { partiesDate } from '$lib/date';
	import { natureDe } from '$lib/tickets';

	/** L'affaire : ses natures (dérivées par le serveur) et ses deux dates. */
	export let affaire: { natures?: string[]; cree_le: string; mis_a_jour_le?: string | null };

	$: nature = natureDe(affaire);
	$: quand = affaire.mis_a_jour_le ?? affaire.cree_le;
	$: date = partiesDate(quand);
</script>

<div class="gouttiere">
	{#if date}
		<time class="g-date" datetime={quand}>
			<span class="g-jour">{date.jour}</span>
			<span class="g-mois">{date.mois} <span class="g-annee">{date.annee}</span></span>
		</time>
	{/if}
	<span class="g-nature" title={nature.libelle}>
		<Icon name={nature.icone} size={18} />
		<abbr title={nature.libelle}>{nature.abrege}</abbr>
	</span>
</div>

<style>
	/*  La colonne court sur toute la hauteur de la carte, dépliée comprise : elle
	    est posée en absolu dans le retrait que la carte lui réserve
	    (`padding-left: var(--largeur-gouttiere)`, `normes.css`). Son fond est un
	    pierre ADOUCI — la charte, mêlée au blanc de la carte : le repère existe
	    sans crier, là où l'ancien bandeau teintait toute la hauteur. */
	.gouttiere {
		position: absolute;
		inset: 0 auto 0 0;
		width: var(--largeur-gouttiere);
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 0.85rem 0.25rem;
		background: color-mix(in srgb, var(--color-bg) 45%, var(--color-surface));
		border-right: 1px solid color-mix(in srgb, var(--color-border) 60%, transparent);
		border-radius: var(--radius) 0 0 var(--radius);
		text-align: center;
	}
	.g-date {
		display: flex;
		flex-direction: column;
		align-items: center;
	}
	.g-jour {
		font-family: var(--police-titres);
		font-size: var(--fs-chiffre);
		line-height: 1;
		color: var(--color-text);
		font-variant-numeric: lining-nums tabular-nums;
	}
	.g-mois {
		margin-top: 0.25rem;
		font-size: var(--fs-xs);
		line-height: 1.25;
		color: var(--color-text-muted);
	}
	.g-annee {
		display: block;
	}
	/*  La nature prend la teinte de la carte (`--nature-fort`). Petites capitales
	    espacées, abrégées : écrit en entier, « CALENDRIER » élargissait la
	    colonne (#1220). `e2e/gouttiere-nature` mesure que le mot y tient. */
	.g-nature {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.2rem;
		color: var(--nature-fort);
	}
	.g-nature abbr {
		text-decoration: none;
		font-size: var(--fs-2xs);
		font-weight: 700;
		letter-spacing: 0.06em;
	}

	/*  Au pouce, une LIGNE au-dessus du titre : la date à gauche, la nature au
	    bout. Le jour reprend la taille du texte — en vedette, il mangerait la
	    hauteur que la colonne vient de rendre. */
	@media (max-width: 480px) {
		.gouttiere {
			position: static;
			width: auto;
			flex-direction: row;
			align-items: center;
			justify-content: space-between;
			padding: 0.4rem 0.7rem;
			border-right: 0;
			border-bottom: 1px solid color-mix(in srgb, var(--color-border) 60%, transparent);
			border-radius: var(--radius) var(--radius) 0 0;
		}
		.g-date {
			flex-direction: row;
			align-items: baseline;
			gap: 0.3em;
			font-size: var(--fs-sm);
			font-weight: 600;
			color: var(--color-text);
		}
		.g-jour {
			font-family: inherit;
			font-size: inherit;
			line-height: inherit;
		}
		.g-mois {
			margin: 0;
			font-size: inherit;
			color: inherit;
		}
		.g-annee {
			display: inline;
		}
		.g-nature {
			flex-direction: row;
			gap: 0.35rem;
		}
	}
</style>
