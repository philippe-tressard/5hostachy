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
    tiers, et les badges de la copropriété.

  ⚠️ La « vue par locataire » d'un bailleur est restée dans `OngletAcces`, et ce
  n'est pas un oubli : elle MODIFIE les deux listes (récupérer les accès confiés
  remet `chez_locataire` à faux). La faire voyager aurait demandé de remonter
  l'état des listes ici — donc de déplacer le problème, pas de le découper.

  🔴 Ces blocs ne se découpent PAS par type d'accès, et c'est ce qui justifie
  qu'ils vivent ensemble : une demande porte les deux types dans la même ligne,
  un bail confie un badge ET une télécommande. Les scinder par onglet
  demanderait de filtrer, donc de décider qu'une demande à deux lignes se lit en
  deux endroits.

  ⚠️ Ils s'affichent donc ENTIERS sous chaque sous-onglet. C'est délibéré : ce
  que l'onglet découpe, ce sont mes listes, pas mon historique.
-->
<script lang="ts">
	import ArchivesParAnnee from '$lib/components/ArchivesParAnnee.svelte';
	import BadgesCopropriete from '$lib/components/BadgesCopropriete.svelte';
	import { currentUser, isCS } from '$lib/stores/auth';
	import { fmtDateShort } from '$lib/date';

	/** Les demandes d'accès passées, tous types confondus. */
	export let commandes: any[] = [];
	/** Les accès confiés par le bailleur — locataires seulement. */
	export let accesRecus: any[] = [];
	/** La classe de badge d'un statut — l'hôte la porte, elle sert aux deux. */
	export let statutClass: (s: string) => string;
	/** Idem pour le statut d'une commande. */
	export let commandeStatutClass: (s: string) => string;
</script>

<!--  Archives — les demandes passées. « Historique » nomme le fil d'un objet
      (cadre #430) ; ici ce sont des objets rangés (#516).

      C'était le seul écran dont la section n'était NI repliable NI groupée :
      un `<h2>` et une liste à plat. Il adopte le rendu commun. -->
<section class="section card" style="margin-top:1rem">
	<ArchivesParAnnee
		items={commandes}
		dateDe={(c) => c.cree_le}
		compte={commandes.length}
		charge
		messageVide="Aucune demande passée."
		let:objet={cmd}
	>
		<div class="commande-row">
			<div>
				<strong>{cmd.type === 'vigik' ? 'Badge Vigik' : 'Télécommande'}</strong>
				<span style="color:var(--color-text-muted);font-size:.8rem;margin-left:.5rem">
					× {cmd.quantite} — {fmtDateShort(cmd.cree_le)}
				</span>
				{#if cmd.motif}<p style="font-size:.85rem;color:var(--color-text-muted);margin:.2rem 0 0">
						{cmd.motif}
					</p>{/if}
			</div>
			<span class="badge {commandeStatutClass(cmd.statut)}">{cmd.statut.replace('_', ' ')}</span>
		</div>
	</ArchivesParAnnee>
</section>

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

{#if $isCS}
	<BadgesCopropriete />
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
	.commande-row {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		padding: 0.65rem 0;
		border-bottom: 1px solid var(--color-border);
	}
	.section {
		padding: 1.25rem;
	}
</style>
