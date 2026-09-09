<!--
  L'onglet **Maintenance** de l'administration : les tâches planifiées des deux
  nœuds, l'intégrité référentielle, et le contrôle de santé quotidien.

  Extrait de `admin/+page.svelte` le 09/09/2026 (#852) — la page fait 1 741 lignes
  et son plafond de modularité lui interdit de grossir. Elle porte déjà dix-sept
  onglets sous forme de composants (`Onglet*.svelte`) : celui-ci était l'un des
  derniers écrits en ligne, et l'accueillir aurait demandé de l'agrandir.
-->
<script lang="ts">
	import ControleSante from '$lib/components/ControleSante.svelte';
	import IntegriteReferentielle from '$lib/components/IntegriteReferentielle.svelte';
	import TachesPlanifiees from '$lib/components/TachesPlanifiees.svelte';
</script>

<p class="muted" style="margin-bottom:1.25rem">
	Exécution des tâches planifiées sur les <strong>deux</strong> Raspberry&nbsp;Pi. Le nœud actif assure
	la maintenance applicative (purges, VACUUM) ; le nœud en veille fait son hygiène locale (cache de build,
	rotation des logs) et transmet son rapport au nœud actif.
</p>

<!--  Les deux cartes « Sauvegarde quotidienne — historique » et « Agrégation
      télémétrie — historique » vivaient ici. Supprimées avec #299 : depuis que la
      synthèse déplie l'historique de chaque tâche et porte son bouton de
      lancement, elles montraient les MÊMES lignes, tirées des MÊMES endpoints,
      sous un titre construit exprès pour ressembler à celui de la synthèse.
      Ce qu'elles portaient d'unique — le lieu de stockage des archives et le rôle
      de l'agrégation — est déplacé dans `TachesPlanifiees` (AIDE_TACHE), et la
      profondeur d'historique y passe de 4 à 10 : retirer les cartes sans
      compenser aurait réduit en silence ce qu'un administrateur peut voir. -->
<TachesPlanifiees />
<IntegriteReferentielle />
<ControleSante />
