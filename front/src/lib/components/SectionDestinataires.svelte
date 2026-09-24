<!--
  La section **Destinataires** du cadre — *à qui* on l'adresse.

  Extraite de `ChampsCommuns` le 22/09/2026, au fil de l'eau : le fichier
  dépassait 500 lignes et le garde-fou de modularité (rang 1) a refusé qu'il
  grossisse en relayant la fin de validité d'une actualité (#1093).

  Ce n'est pas un découpage arbitraire : **neuf sections sur onze avaient déjà
  leur composant** — `SectionQuand`, `SectionDescription`, `SectionDiffusion`,
  `SectionOptionsPublication`, `SectionWorkflow`… Les deux dernières écrites en
  ligne étaient le Périmètre et celle-ci, restées là parce qu'elles tiennent en
  quinze lignes. Une exception qui n'a d'autre raison que sa brièveté finit par
  être la raison pour laquelle le fichier ne peut plus rien recevoir.

  🔴 Le sélecteur se tait (`titre=""`) : c'est la SECTION qui nomme. Sans quoi
  on lirait « DESTINATAIRES » puis « Destinataires * », le nom deux fois —
  signalé à l'écran le 16/08/2026, dès la mise en production.
-->
<script lang="ts">
	import DestinatairePicker from '$lib/components/DestinatairePicker.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import { concerneTousLesResidents } from '$lib/destinataires';
	import { SECTIONS_LIBELLE } from '$lib/entites/types';

	/** Préfixe des identifiants — l'écran en ouvre parfois plusieurs à la fois. */
	export let idPrefixe: string;

	export let premiere = false;

	/** Repliée par défaut — la valeur vient de la déclaration (#1095). */
	export let pliable = false;

	export let destinataires: string[] = ['résidents'];

	/**  🔴 Il est REÇU, plus écrit en dur (22/09/2026).
	 *
	 *   Ce composant posait `requis` lui-même. La déclaration ne le savait donc
	 *   pas, et `lint:etats` ne pouvait pas voir qu'une section obligatoire
	 *   était déclarée pliée : l'écran affichait « DESTINATAIRES* » sur une
	 *   ligne fermée, ce que la règle interdit — signalé à l'écran, deux fois.
	 *
	 *   ⚠️ Même angle mort que `pliable` le matin même : ce qu'un composant
	 *   PORTEUR écrit lui-même échappe à la déclaration qui gouverne les
	 *   autres. `lint:pliage-transmis` le refuse désormais pour les deux. */
	export let requis = false;

	/**  Le badge du TITRE de section, calculé ici et nulle part ailleurs.
	 *
	 *   Il n'invente rien : `concerneTousLesResidents` est la fonction qu'emploie
	 *   déjà le sélecteur lui-même. */
	$: badge = concerneTousLesResidents(destinataires) ? 'Tous les résidents' : '';
	/** Le motif d'extinction de la section, ou `''` (`inactivePour`, #1191). */
	export let inactive = '';
</script>

<SectionFormulaire
	{premiere}
	{pliable}
	{badge}
	titre={SECTIONS_LIBELLE.destinataires}
	{inactive}
	{requis}
	rempli={destinataires.length > 0}
	valeurModifiee={!concerneTousLesResidents(destinataires)}
	idTitre="{idPrefixe}-destinataires-titre"
>
	<!--  Les pastilles ne sont pas un contrôle labelable — `for` n'y associerait
	      rien —, d'où le couple `id` sur le titre / `aria-labelledby` sur le
	      groupe. -->
	<div class="field champ-large" role="group" aria-labelledby="{idPrefixe}-destinataires-titre">
		<DestinatairePicker bind:value={destinataires} titre="" />
	</div>
</SectionFormulaire>
