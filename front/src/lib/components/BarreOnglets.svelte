<!--
  BarreOnglets.svelte — LA rangée d'onglets d'une page, écrite une fois.

  ## Pourquoi (05/09/2026)

  Un onglet n'avait pas d'adresse. `/sondages` ouvrait toujours les sondages, et
  « Petites annonces » ne s'atteignait que par un clic : impossible d'ENVOYER un
  lien vers une rubrique. Signalé par l'utilisateur, qui voulait partager une
  annonce et n'avait à copier que l'adresse de la page voisine.

  Le remède n'est pas d'écrire l'onglet dans l'URL après coup — c'est que
  **l'onglet SOIT une adresse**. Chaque onglet est donc un `<a href>` vers sa
  route déclarée (`$lib/pages.ts`), et la page lit l'onglet actif dans le chemin.
  On y gagne trois choses qu'un `<button>` ne donnait pas : le lien se copie, le
  bouton Précédent revient à l'onglet précédent, et le clic milieu ouvre la
  rubrique dans un nouvel onglet du navigateur.

  ## Ce que ce composant supprime

  Les cinq pages à onglets écrivaient leur rangée à la main, et elles avaient déjà
  divergé : `<button>` nu ici, `<Onglet>` là, libellés pris dans la configuration
  sur quatre pages et **codés en dur** sur `/prestataires` — dont le troisième
  onglet n'était même pas déclaré dans la table, donc ni renommable ni
  descriptible depuis l'administration.

  ⚠️ Le libellé se replie sur celui de la TABLE, jamais sur une chaîne écrite ici :
  une configuration enregistrée avant l'ajout d'un onglet ne porte pas sa clé
  (`getPageConfig` remplace le dictionnaire entier), et l'onglet neuf s'afficherait
  sans nom.
-->
<script lang="ts">
	import Onglet from '$lib/components/Onglet.svelte';
	import { configStore, getPageConfig, defautsDePage } from '$lib/stores/pageConfig';
	import { PAGES } from '$lib/pages';
	import { safeHtml } from '$lib/sanitize';

	/** L'identifiant de configuration de la page — celui de `PAGES`. */
	export let pageId: string;
	/** L'onglet actif, tel que la page l'a résolu depuis le chemin. */
	export let actif: string;
	/**  Les onglets que l'utilisateur courant ne doit pas voir. C'est la PAGE qui
	 *   sait à quels droits ils répondent (le Kanban et les Archives du calendrier
	 *   sont fermés aux locataires) — ce composant ne connaît que l'affichage.
	 *   ⚠️ Masquer ne suffit pas : la page doit aussi refuser la route directe. */
	export let masques: readonly string[] = [];
	/** Pastilles de compte, par identifiant d'onglet. */
	export let comptes: Record<string, number> = {};

	$: defauts = defautsDePage(pageId);
	$: _pc = getPageConfig($configStore, pageId, defauts);
	$: onglets = (PAGES.find((p) => p.id === pageId)?.onglets ?? []).filter(
		(o) => !masques.includes(o.id),
	);
	$: descriptif = _pc.onglets?.[actif]?.descriptif ?? defauts.onglets?.[actif]?.descriptif ?? '';
</script>

<div class="tabs" role="tablist">
	{#each onglets as o (o.id)}
		<Onglet href={o.route} actif={actif === o.id} compte={comptes[o.id] ?? null}>
			{_pc.onglets?.[o.id]?.label ?? defauts.onglets?.[o.id]?.label ?? o.label}
		</Onglet>
	{/each}
</div>
{#if descriptif}
	<p class="tab-descriptif">{@html safeHtml(descriptif)}</p>
{/if}

<style>
	/*  `.tabs` et `.tab-btn` vivent dans la feuille commune : la rangée est un
	    conteneur d'écran, partagé avec l'administration qui garde ses boutons.
	    Ne sont ici que les écarts.

	    ⚠️ La marge basse N'Y EST PAS : la charte la porte déjà, à la même valeur.
	    Les cinq pages l'écrivaient pourtant en style EN LIGNE — cinq fois la
	    valeur dont elles héritaient. C'est `lint:charte` qui l'a dit, en refusant
	    la règle que j'avais reprise d'elles. */
	.tabs {
		padding-bottom: 0.1rem;
		/*  Les onglets DÉFILENT plutôt que de se replier — même parti que les tags
		    d'`EnteteCarte`. C'était l'écart de `/prestataires`, seule page à trois
		    onglets longs ; il n'a plus de raison d'être propre à un écran. */
		overflow-x: auto;
		scrollbar-width: thin;
	}

	/*  `:global()` IMBRIQUÉ, donc borné à cette rangée : `.tab-btn` est rendu par
	    `Onglet.svelte`, et le style d'un composant n'atteint pas le balisage d'un
	    enfant (leçon de `Pastille.svelte`, v2.67.11). Ce qui fuirait, c'est un
	    `:global()` de PAGE — cf. #672. */
	.tabs :global(.tab-btn) {
		white-space: nowrap;
	}
</style>
