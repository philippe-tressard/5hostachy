<!--
  Historique des publications archivées : replié par défaut, groupé par année,
  chargé seulement au premier dépliage.

  Extrait de `actualites/+page.svelte` (#356) : la page dépassait le plafond de
  500 lignes, et cette section est autonome — elle a sa propre source de données
  (`list(true)`), son propre état de dépliage et sa propre suppression. Rien de
  ce qu'elle manipule n'est partagé avec le fil principal.

  La carte, elle, est la MÊME que celle du fil : `CarteActualite`, en variante
  `historique`. C'est tout l'objet du ticket — les deux rendus ne peuvent plus
  diverger.
-->
<script lang="ts">
	import CarteActualite from '$lib/components/CarteActualite.svelte';
	import ArchivesParAnnee from '$lib/components/ArchivesParAnnee.svelte';
	import { isAdmin } from '$lib/stores/auth';
	import { publications as pubsApi, ApiError, type Publication } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';

	let archivedPubs: Publication[] = [];
	let archivedPubsLoaded = false;
	let historyExpanded = false;
	let expandedHistoryItems = new Set<number>();

	async function loadArchivedPubs() {
		if (archivedPubsLoaded) return;
		archivedPubsLoaded = true;
		try {
			archivedPubs = await pubsApi.list(true);
		} catch {
			/* silencieux */
		}
	}

	$: if (historyExpanded) loadArchivedPubs();

	function toggleHistoryItem(id: number) {
		expandedHistoryItems = expandedHistoryItems.has(id) ? new Set() : new Set([id]);
	}

	async function deleteArchivedPub(pub: Publication) {
		if (!confirm(`Supprimer définitivement « ${pub.titre} » ?`)) return;
		try {
			await pubsApi.delete(pub.id);
			archivedPubs = archivedPubs.filter((p) => p.id !== pub.id);
			toast('success', 'Publication supprimée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Impossible de supprimer');
		}
	}
</script>

<!--  Le bandeau et le groupement par année viennent d'`ArchivesParAnnee` :
      le motif était écrit ici ET dans le calendrier, avec deux aspects et deux
      comportements (#516). `ouvert` est LIÉ — c'est lui qui déclenche encore le
      chargement différé au premier dépliage.

      ⚠️ « Archives » et non « Historique » : ce dernier nomme déjà le FIL d'un
      objet (cadre #430). Sur Tickets, les deux mots coexistaient sur le même
      écran pour deux notions sans rapport. -->
<ArchivesParAnnee
	items={archivedPubs}
	dateDe={(pub) => pub.mis_a_jour_le ?? pub.cree_le}
	compte={archivedPubsLoaded ? archivedPubs.length : null}
	charge={archivedPubsLoaded}
	messageVide="Aucune actualité archivée."
	bind:ouvert={historyExpanded}
	let:objet={pub}
>
	<CarteActualite
		{pub}
		variante="historique"
		expanded={expandedHistoryItems.has(pub.id)}
		on:toggle={() => toggleHistoryItem(pub.id)}
	>
		<svelte:fragment slot="actions">
			{#if $isAdmin}
				<button
					class="btn-icon"
					aria-label="Supprimer"
					title="Supprimer définitivement"
					style="color:var(--color-danger)"
					on:click|stopPropagation={() => deleteArchivedPub(pub)}>&#x1F5D1;&#xFE0F;</button
				>
			{/if}
		</svelte:fragment>
	</CarteActualite>
</ArchivesParAnnee>
