<!--
  Un encart d'avertissement : fond et filet de la teinte d'avertissement, texte
  en `--color-warning-texte` — la teinte dédiée au texte ; `--color-warning`
  seule n'y sert jamais (charte, `ux-patterns` §18).

  Créé le 29/09/2026 (#779) pour les deux bandeaux du profil, puis devenu la
  SEULE écriture de la notion (#1455) : elle était recopiée dans sept écrans,
  chacun avec sa marge, son rayon et sa taille, et `.alert-warning` en portait
  une huitième aux couleurs en dur. La couleur du texte est celle de cinq copies
  sur six.

  - `compact` : sous un champ, dans le flux d'un formulaire (Verr. Maj.,
    divergence d'étage) — plus serré, plus petit, et détaché du champ.
  - les autres attributs (`role`, `id`…) passent sur l'encart.
  - la MARGE appartient à l'appelant : c'est sa mise en page, pas la notion.

  🔒 `npm run lint:encart-avertissement` refuse le fond d'avertissement ailleurs
  qu'ici, hors emprunts de teinte déclarés.
-->
<script lang="ts">
	/** Sous un champ : resserré, et détaché de lui par une ligne fine. */
	export let compact = false;
</script>

<div class="encart-avertissement" class:compact {...$$restProps}><slot /></div>

<style>
	.encart-avertissement {
		padding: 0.6rem 0.9rem;
		border-radius: var(--radius);
		font-size: var(--fs-md);
		line-height: 1.45;
		color: var(--color-warning-texte);
		background: var(--color-warning-fond);
		border: 1px solid var(--color-warning-bordure);
	}
	.compact {
		margin-top: 0.4rem;
		padding: 0.45rem 0.7rem;
		font-size: var(--fs-sm);
		line-height: 1.4;
	}
</style>
