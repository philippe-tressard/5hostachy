<!--
  ChampConfidentiel.svelte — « réserver ce ticket au conseil syndical ».

  Sorti de `FormulaireTicket.svelte` le 05/09/2026, sur refus du contrôle de
  modularité. C'est le voisin immédiat de `ChampSaisiPour`, qui est un composant
  depuis longtemps pour la même raison : un champ qui porte une RÈGLE — ici, qui
  voit le ticket — se nomme, et se lit ailleurs que dans un formulaire de 500
  lignes.

  ## Ce qui a changé en même temps, et qui est le vrai sujet (#710 → 05/09/2026)

  L'utilisateur a signalé : *« l'UX n'est pas terrible entre confidentiel et la
  case à cocher : est-ce lié ou indépendant ? j'ai du mal à comprendre »*. Deux
  causes, et la première n'était pas dans ce fichier :

  1. **La case était étirée sur toute la largeur**, avec bordure et fond, parce
     que `.field input` de la charte habille les zones de saisie sans exclure les
     cases. Le libellé se retrouvait à l'autre bout de la ligne, et la case
     semblait flotter sous « Saisi pour ». Corrigé dans la charte, donc partout.
  2. **Le libellé ne se suffisait pas.** « 🔒 Confidentiel » oblige à lire l'aide
     en dessous pour savoir de quoi il est le confidentiel. Le verbe dit le geste,
     le complément dit sur quoi il porte — et l'aide dit désormais, en toutes
     lettres, que le réglage est indépendant du champ voisin.

  🔴 Le CS seul le pose, et le serveur le revérifie (#710) : cet écran ne fait que
  proposer. La règle qui compte est côté API.
-->
<script lang="ts">
	/** Le ticket est-il réservé au conseil syndical ? */
	export let confidentiel = false;
</script>

<div class="field">
	<label class="case" for="ticket-confidentiel">
		<input id="ticket-confidentiel" type="checkbox" bind:checked={confidentiel} />
		🔒 Réserver ce ticket au conseil syndical
	</label>
	<!--  `.field-hint` : l'aide d'un champ, telle que la charte la définit. La
	      version locale de `FormulaireTicket` (`.aide-champ`) dit la même chose à
	      0,02 rem près — deux écritures d'une notion, dont l'une allait partir nue
	      en sortant du fichier. C'est `lint:classes-nues` qui l'a dit. -->
	<p class="field-hint">
		{confidentiel
			? 'Seuls vous, le conseil syndical et la personne concernée voyez ce ticket.'
			: 'Par défaut, un ticket est visible des résidents dont il concerne le bâtiment. Ce réglage est indépendant du champ « Saisi pour ».'}
	</p>
</div>
