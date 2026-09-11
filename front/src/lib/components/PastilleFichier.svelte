<!--
  La PASTILLE d'un fichier joint — « TYPE: nom », et la croix qui le retire.

  ## Pourquoi ce composant (11/09/2026)

  Deux rendus coexistaient pour la même chose, et l'utilisateur a désigné le bon :

  | Écran | Ce qu'il rendait |
  |---|---|
  | Tickets (`FichiersUpload`) | des pastilles **horizontales**, une croix rouge |
  | Actualités (`DocumentsPublication`) | une **liste verticale**, un 🗑️ par ligne |

  *« Adopter celui de Tickets, qui est très beau »* — et surtout : le même objet
  ne peut pas avoir deux formes selon l'écran qui le montre (R3 du cadre). La
  pastille vit donc ici, et les deux appelants la reçoivent.

  ## Le format « TYPE: nom »

  Demandé le même jour : *« PDF: MON NOM »*. Le type est l'information la plus
  utile d'une liste de pièces jointes — on cherche « le PDF », pas « le
  cinquième ». Il se calcule dans `$lib/fichiers` (`typeFichier`), jamais ici :
  quatre rendus l'affichent, un format recopié aurait divergé au premier
  ajustement.

  ⚠️ L'extension ne s'affiche PAS dans le nom : elle est déjà dite par le type,
  et « PDF: contrat.pdf » allonge la pastille pour ne rien apprendre.
-->
<script lang="ts">
	import { typeFichier, nomSansExtension } from '$lib/fichiers';

	/**  Le nom du fichier, ou son URL — `typeFichier` accepte les deux. */
	export let nom: string;
	/**  Un nom d'affichage qui prime sur celui du fichier (le `titre` d'un
	 *   `Document`, par exemple). L'extension reste tirée de `nom`. */
	export let libelle: string | null = null;
	export let readonly = false;

	$: type = typeFichier(nom);
	$: affiche = libelle?.trim() || nomSansExtension(nom);
</script>

<span class="fichier-chip">
	<span class="fichier-type">{type}</span>
	<span class="fichier-nom">{affiche}</span>
	{#if !readonly}
		<button
			type="button"
			class="fichier-retirer"
			title="Retirer ce document"
			aria-label="Retirer {affiche}"
			on:click
		>
			×
		</button>
	{/if}
</span>

<style>
	/*  🔴 Ces règles voyagent AVEC le balisage. Les laisser chez l'appelant
	    rendrait la pastille nue dans l'autre — c'est la régression des pastilles
	    de la v2.67.11, et elle s'est reproduite trois fois le 19/08/2026. */
	.fichier-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		max-width: 100%;
		padding: 0.2rem 0.45rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-bg-alt, #f5f5f5);
		font-size: 0.8rem;
	}
	/*  Le type en tête, gris et compact : il se lit d'un coup d'œil sans voler la
	    place au nom, qui est ce qu'on cherche ensuite. */
	.fichier-type {
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.02em;
		color: var(--color-text-muted);
		flex-shrink: 0;
	}
	.fichier-type::after {
		content: ':';
	}
	.fichier-nom {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.fichier-retirer {
		border: none;
		background: none;
		color: var(--color-danger);
		cursor: pointer;
		font-size: 1rem;
		line-height: 1;
		padding: 0;
		flex-shrink: 0;
	}
</style>
