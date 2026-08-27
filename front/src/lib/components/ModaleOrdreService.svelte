<!--
  Modale « Ordre de service » : joindre l'OS signé d'un devis, qui passe alors en
  **Accepté**. L'OS est facultatif — confirmer sans fichier change le statut, et
  c'est ce que dit la phrase d'aide.

  ## Pourquoi ce composant existe (27/08/2026, #370 et #453)

  Extraite de `prestataires/+page.svelte`, page de près de 2 000 lignes que le
  garde-fou de modularité (rang 1) refuse de voir grossir. Le lot #370 y remplaçait
  quatre `<input type="file">` nus par `FichiersUpload` — le composant unique de
  saisie de pièces jointes du site —, ce qui allongeait la page de onze lignes.

  ⚠️ La réponse évidente aurait été de comprimer les attributs sur une ligne pour
  repasser sous le seuil. C'est exactement ce que #453 décrit et interdit :
  *« satisfaire le contrôle par la mise en forme, pas par la structure »*. La
  modale est un objet complet — son état, son geste, son rendu — donc elle sort.

  ## Ce qui reste à la page

  L'appel réseau. La modale ne sait pas enregistrer un devis : elle rend le fichier
  retenu et le geste de confirmation, la page fait l'appel et met sa liste à jour.
  C'est la même frontière que partout ailleurs — un composant d'écran ne parle pas
  à l'API du métier de la page qui l'héberge.
-->
<script lang="ts">
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import { createEventDispatcher } from 'svelte';

	/** Identifiant du devis visé, ou `null` : la modale est alors fermée. */
	export let devisId: number | null = null;
	/** Un enregistrement est en cours — le bouton se verrouille. */
	export let envoi = false;

	const dispatch = createEventDispatcher<{ confirmer: File | null; fermer: void }>();

	let fichiers: File[] = [];

	function fermer() {
		//  L'annulation VIDE la sélection : sans cela, le fichier retenu survit à
		//  la fermeture et se retrouve joint au devis suivant qu'on ouvre.
		fichiers = [];
		dispatch('fermer');
	}
</script>

{#if devisId}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="modal-overlay" on:click={fermer}>
		<div
			class="modal modal-sm"
			role="dialog"
			aria-modal="true"
			aria-labelledby="modale-os-titre"
			on:click|stopPropagation
		>
			<div class="modal-header">
				<h2 id="modale-os-titre">Ordre de service</h2>
				<button class="modal-close" aria-label="Fermer" on:click={fermer}>×</button>
			</div>
			<div class="modal-body">
				<p class="modale-os-aide">
					Joindre l'OS signé (optionnel) — le statut passera en <strong>Accepté</strong>.
				</p>
				<!--  Mode DIFFÉRÉ obligatoire : l'OS part par un endpoint PROPRE au devis
				      (`uploadDevisOs`), pas par l'endpoint générique de téléversement. -->
				<FichiersUpload
					id="devis-os"
					mode="mixte"
					differe
					max={1}
					label="Choisir l'OS signé"
					bind:fichiers
					disabled={envoi}
				/>
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={fermer}>Annuler</button>
				<button
					class="btn btn-primary"
					disabled={envoi}
					on:click={() => dispatch('confirmer', fichiers[0] ?? null)}
				>
					{envoi ? 'Enregistrement...' : "Confirmer l'OS"}
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	/*  Le style voyage avec le balisage : la phrase d'aide portait ses règles en
	    ligne dans la page, où rien ne les rattachait à cette modale. */
	.modale-os-aide {
		font-size: 0.875rem;
		color: var(--color-text-muted);
	}
</style>
