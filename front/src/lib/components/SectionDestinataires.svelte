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

	/**  Le badge du TITRE de section, calculé ici et nulle part ailleurs.
	 *
	 *   Il n'invente rien : `concerneTousLesResidents` est la fonction qu'emploie
	 *   déjà le sélecteur lui-même. */
	$: badge = concerneTousLesResidents(destinataires) ? 'Tous les résidents' : '';
</script>

<SectionFormulaire
	{premiere}
	{pliable}
	{badge}
	titre={SECTIONS_LIBELLE.destinataires}
	requis
	rempli={destinataires.length > 0}
	ouvrirSiRenseignee={!concerneTousLesResidents(destinataires)}
	idTitre="{idPrefixe}-destinataires-titre"
>
	<!--  Les pastilles ne sont pas un contrôle labelable — `for` n'y associerait
	      rien —, d'où le couple `id` sur le titre / `aria-labelledby` sur le
	      groupe. -->
	<div class="field champ-large" role="group" aria-labelledby="{idPrefixe}-destinataires-titre">
		<DestinatairePicker bind:value={destinataires} titre="" />
	</div>
</SectionFormulaire>
