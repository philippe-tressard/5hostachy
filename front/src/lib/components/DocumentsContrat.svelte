<!--
  DocumentsContrat.svelte — les pièces d'un contrat d'entretien, écrites UNE fois.

  ## Pourquoi (30/08/2026, #453 · #640)

  `prestataires/+page.svelte` rendait ce bloc **deux fois** : dans le formulaire
  du haut et dans l'édition en ligne de la carte. Vingt-cinq lignes chacune, ne
  différant que par la source de l'identifiant (`editContratId` ou `c.id`) et par
  l'enveloppe.

  C'est la moitié qui restait après l'extraction de `ChampsContrat` — elle avait
  été laissée en le disant, faute de pouvoir faire voyager la table des documents
  et son téléversement dans le même lot.

  ⚠️ **Une duplication qu'aucun contrôle inter-fichiers ne voit**, puisqu'elle vit
  dans un seul fichier. C'est la forme la plus discrète, et celle qui produit les
  divergences les plus longues à trouver : `ChampsContrat` en portait quatre, dont
  un champ entier absent d'un des deux rendus.

  Le style reste en ligne, tel qu'il était : le remonter dans la charte est un
  autre geste, et le mêler à celui-ci rendrait la comparaison avant/après
  illisible.
-->
<script lang="ts">
	import AjoutDocumentContrat from '$lib/components/AjoutDocumentContrat.svelte';
	import { documents as docsApi } from '$lib/api';
	import { fmtDateShort } from '$lib/date';

	/** Le contrat dont on montre les pièces. */
	export let contratId: number;
	/** Les documents déjà attachés. */
	export let documents: any[] = [];
	/** Qui sait supprimer — l'écran, qui tient la table. */
	export let onSupprimer: (contratId: number, docId: number) => void;
	/** Qui sait recharger après un ajout. */
	export let onAjoute: (contratId: number) => void;
	/** Identifiant du champ de téléversement — unique par emplacement. */
	export let idChamp: string;
</script>

<div style="font-size:.85rem;font-weight:600;margin-bottom:.4rem">
	&#x1F4C4; Documents ({documents?.length ?? 0})
</div>
{#if documents?.length > 0}
	{#each documents as doc (doc.id)}
		<div
			style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem;font-size:.85rem;flex-wrap:wrap"
		>
			<a href={docsApi.downloadUrl(doc.id)} target="_blank"
				>&#x1F4CE; {doc.titre || doc.fichier_nom}</a
			>
			<span style="font-size:.75rem;color:var(--color-text-muted)"
				>{fmtDateShort(doc.publie_le)}</span
			>
			<button
				class="btn-icon-danger"
				title="Supprimer"
				style="margin-left:auto"
				on:click|stopPropagation={() => onSupprimer(contratId, doc.id)}>🗑️</button
			>
		</div>
	{/each}
{:else}
	<p style="font-size:.82rem;color:var(--color-text-muted);margin:0">Aucun document.</p>
{/if}
<AjoutDocumentContrat id={idChamp} {contratId} on:ajoute={() => onAjoute(contratId)} />
