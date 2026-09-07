<!--
  **Mes badges** — une section de l'écran Accès & sécurité, rendue deux fois :
  une pour les vigiks, une pour les télécommandes.

  ## 🔴 Pourquoi ce composant (#805, 06/09/2026)

  Les deux sections étaient écrites **à l'identique**, à quatre mots près : le
  titre, le nom du tableau, le libellé du vide, et le `'vigik'` / `'tc'` passé
  aux deux gestes. Quarante lignes en double — table, colonnes, en-têtes, bouton
  « Signaler perdu » conditionné au statut, bouton de suppression conditionné au
  droit.

  ⚠️ Elles n'avaient PAS encore divergé, et c'est justement le moment où l'on
  factorise : après, il faut d'abord décider laquelle des deux a raison. C'est ce
  qui a coûté deux jours sur les libellés de rôles, le matin même (#801).

  ## Ce qui reste chez le parent, et pourquoi

  Les deux gestes — signaler perdu, supprimer — parlent à l'API et rechargent la
  liste. Ils restent callbacks : un seul endroit parle au serveur, et le
  composant ne connaît ni les routes ni le type d'objet qu'il rend. C'est le même
  contrat que `ListeAnnonces` et `ListeIdees`.

  ## La condition d'affichage vient du parent, elle aussi

  `{#if vigiks.length > 0 || statut !== 'locataire'}` — un locataire qui n'a
  aucun badge ne voit pas la section vide, un copropriétaire si (il peut en
  déclarer un). Cette règle est écrite **une fois** dans le parent, pour les deux
  sections : la porter ici obligerait à lui passer le statut, alors qu'elle ne
  parle pas du tableau mais de la place qu'il occupe dans l'écran.
-->
<script lang="ts">
	/** « Badges d'accès (Vigik) » ou « Télécommandes de parking ». */
	export let titre: string;
	/** Ce qu'on affiche quand la personne n'en a aucun. */
	export let messageVide: string;
	export let items: { id: number; code: string; statut: string }[] = [];
	/** Vrai pour le conseil syndical : lui seul peut supprimer un badge. */
	export let peutSupprimer = false;
	/** Comment un statut se traduit en classe de badge — fourni par l'écran. */
	export let classeStatut: (s: string) => string;

	export let onSignalerPerdu: (id: number) => void;
	export let onSupprimer: (id: number) => void;

	/**  Ce que l'`aria-label` du bouton de suppression doit nommer : « ce badge
	 *   Vigik », « cette télécommande ». Un libellé générique dirait « supprimer »
	 *   sans dire quoi, et c'est tout ce qu'un lecteur d'écran entendrait. */
	export let nomObjet: string;
</script>

<section class="card mes-acces-carte">
	<div class="section-header">
		<h2 class="section-title">{titre}</h2>
	</div>
	{#if items.length === 0}
		<p class="mes-acces-vide">{messageVide}</p>
	{:else}
		<table class="table" style="table-layout:fixed;width:100%">
			<colgroup><col style="width:35%" /><col style="width:9rem" /><col /></colgroup>
			<thead><tr><th>Code</th><th>Statut</th><th>Actions</th></tr></thead>
			<tbody>
				{#each items as item (item.id)}
					<tr>
						<td class="mes-acces-code">{item.code}</td>
						<td><span class="badge {classeStatut(item.statut)}">{item.statut}</span></td>
						<td class="mes-acces-actions">
							{#if item.statut === 'actif'}
								<button class="btn btn-sm btn-outline" on:click={() => onSignalerPerdu(item.id)}>
									Signaler perdu
								</button>
							{/if}
							{#if peutSupprimer}
								<button
									class="btn-icon-danger"
									aria-label="Supprimer {nomObjet}"
									title="Supprimer"
									on:click={() => onSupprimer(item.id)}>&#x1F5D1;&#xFE0F;</button
								>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
</section>

<style>
	/*  `.section` n'est pas globale : elle vit dans l'écran hôte, scopée à lui.
	    L'employer ici aurait rendu la carte sans son cadre (`standards/02` §4 ter,
	    et `lint:classes-nues` le refuse). */
	.mes-acces-carte {
		padding: 1.25rem;
	}
	.mes-acces-carte + :global(.mes-acces-carte) {
		margin-top: 1rem;
	}
	.mes-acces-vide {
		color: var(--color-text-muted);
		font-size: 0.9rem;
	}
	.mes-acces-code {
		font-family: monospace;
	}
	.mes-acces-actions {
		display: flex;
		gap: 0.35rem;
		flex-wrap: wrap;
	}
</style>
