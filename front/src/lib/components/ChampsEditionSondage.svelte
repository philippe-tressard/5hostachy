<!--
  Les champs de la CORRECTION d'un sondage — question, description, libellés
  des réponses, date de clôture, visibilité des résultats.

  Extraits de `sondages/[id]` le 24/09/2026 (#1254) : la page dépassait six
  cents lignes, et le garde-fou de modularité demande de découper le fichier
  qu'on touche. La coupe suit le geste : la page garde l'ouverture de la boîte
  et l'appel à l'API, ce composant ne porte que la saisie.
-->
<script context="module" lang="ts">
	/**  `options` ne porte que l'`id` et le LIBELLÉ : le serveur n'accepte rien
	 *   d'autre, et c'est ce qui rend l'ajout et le retrait impossibles par
	 *   construction plutôt que par un contrôle qu'on pourrait oublier (#467). */
	export interface EditionSondage {
		question: string;
		description: string;
		cloture_le: string;
		resultats_publics: boolean;
		options: { id: number; libelle: string }[];
	}
</script>

<script lang="ts">
	import EtoileRequis from '$lib/components/EtoileRequis.svelte';
	import SectionDescription from '$lib/components/SectionDescription.svelte';
	import { contexteAssistant } from '$lib/assistant';

	export let form: EditionSondage;
	export let assisteIA = false;
</script>

<label class="field">
	<span>Question<EtoileRequis vide={!form.question.trim()} /></span>
	<input bind:value={form.question} required />
</label>
<SectionDescription
	idPrefixe="sondage-edit"
	placeholder="Description du sondage…"
	bind:valeur={form.description}
	assistant={contexteAssistant('sondage', {})}
	bind:titreObjet={form.question}
	bind:assisteIA
/>
<!--  Les RÉPONSES : leur libellé se corrige, la liste ne bouge pas.
      Ni ajout ni retrait — un vote déjà exprimé sur une option retirée n'a
      pas de repli honnête : le compter ailleurs fausse le résultat, le
      supprimer efface l'expression de quelqu'un sans le lui dire (#467).
      L'interface dit donc EXACTEMENT ce que le serveur accepte : pas de
      bouton « + », pas de croix, et l'ordre ne se change pas non plus. -->
{#if form.options.length}
	<div class="field">
		<span class="champ-titre">Réponses possibles</span>
		{#each form.options as opt, i (opt.id)}
			<input
				class="reponse-saisie"
				bind:value={form.options[i].libelle}
				aria-label="Libellé de la réponse {i + 1}"
				required
			/>
		{/each}
		<p class="aide">
			Seul le <strong>texte</strong> se corrige. Ajouter ou retirer une réponse invaliderait les votes
			déjà exprimés : il faudrait alors créer un nouveau sondage.
		</p>
	</div>
{/if}

<label class="field">
	Date de clôture
	<input type="datetime-local" bind:value={form.cloture_le} />
</label>
<p class="aide">
	Elle peut être <strong>reculée</strong>, jamais avancée une fois qu'un vote a été exprimé —
	raccourcir priverait de leur voix ceux qui n'ont pas encore voté.
</p>
<label style="display:flex;align-items:center;gap:.5rem;margin-bottom:1rem;cursor:pointer">
	<input type="checkbox" bind:checked={form.resultats_publics} />
	Afficher les résultats avant la clôture
</label>
<p style="margin:-.6rem 0 1rem 1.6rem;font-size:.8rem;color:var(--color-text-muted)">
	Ils seront lus par les destinataires du sondage. Sinon, ils n'apparaissent qu'une fois le sondage
	clôturé.
</p>

<style>
	/*  Saisie des libellés de réponse (#467). */
	.champ-titre {
		display: block;
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--color-text);
		margin-bottom: 0.3rem;
	}
	.reponse-saisie {
		width: 100%;
		margin-bottom: 0.35rem;
	}
</style>
