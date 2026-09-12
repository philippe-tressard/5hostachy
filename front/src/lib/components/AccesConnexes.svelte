<!--
  **Ce qui entoure les accès d'un résident** : ses demandes passées, les accès
  que son bailleur lui a confiés, la vue par locataire d'un bailleur, et — pour
  le conseil syndical — les badges de la copropriété.

  ## Pourquoi séparé des listes (12/09/2026, #928)

  `OngletAcces` est né à 604 lignes en extrayant l'écran `/acces-securite`, donc
  au-dessus du plafond de modularité dès sa première ligne. La coupe suit la
  NATURE des blocs, pas leur position :

  * `OngletAcces` — **mes** accès : les deux listes, et les deux gestes qui les
    alimentent (demander, déclarer) ;
  * ce fichier-ci — **ce qui les entoure** : l'historique, ce qui vient d'un
    tiers.

  🔴 Les badges de la COPROPRIÉTÉ ont quitté ce composant le 12/09/2026 :
  ils sont un outil de rôle, pas une pièce de l'écran du résident. Ils vivent
  dans l'espace CS, sous leur propre onglet.

  ⚠️ La « vue par locataire » d'un bailleur est restée dans `OngletAcces`, et ce
  n'est pas un oubli : elle MODIFIE les deux listes (récupérer les accès confiés
  remet `chez_locataire` à faux). La faire voyager aurait demandé de remonter
  l'état des listes ici — donc de déplacer le problème, pas de le découper.

  🔴 Ces blocs ne se découpent PAS par type d'accès, et c'est ce qui justifie
  qu'ils vivent ensemble : une demande porte les deux types dans la même ligne,
  un bail confie un badge ET une télécommande. Les scinder par onglet
  demanderait de filtrer, donc de décider qu'une demande à deux lignes se lit en
  deux endroits.

  🔴 La section **Archives** (les demandes passées) a été RETIRÉE le 12/09/2026,
  sur demande de l'utilisateur : elle s'affichait sous « Mes badges » ET sous
  « Télécommandes », c'est-à-dire deux fois pour un seul contenu, et elle
  répétait sous chaque onglet une liste que l'onglet ne découpe pas.

  ⚠️ Conséquence assumée : un résident ne voit plus le suivi de ses demandes
  passées depuis cet écran. Le conseil syndical le voit, lui, dans ses
  validations — c'est là que la demande est traitée. `GET /acces/mes-commandes`
  reste servi, il n'a simplement plus d'appelant ici.

  ⚠️ Le seul « Archives » qui subsiste dans « Mes lots & accès » est celui de la
  **gestion locative**, qui est un sous-onglet à part entière et non un bloc
  répété.
-->
<script lang="ts">
	import { currentUser } from '$lib/stores/auth';

	/** Les accès confiés par le bailleur — locataires seulement. */
	export let accesRecus: any[] = [];
	/** La classe de badge d'un statut, portée par l'hôte. */
	export let statutClass: (s: string) => string;
</script>

<!-- Accès reçus du bailleur (locataires uniquement) -->
{#if $currentUser?.statut === 'locataire'}
	<section class="section card" style="margin-top:1rem;border-left:3px solid var(--color-primary)">
		<div class="section-header">
			<h2 class="section-title">&#x1F3E0; Accès confiés par votre bailleur</h2>
		</div>
		{#if accesRecus.length === 0}
			<p style="font-size:.85rem;color:var(--color-text-muted)">
				Aucun accès ne vous a encore été confié par votre propriétaire.
			</p>
		{:else}
			<p style="font-size:.85rem;color:var(--color-text-muted);margin-bottom:.75rem">
				Ces accès vous ont été confiés par votre propriétaire pour la durée de votre bail.
			</p>
			<table class="table" style="table-layout:fixed;width:100%">
				<colgroup
					><col style="width:30%" /><col style="width:10rem" /><col style="width:9rem" /></colgroup
				>
				<thead><tr><th>Code</th><th>Type</th><th>Statut</th></tr></thead>
				<tbody>
					{#each accesRecus as a (a.id)}
						<tr>
							<td style="font-family:monospace">{a.code}</td>
							<td>{a.type === 'vigik' ? '\u{1F3F7}️ Vigik' : '\u{1F4E1} Télécommande'}</td>
							<td><span class="badge {statutClass(a.statut)}">{a.statut}</span></td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</section>
{/if}

<style>
	/*  Le style suit le BALISAGE (12/09/2026) : ces règles étaient restées dans
	    `OngletAcces` quand le tableau et la ligne de commande sont partis ici.
	    C'est le défaut que `lint:css-orphelin` et `lint:classes-nues` attrapent
	    à chaque extraction — un style laissé derrière ne lève rien à
	    l'exécution, il rend simplement le balisage NU. */
	/*  Seule la taille differe de `.table` (#607, 28/08/2026). */
	.table {
		font-size: 0.9rem;
	}
	/*  Ne garde que l'écart — la raison est déclarée dans
	    `check-charte-recomposee.regles.mjs` (30/08/2026). */
	.table th {
		padding: 0.4rem 0.5rem;
		font-size: 0.8rem;
	}
	.table td {
		padding: 0.5rem;
	}
	.section {
		padding: 1.25rem;
	}
</style>
