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
	//  Glyphes et libellés : la table est la source unique (`$lib/options-publication`).
	//  Ils étaient écrits ici ET dans les badges de `CarteActualite`, et avaient
	//  divergé — l'épinglage n'avait pas de glyphe ici et 📌 là-bas.
	import {
		actionOption,
		optionPublication,
		type CleOptionPublication,
	} from '$lib/options-publication';

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
	/**  🔒 DÉJÀ ACQUIS — le motif pour lequel cette entité est TOUJOURS restreinte
	 *   à son périmètre. Vide quand le choix se pose vraiment.
	 *
	 *   Demandé à l'écran le 05/09/2026 : *« il manque l'option confidentiel sur
	 *   l'objet Options de publication »*. Sur un ticket, elle ne pouvait rien
	 *   restreindre — sa lecture passe par `perimetre_visible` SANS
	 *   `ouvert_a_la_copropriete`, là où une actualité le passe (#339) : le ticket
	 *   se comporte déjà comme une actualité confidentielle.
	 *
	 *   Plutôt que de l'omettre (l'option manquait) ou de la rendre cochable
	 *   (elle n'aurait rien fait — une promesse vide), elle est montrée **cochée
	 *   et verrouillée**, avec son motif écrit. Ce n'est pas une case morte :
	 *   c'est un ÉTAT de l'objet, et il vaut la peine d'être lu. */
	export let confidentielAcquis = '';

	/**  Le nom de l'objet décrit — « publication », « ticket ». Il entre dans les
	 *   libellés qui le nomment (« Visibilité du **ticket** au seul conseil
	 *   syndical ») : la même case sert deux entités, et « ce truc-là » ne se dit
	 *   pas. */
	export let objet = 'publication';

	/**  Les options RENDUES, dans l'ordre de la table. Toutes par défaut — un
	 *   ticket n'en porte qu'une, faute de colonne pour l'épinglage et l'urgence,
	 *   qu'il exprime par sa catégorie (05/09/2026). */
	export let options: CleOptionPublication[] = ['epingle', 'urgente', 'brouillon', 'confidentiel'];
	$: rendue = (cle: CleOptionPublication) => options.includes(cle);

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
	//  Les quatre options, lues UNE fois dans la table. Constantes de module et
	//  non `{@const}` de balisage : Svelte ne l'admet pas comme enfant direct
	//  d'un `<div>`, et ces valeurs ne dépendent d'aucun état.
	const optEpingle = optionPublication('epingle');
	const optUrgente = optionPublication('urgente');
	const optBrouillon = optionPublication('brouillon');
	const optConfidentiel = optionPublication('confidentiel');

	$: rienARestreindre = concerneTous(perimetreCible);

	//  Le périmètre peut changer APRÈS que la case a été cochée : on ne laisse pas
	//  une valeur devenue impossible partir dans la requête.
	$: if (rienARestreindre && confidentiel) confidentiel = false;
</script>

<div class="cases">
	<!--  Les glyphes et les intitulés viennent de la table, jamais du balisage :
	      c'est ce qui garantit qu'une case et le badge correspondant montrent la
	      même chose. Les LIAISONS, elles, restent explicites — `bind:checked` a
	      besoin d'une variable nommée, et une boucle générique obligerait à un
	      objet intermédiaire que l'hôte devrait ensuite redéfaire. -->
	{#if rendue('epingle')}
		<label class="checkbox-field" title={optEpingle?.aide}>
			<input type="checkbox" bind:checked={epingle} />
			{optEpingle?.glyphe}
			{optEpingle && actionOption(optEpingle, objet)}
		</label>
	{/if}
	{#if rendue('urgente')}
		<label class="checkbox-field" title={optUrgente?.aide}>
			<input type="checkbox" bind:checked={urgente} />
			{optUrgente?.glyphe}
			{optUrgente && actionOption(optUrgente, objet)}
		</label>
	{/if}
	{#if rendue('brouillon')}
		<label class="checkbox-field" title={optBrouillon?.aide}>
			<input type="checkbox" bind:checked={brouillon} />
			{optBrouillon?.glyphe}
			{optBrouillon && actionOption(optBrouillon, objet)}
		</label>
	{/if}
	{#if rendue('confidentiel')}
		<label
			class="checkbox-field"
			class:desactivee={rienARestreindre || confidentielAcquis}
			title={confidentielAcquis ||
				(rienARestreindre
					? "Le périmètre sélectionné concerne déjà tous les résidents : il n'y a rien à restreindre."
					: optConfidentiel?.aide)}
		>
			<input
				type="checkbox"
				checked={confidentielAcquis ? true : confidentiel}
				on:change={(e) => (confidentiel = e.currentTarget.checked)}
				disabled={!!confidentielAcquis || rienARestreindre}
				aria-describedby={rienARestreindre || confidentielAcquis ? idAideConfidentiel : undefined}
			/>
			{optConfidentiel?.glyphe}
			{optConfidentiel && actionOption(optConfidentiel, objet)} — visible du seul périmètre sélectionné
		</label>
	{/if}
</div>

{#if rendue('confidentiel') && confidentielAcquis}
	<!--  Le motif est ÉCRIT, pas seulement en infobulle : au doigt il n'y a pas
	      de survol, et un lecteur d'écran ne lit pas un `title` sans l'y
	      chercher (leçon du 28/08/2026). -->
	<p class="aide" id={idAideConfidentiel}>{confidentielAcquis}</p>
{:else if rendue('confidentiel') && rienARestreindre}
	<p class="aide" id={idAideConfidentiel}>
		&#x1F512; <strong>Confidentiel</strong> demande un périmètre restreint — un bâtiment, par exemple.
		Le périmètre choisi concerne déjà tous les résidents : il n'y a rien à leur cacher.
	</p>
{:else if rendue('confidentiel') && confidentiel}
	<p class="aide">
		&#x1F512; Seuls les résidents du périmètre sélectionné verront cette actualité — ni dans le fil,
		ni par un lien direct pour les autres. Le réglage reste modifiable après publication.
	</p>
	<!--  🔴 CE QUI SORT, canal par canal (#623, 29/08/2026).
	      L'auteur découvrait la conséquence après l'envoi, ou jamais. Et elle
	      n'est PAS la même partout : le titre part sur WhatsApp, tout part par
	      e-mail. Un avertissement qui dirait « le contenu ne sort pas » serait
	      faux sur un canal sur deux — et une assurance fausse au moment précis
	      où l'auteur décide est pire que pas d'avertissement.

	      ⚠️ Il s'affiche dès que « Confidentiel » est coché, sans attendre que
	      les canaux le soient : c'est en écrivant le TITRE qu'il faut le savoir,
	      pas au moment de cocher un envoi. -->
	<div class="avert-diffusion" role="note">
		<p class="avert-titre">&#x26A0;&#xFE0F; Ce qui sortira de l'application</p>
		<ul class="avert-liste">
			<li>
				<strong>Groupe WhatsApp</strong> — le <strong>titre</strong> et le périmètre partent, avec
				un lien vers l'application. Le contenu, lui, ne sort pas.
				<span class="avert-consigne"
					>Le groupe est commun à toute la copropriété : n'écrivez rien de confidentiel dans le
					titre.</span
				>
			</li>
			<li>
				<strong>Syndic et conseil syndical</strong> — l'e-mail part
				<strong>en entier</strong>, titre et contenu, sans restriction.
			</li>
		</ul>
	</div>
{/if}

<AlerteEpinglage coche={epingle} {dejaEpingle} />

<style>
	.cases {
		display: flex;
		gap: 1.5rem;
		flex-wrap: wrap;
		margin-bottom: 1rem;
	}
	/*  🔴 `.checkbox-field` A DÉMÉNAGÉ dans `styles/composants.css` (02/09/2026),
	    et c'est une correction. La règle qui vivait ici ne s'appliquait qu'à
	    l'intérieur de `.cases` — or HUIT fichiers emploient la classe (profil,
	    inscription, notifications, diffusion, formulaire de ticket…), et partout
	    ailleurs la case se rendait NUE, sans alignement ni curseur.
	    ⚠️ Le commentaire qui était ici affirmait que `.checkbox-field` était
	    « une classe partagée du thème ». C'était faux, et jamais vérifié : il
	    décrivait ce qu'on croyait avoir fait. `lint:classes-nues` l'a vu au 9e
	    usage, pas avant. */
	/*  Une case grisée doit se VOIR grisée, pas seulement refuser le clic. */
	.cases .desactivee {
		opacity: 0.5;
		cursor: not-allowed;
	}
	/*  L'avertissement de diffusion : encadré, pas un simple paragraphe d'aide.
	    Il annonce une conséquence IRRÉVERSIBLE — un message parti ne se retire
	    pas d'un groupe — là où `.aide` explique un réglage. Deux niveaux de
	    gravité, deux rendus. */
	.avert-diffusion {
		border-left: 3px solid var(--color-warning, #b07d1e);
		background: var(--color-warning-light, #fffbeb);
		border-radius: var(--radius);
		padding: 0.6rem 0.8rem;
		margin: -0.25rem 0 1rem;
	}
	.avert-titre {
		margin: 0 0 0.35rem;
		font-size: 0.8rem;
		font-weight: 600;
	}
	.avert-liste {
		margin: 0;
		padding-left: 1.1rem;
		font-size: 0.78rem;
		line-height: 1.5;
		color: var(--color-text);
	}
	.avert-liste li + li {
		margin-top: 0.3rem;
	}
	/*  La consigne d'écriture sur sa propre ligne : c'est la SEULE phrase qui
	    demande une action de l'auteur, les autres décrivent. */
	.avert-consigne {
		display: block;
		margin-top: 0.15rem;
		font-style: italic;
	}
	.aide {
		font-size: 0.78rem;
		color: var(--color-text-muted);
		margin: -0.5rem 0 1rem;
		line-height: 1.45;
	}
	/*  Sous 480 px, les cases passent en colonne et gagnent une cible tactile
	    de 44 px (socle 11 §10) — même règle que `CanauxNotification`. */
	@media (max-width: 480px) {
		.cases {
			flex-direction: column;
			gap: 0.25rem;
		}
		.cases :global(.checkbox-field) {
			min-height: 44px;
		}
	}
</style>
