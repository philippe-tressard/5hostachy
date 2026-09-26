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

  ## La pastille de lecture (lot 1, 25/09/2026)

  Quand l'écran dit la NATURE (`lecture`), la section répond à « qui d'autre
  la lit ? » : la pastille est son badge d'état — et son résumé, pliée —, la
  case « Confidentielle » l'ouvre, et la phrase entière se lit dessous.
  Sans `lecture`, la section reste celle d'avant (sondages, événements).

  ## Une affaire choisit ses destinataires (#1343, 26/09/2026)

  *« il n'est toujours pas possible de choisir son destinataire ! c'est
  urgent »* — dans toute édition. Les pastilles sont TOUJOURS là, présélection
  faite par la nature (`destinatairesParDefaut`) ; le conseil les change à tout
  moment. Ce qu'il laisse tel quel reste VIDE — la règle de la nature, qui
  suivra l'affaire si elle se date —, ce qu'il change est retenu, et le
  serveur l'applique (`ticket_visible`). « Résident concerné » y remplace la
  case Confidentielle : l'auteur, ou la personne pour qui elle a été saisie,
  et le conseil — c'est ce que le drapeau a toujours voulu dire sur une affaire.
-->
<script lang="ts">
	import DestinatairePicker from '$lib/components/DestinatairePicker.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import CaseConfidentielle from '$lib/components/CaseConfidentielle.svelte';
	import { LIBELLE_TOUS, concerneTousLesResidents } from '$lib/destinataires';
	import { SECTIONS_LIBELLE } from '$lib/entites/types';
	import { destinatairesParDefaut, lectureDe, titreLecture } from '$lib/lecture';
	import { perimetreRestreint, type NatureLue } from '$lib/lecture-ticket';
	import { perimetresStore } from '$lib/stores/perimetres';
	import { relire } from '$lib/utils';

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
	$: badge = concerneTousLesResidents(destinataires) ? LIBELLE_TOUS : '';
	/** Le motif d'extinction de la section, ou `''` (`inactivePour`, #1191). */
	export let inactive = '';

	/**  La nature lue — `null` : pas de pastille de lecture (section d'avant).
	 *   Avec elle viennent la case, le périmètre et sa réserve, qui la décident. */
	export let lecture: NatureLue | null = null;
	export let confidentiel = false;
	export let perimetre: string[] = [];
	export let reservePerimetre = false;
	/**  Les destinataires d'une affaire sans choix — donnés par une Suite, qui
	 *   n'a pas de `lecture` ; déduits de la nature sinon. `null` : aucun. */
	export let parDefaut: string[] | null = null;
	/** Le « Résident concerné » — l'auteur, ou pour qui elle a été saisie. */
	export let concerne = '';
	$: defaut = lecture && !lecture.actualite ? destinatairesParDefaut(lecture) : parDefaut;
	const cle = (c: string[]) => [...c].sort().join();
	/**  Vide = la règle de la nature : ce qui revient au défaut n'est pas un choix. */
	function choisir(e: CustomEvent<string[]>) {
		destinataires = defaut && cle(e.detail) === cle(defaut) ? [] : e.detail;
	}
	$: lue = relire($perimetresStore, () =>
		lectureDe({
			actualite: !!lecture?.actualite,
			datee: lecture?.datee,
			enAg: lecture?.enAg,
			confidentiel,
			publicCible: destinataires,
			perimetreRestreint: perimetreRestreint(perimetre),
			reservePerimetre,
		}),
	);
	$: modifiee =
		confidentiel || (defaut ? destinataires.length > 0 : !concerneTousLesResidents(destinataires));
</script>

<SectionFormulaire
	{premiere}
	{pliable}
	badge={lecture ? titreLecture(lue) : badge}
	badgeIcones={lecture ? lue.icones : []}
	badgeIconeFin={lecture && lue.perimetreReserve ? 'lock' : ''}
	titre={SECTIONS_LIBELLE.destinataires}
	{inactive}
	{requis}
	rempli={destinataires.length > 0 || !!defaut}
	valeurModifiee={modifiee}
	idTitre="{idPrefixe}-destinataires-titre"
>
	{#if lecture?.actualite}
		<CaseConfidentielle bind:coche={confidentiel} />
	{/if}
	{#if defaut}
		<!--  « Résident concerné » est UNE PASTILLE DE LA RANGÉE, entre Locataires
		      et Conseil syndical (arbitré à l'écran le 26/09/2026) — pas une ligne
		      à part : c'est un destinataire comme les autres, le plus restreint
		      avant le conseil seul. Choisie, elle éteint les autres. -->
		<fieldset
			class="field champ-large destinataires-groupe"
			aria-labelledby="{idPrefixe}-destinataires-titre"
		>
			<DestinatairePicker
				value={destinataires.length ? destinataires : defaut}
				titre=""
				concerne={lecture || parDefaut
					? `Résident concerné${concerne ? ` : ${concerne}` : ''}`
					: null}
				concerneActif={confidentiel}
				on:change={choisir}
				on:concerne={(e) => (confidentiel = e.detail)}
			/>
		</fieldset>
	{:else}
		<!--  Les pastilles ne sont pas un contrôle labelable — `for` n'y associerait
		      rien —, d'où le couple `id` sur le titre / `aria-labelledby` sur le
		      groupe. Éteintes, pas effacées, quand « Confidentielle » passe outre :
		      `disabled` d'un `fieldset` désactive chaque bouton sans les recopier. -->
		<fieldset
			class="field champ-large destinataires-groupe"
			disabled={lecture !== null && confidentiel}
			aria-labelledby="{idPrefixe}-destinataires-titre"
		>
			<DestinatairePicker bind:value={destinataires} titre="" />
		</fieldset>
	{/if}
	{#if lecture}
		<p class="aide">
			{lue.phrase}
			{lue.exclus}
		</p>
		{#if lue.avertissement}<p class="aide avertissement">{lue.avertissement}</p>{/if}
	{/if}
</SectionFormulaire>

<style>
	/*  Un `fieldset` sans son cadre natif : il ne sert qu'à éteindre le groupe. */
	.destinataires-groupe {
		border: none;
		margin: 0;
		padding: 0;
		min-width: 0;
	}
	.destinataires-groupe:disabled {
		opacity: 0.45;
	}
	.avertissement {
		color: var(--color-warning, #b07d1e);
	}
</style>
