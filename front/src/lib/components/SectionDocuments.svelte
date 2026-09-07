<!--
  **Une section de documents de la page Résidence** — son titre, son bouton
  d'ajout, ses trois états et ses lignes téléchargeables.

  ## Pourquoi ce composant (#522)

  La page Résidence portait **trois fois** la même section, à quarante lignes
  d'intervalle : Plans, Règlement de copropriété, Comptes-rendus d'AG. Même
  en-tête, même bouton « + Ajouter », même `doc-row`, mêmes gestes (télécharger,
  modifier, supprimer). Seuls les **badges** d'une ligne changeaient.

  Le garde-fou de modularité a refusé que la page grossisse en recevant les états
  d'erreur de #522, et il disait vrai : une page de 1 350 lignes qui rend trois
  fois la même chose n'a pas un problème de taille, elle a un problème de
  découpage (#453).

  ## Ce qui varie, et comment

  Le **badge** d'une ligne, par le `slot` nommé `badges` — c'est la seule
  différence réelle entre les trois sections :

  | Section | Badge |
  |---|---|
  | Plans | le bâtiment, ou « Copropriété » |
  | Règlement | aucun |
  | Comptes-rendus d'AG | l'année, la date d'AG, les bâtiments concernés |

  ## 🔴 Les styles voyagent avec le balisage

  `.doc-list`, `.doc-row`, `.doc-info`… vivaient dans le `<style>` de la page.
  Svelte scope les styles au composant qui rend l'élément : les y laisser aurait
  livré les lignes **nues** en production — c'est la panne des pastilles de la
  v2.67.11, refaite deux fois depuis. Ils sont donc ici, avec ce qu'ils habillent.
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import BoutonLien from '$lib/components/BoutonLien.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';

	/** Le titre affiché, emoji compris — la page reste maîtresse de son vocabulaire. */
	export let titre: string;
	export let documents: any[] = [];
	/**  Non vide = on n'a PAS pu charger. Distinct de « chargé et vide » : c'est
	 *   toute la raison de ce lot (#522). */
	export let erreur = '';
	export let messageVide = 'Aucun document ajouté.';
	/** Le lecteur peut-il ajouter, corriger et supprimer ? (conseil syndical) */
	export let peutModifier = false;
	/** L'URL de téléchargement — construite par la page, qui connaît son client API. */
	export let urlTelechargement: (doc: any) => string;
	export let onAjouter: () => void;
	export let onModifier: (doc: any) => void;
	export let onSupprimer: (id: number) => void;
	/** Rendu de la date d'un document ; vide = pas de date affichée. */
	export let dateDe: (doc: any) => string = () => '';
</script>

<section class="section-documents">
	<div class="section-header">
		<!--  Texte, jamais `{@html}` : Svelte décode déjà les entités HTML dans
		      une valeur d'attribut, donc `titre="&#x1F5FA;️ Plans"` arrive ici en
		      emoji. Passer par `{@html}` aurait exigé un assainisseur pour un
		      titre que la page écrit elle-même — une exception de plus à la
		      règle XSS, pour rien. -->
		<h2 class="section-title">{titre}</h2>
		{#if peutModifier}
			<button class="btn btn-sm" on:click={onAjouter}>+ Ajouter</button>
		{/if}
	</div>

	<EtatListe compact {erreur} vide={documents.length === 0} {messageVide}>
		<div class="doc-list">
			{#each documents as doc (doc.id)}
				<div class="doc-row card" id="doc-{doc.id}">
					<div class="doc-info">
						<Icon name="file-text" size={16} />
						<span class="doc-titre">{doc.titre}</span>
						<slot name="badges" {doc} />
						{#if dateDe(doc)}<span class="doc-date">{dateDe(doc)}</span>{/if}
					</div>
					<div class="doc-actions">
						<BoutonLien ancre="doc-{doc.id}" quoi="le document" />
						<a href={urlTelechargement(doc)} target="_blank" class="btn btn-sm" download>
							⬇ Télécharger
						</a>
						{#if peutModifier}
							<button
								class="btn-icon-edit"
								aria-label="Modifier"
								title="Modifier"
								on:click={() => onModifier(doc)}>✏️</button
							>
							<button
								class="btn-icon-danger"
								aria-label="Supprimer"
								title="Supprimer"
								on:click={() => onSupprimer(doc.id)}>&#x1F5D1;️</button
							>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	</EtatListe>
</section>

<style>
	.section-documents {
		margin-bottom: 2.5rem;
	}
	/*  Seul `margin: 0` differe : la charte pose `margin-bottom` (#607, 28/08/2026). */
	.section-title {
		margin: 0;
	}
	/*  🔴 `.doc-*` REMONTÉES dans `styles/composants.css` le 29/08/2026 (#491).
	    Elles étaient scopées ici, et `residence` employait le même vocabulaire
	    dans SON balisage — trois blocs y sortaient nus. Une notion partagée par
	    plusieurs écrans vit dans la charte, elle ne se recopie pas. */
</style>
