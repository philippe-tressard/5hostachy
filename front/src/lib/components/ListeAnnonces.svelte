<!--
  Une liste de petites annonces — le `{#each}`, la carte et son formulaire de
  correction, écrits **une seule fois**.

  ## Pourquoi ce composant existe (18/08/2026)

  L'onglet en rend maintenant **deux** : les annonces courantes, et l'Historique
  replié des annonces conclues depuis plus d'un mois. Le premier réflexe est de
  recopier le bloc `{#each}` — une quinzaine de lignes de câblage — sous la
  section repliée.

  🔴 **Ce réflexe est exactement ce que le rang 1 interdit**, et l'histoire du
  projet dit pourquoi : le fil des tickets a été rendu à la main six fois, et les
  copies avaient divergé sur les pièces jointes, la marge et jusqu'au libellé des
  boutons (#431). Deux listes qui se ressemblent aujourd'hui divergent au premier
  correctif appliqué à une seule.

  Ici, la seule différence entre les deux listes est **la liste elle-même** —
  l'atténuation des cartes archivées vient de `annonce.archivee`, que le serveur
  calcule. Rien d'autre ne change, donc rien d'autre ne se paramètre.
-->
<script lang="ts">
	import AnnonceCard from './AnnonceCard.svelte';
	import FormulaireAnnonce from './FormulaireAnnonce.svelte';

	/** Les annonces à rendre, déjà filtrées et triées par l'appelant. */
	export let liste: any[] = [];
	/** L'annonce dépliée, et celle en cours de correction — tenues par l'onglet. */
	export let expandedId: number | null = null;
	export let gestionPhotosId: number | null = null;
	export let editAnnonce: any = null;

	export let estCS = false;
	export let estAdmin = false;
	export let currentUserId: number | undefined = undefined;

	export let onToggle: (a: any) => void;
	export let onToggleGestion: (a: any) => void;
	export let onModifier: (a: any) => void;
	export let onUpload: (id: number, f: File) => Promise<string>;
	export let onRemove: (id: number, url: string) => Promise<string[] | void>;
	export let onStatut: (id: number, statut: string) => void;
	export let onSupprimer: (id: number) => void;
	export let onRepondre: (id: number, contenu: string) => Promise<void>;
	export let onSupprimerReponse: (id: number, repId: number) => void;
	export let onSignaler: (cibleType: string, cibleId: number) => void;
	/** Une annonce vient d'être corrigée : l'onglet met sa liste à jour. */
	export let onModifiee: (maj: any) => void;
	export let onAnnulerEdition: () => void;
</script>

{#each liste as annonce (annonce.id)}
	<AnnonceCard
		{annonce}
		expanded={expandedId === annonce.id}
		gestionOuverte={gestionPhotosId === annonce.id}
		formulaireOuvert={editAnnonce?.id === annonce.id}
		{estCS}
		{estAdmin}
		{currentUserId}
		onToggle={() => onToggle(annonce)}
		onToggleGestion={() => onToggleGestion(annonce)}
		onModifier={() => onModifier(annonce)}
		onUpload={(f) => onUpload(annonce.id, f)}
		onRemove={(url) => onRemove(annonce.id, url)}
		onStatut={(statut) => onStatut(annonce.id, statut)}
		onSupprimer={() => onSupprimer(annonce.id)}
		onRepondre={(c) => onRepondre(annonce.id, c)}
		onSupprimerReponse={(rid) => onSupprimerReponse(annonce.id, rid)}
		onSignalerAnnonce={() => onSignaler('annonce', annonce.id)}
		onSignalerReponse={(rid) => onSignaler('reponse', rid)}
	>
		<!--  Le formulaire de CORRECTION prend la place du corps, il ne s'ajoute pas
		      dessous : deux cartes empilées pour un seul objet, c'est ce que #425
		      appelle « la carte dans la carte ».
		      `{#key}` remonte le composant d'une annonce à l'autre — ses champs sont
		      initialisés une seule fois, à la construction. -->
		<svelte:fragment slot="formulaire">
			{#key editAnnonce?.id}
				<FormulaireAnnonce
					annonce={editAnnonce}
					on:modifie={(e) => onModifiee(e.detail)}
					on:annule={onAnnulerEdition}
				/>
			{/key}
		</svelte:fragment>
	</AnnonceCard>
{/each}
