<!--
  L'en-tête d'une page : retour éventuel, titre, actions.

  Une seule écriture pour tout le site (#363). Avant ce composant, l'en-tête était
  écrit de douze façons : `.page-header` redéfini en CSS local dans six pages et
  surchargé en ligne dans six autres, le style du `<h1>` recopié **en ligne** dans
  onze pages, et trois formes de bouton retour pour deux classes.

  Le défaut visible qui l'a déclenché : `tickets/nouveau` réécrivait `.page-header`
  avec `display:flex; align-items:center; gap:1rem` — l'intention est claire, un
  groupe serré à gauche — sans redéclarer le `justify-content: space-between` de la
  règle globale, dont elle héritait donc en silence. Résultat : le titre projeté à
  l'autre bout de l'écran, seul écran du site dans ce cas, et personne ne l'avait
  voulu. C'est le « piège de l'héritage partiel » de `standards/11-interface-et-ux.md`
  §1 bis.

  Disposition, la même partout : [retour] titre à GAUCHE · actions à DROITE.
  C'est déjà ce que faisaient seize pages sur dix-sept.

  Le conteneur `.page-header` reste porté par `app.css` — y compris son passage en
  colonne et en `sticky` sous 640 px. Ce composant ne le redéfinit pas : il n'écrit
  que ce que la règle globale ne dit pas.
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';

	export let titre: string;
	/** Nom d'icône Lucide. Toute page en porte une — sauf à ne pas savoir laquelle. */
	export let icone: string | null = null;
	/** Cible du bouton de retour. Absent = pas de retour. */
	export let retour: string | null = null;
	/**  Marge basse, quand la page a besoin d'un écart plus serré (onglets ou
	 *   descriptif juste dessous). Quatre pages divergeaient ainsi en `style=` en
	 *   ligne : la valeur est désormais explicite et centralisée, mais elle reste
	 *   une dette — le bon écart se tranche à l'écran, pas dans le code. */
	export let marge: string | null = null;
	/**  Aligne l'en-tête sur la largeur de saisie (720 px) au lieu de la pleine
	 *   largeur. À activer quand un formulaire est ouvert dans la page : sinon
	 *   son bouton d'annulation se pose au bord droit de l'ÉCRAN, très loin de la
	 *   boîte qu'il annule — signalé par l'utilisateur le 15/08/2026 (#367).
	 *
	 *   Réservé à ce cas : hors saisie, la liste occupe toute la largeur et
	 *   contraindre l'en-tête décalerait le bouton par rapport à ce qu'il domine. */
	export let alignerSaisie = false;
</script>

<div class="page-header" class:largeur-saisie={alignerSaisie}
	style={marge ? `margin-bottom:${marge}` : undefined}>
	<div class="entete-principal">
		{#if retour}
			<a href={retour} class="btn btn-outline entete-retour">← Retour</a>
		{/if}
		<h1>{#if icone}<Icon name={icone} size={20} />{/if}{titre}</h1>
	</div>
	{#if $$slots.default}
		<div class="entete-actions"><slot /></div>
	{/if}
</div>

<style>
	/*  Retour et titre forment UN bloc : sans ce groupe, `space-between` les
	    écarterait aux deux bouts — exactement le défaut corrigé ici. */
	.entete-principal { display: flex; align-items: center; gap: .75rem; min-width: 0; }
	.entete-retour { flex-shrink: 0; }

	h1 { display: flex; align-items: center; gap: .4rem; font-size: 1.4rem; font-weight: 700; min-width: 0; }

	.entete-actions { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }

	/*  Aucune largeur n'est écrite ici : c'est la classe globale `largeur-saisie`
	    (app.css) qui est posée sur le conteneur. Recopier « 720 px » aurait créé
	    la deuxième valeur qui dérive le jour où la première change. */
</style>
