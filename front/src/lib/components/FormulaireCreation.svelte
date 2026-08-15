<!--
  Le cadre d'un formulaire de création ou de modification : la boîte, sa largeur,
  son titre. UNE seule écriture pour tout le site (#367).

  Avant, le produit offrait **trois paradigmes** pour la même intention — créer un
  objet :

    • une boîte dans la page       (actualités, sondages)
    • une modale                    (calendrier, prestataires — et deux largeurs)
    • une page dédiée               (nouveau ticket)

  Le paradigme retenu est **la boîte dans la page**, sur désignation de
  l'utilisateur : les actualités sont le modèle de référence. C'est aussi le seul
  qui n'escamote pas l'écran pendant la saisie, et celui que suivaient déjà les
  rubriques les plus utilisées.

  ⚠️ CE QUE CE COMPOSANT NE PORTE PAS : la commande d'annulation. Elle reste dans
  l'en-tête de page, où le bouton d'ouverture bascule en « ✕ Annuler » — c'est le
  modèle des actualités, et il est conservé tel quel. Le défaut signalé n'était
  pas son emplacement mais son **alignement** : il se posait au bord droit de
  l'ÉCRAN alors que la boîte s'arrête à 720 px. C'est `EntetePage` qui le corrige,
  via `alignerSaisie`.

  Ne pas ajouter de second bouton d'annulation ici : deux commandes pour un seul
  formulaire, c'est précisément ce que la modale du calendrier faisait — sa croix
  ET le bouton d'en-tête, ce dernier sous l'overlay, visible et inutilisable.
-->
<script lang="ts">
	export let titre: string;
</script>

<div class="card largeur-saisie formulaire-creation">
	<h2>{titre}</h2>
	<slot />
</div>

<style>
	.formulaire-creation { margin-bottom: 1.5rem; }
	.formulaire-creation h2 { font-size: 1rem; font-weight: 600; margin: 0 0 1rem; }
</style>
