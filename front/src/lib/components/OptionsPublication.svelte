<!--
  OptionsPublication.svelte — les quatre options qui DÉCRIVENT une actualité :
  épinglage, urgence, brouillon, confidentialité. **Section 2 du cadre #430**
  (champs spécifiques), rendue à la création comme à l'édition.

  Extrait de `routes/(app)/actualites/+page.svelte` le 15/08/2026 (la rangée de
  cases y était écrite DEUX fois, sans que rien n'oblige les deux à rester
  d'accord), puis **amputé de sa moitié « acte » le 18/08/2026** (#433).

  ## Pourquoi la coupure (#433)

  Ce composant portait aussi les canaux de notification et l'affiche de hall,
  sous un drapeau `complet` qui les réservait à la création. Le cadre a rendu ce
  drapeau intenable : **les sections 1 à 8 décrivent l'entité, la 9 est un acte**,
  et la 9 est absente de l'édition (*une correction n'est pas une nouvelle*). Un
  composant à cheval sur les deux ne pouvait donc plus être rendu nulle part sans
  mentir — dans la section 2 il aurait glissé des canaux là où on décrit ;
  dans la 9, il aurait emporté avec lui les quatre options **et supprimé le seul
  chemin qui permet de publier un brouillon**.

  Ce qui part : `CanauxNotification` et l'affiche de hall → `DiffusionPublication`.
  Ce qui reste : ce qui se corrige.

  ## La règle que ce composant fait respecter à l'écran

  **« Confidentiel » exige un périmètre restreint.** Sur un périmètre qui concerne
  déjà tous les résidents, il n'y a rien à restreindre : la case est désactivée, et
  le texte dit pourquoi. Une case inerte sans explication laisse l'utilisateur
  croire à un bug (`standards/11`, accessibilité).

  ⚠️ La seconde règle — **« Confidentiel » interdit l'affiche de hall** — enjambe
  désormais deux sections : elle vit chez l'hôte (`FormulaireActualite`), seul
  endroit où les deux valeurs se rencontrent. Les deux sont **aussi** tenues côté
  serveur (`api/app/routers/publications/commun.py`, `appliquer_confidentialite`) ;
  celles d'ici ne sont qu'un confort d'écran — c'est le serveur qui décide.
-->
<script lang="ts">
	import AlerteEpinglage from './AlerteEpinglage.svelte';
	import { concerneTous } from '$lib/utils';

	/** Épingler en tête du fil. */
	export let epingle = false;
	/** Marquer urgent (bord gauche rouge, pas de badge texte). */
	export let urgente = false;
	/** Brouillon : invisible pour les résidents, ne déclenche aucun envoi. */
	export let brouillon = false;
	/** Lecture réservée au périmètre visé (#347). */
	export let confidentiel = false;
	/** Le périmètre sélectionné, qui décide si « Confidentiel » a un sens. */
	export let perimetreCible: string[] = [];
	/** L'élément édité était-il DÉJÀ épinglé ? (évite un double comptage) */
	export let dejaEpingle = false;

	//  Identifiant unique : deux formulaires peuvent coexister à l'écran (la
	//  création est ouverte pendant qu'une actualité est dépliée), et deux
	//  `aria-describedby` pointant sur le même id ne décrivent plus rien.
	const idAideConfidentiel = `aide-confidentiel-${Math.random().toString(36).slice(2, 8)}`;

	//  « Rien à restreindre » : le périmètre choisi concerne déjà tout le monde.
	//  C'est le miroir exact de `a_portee_globale` côté serveur — la question
	//  n'est pas « est-ce la copropriété entière ? » mais « est-ce que cocher
	//  changerait quelque chose ? ». Sur un nœud à portée globale, non : le
	//  serveur laisse passer tout le monde avant même de regarder le bâtiment, et
	//  le cadenas affiché ne protégerait rien.
	$: rienARestreindre = concerneTous(perimetreCible);

	//  Le périmètre peut changer APRÈS que la case a été cochée : on ne laisse pas
	//  une valeur devenue impossible partir dans la requête.
	$: if (rienARestreindre && confidentiel) confidentiel = false;
</script>

<div class="cases">
	<label class="checkbox-field"><input type="checkbox" bind:checked={epingle} /> Épingler</label>
	<label class="checkbox-field"><input type="checkbox" bind:checked={urgente} /> &#x1F6A8; Urgent</label>
	<label class="checkbox-field">
		<input type="checkbox" bind:checked={brouillon} />
		✏️ Brouillon (invisible pour les résidents)
	</label>
	<label
		class="checkbox-field"
		class:desactivee={rienARestreindre}
		title={rienARestreindre
			? "Le périmètre sélectionné concerne déjà tous les résidents : il n'y a rien à restreindre."
			: "Seuls les résidents du périmètre sélectionné verront cette actualité."}
	>
		<input
			type="checkbox"
			bind:checked={confidentiel}
			disabled={rienARestreindre}
			aria-describedby={rienARestreindre ? idAideConfidentiel : undefined}
		/>
		&#x1F512; Confidentiel — visible du seul périmètre sélectionné
	</label>
</div>

{#if rienARestreindre}
	<p class="aide" id={idAideConfidentiel}>
		&#x1F512; <strong>Confidentiel</strong> demande un périmètre restreint — un bâtiment, par
		exemple. Le périmètre choisi concerne déjà tous les résidents : il n'y a rien à leur
		cacher.
	</p>
{:else if confidentiel}
	<p class="aide">
		&#x1F512; Seuls les résidents du périmètre sélectionné verront cette actualité — ni dans le
		fil, ni par un lien direct pour les autres. Le réglage reste modifiable après publication.
	</p>
{/if}

<AlerteEpinglage coche={epingle} {dejaEpingle} />

<style>
	.cases {
		display: flex;
		gap: 1.5rem;
		flex-wrap: wrap;
		margin-bottom: 1rem;
	}
	/*  `:global` parce que `.checkbox-field` est une classe partagée du thème —
	    même raison que dans `CanauxNotification.svelte`. */
	.cases :global(.checkbox-field) {
		display: flex;
		align-items: center;
		gap: .4rem;
		font-size: .875rem;
		cursor: pointer;
	}
	/*  Une case grisée doit se VOIR grisée, pas seulement refuser le clic. */
	.cases .desactivee {
		opacity: .5;
		cursor: not-allowed;
	}
	.aide {
		font-size: .78rem;
		color: var(--color-text-muted);
		margin: -.5rem 0 1rem;
		line-height: 1.45;
	}
	/*  Sous 480 px, les cases passent en colonne et gagnent une cible tactile
	    de 44 px (socle 11 §10) — même règle que `CanauxNotification`. */
	@media (max-width: 480px) {
		.cases {
			flex-direction: column;
			gap: .25rem;
		}
		.cases :global(.checkbox-field) {
			min-height: 44px;
		}
	}
</style>
