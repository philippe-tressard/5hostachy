<!--
  OptionsPublication.svelte — les options d'une actualité, écrites une fois.

  Extrait de `routes/(app)/actualites/+page.svelte` le 15/08/2026, au fil de
  l'eau : cette page tenait 750 lignes et le contrôle de modularité refuse qu'un
  fichier déjà au-dessus de 500 grossisse (rang 1 §4). Il fallait y ajouter la
  case « 🔒 Confidentiel » (#347) — et la rangée de cases était de toute façon
  écrite DEUX fois dans la page, une pour la création, une pour l'édition, sans
  que rien n'oblige les deux à rester d'accord.

  Elles ne l'étaient déjà plus : la création montrait les canaux de notification
  et l'affiche de hall, l'édition non. Cet écart-là est conservé (`complet`),
  parce qu'il a une raison — on ne renvoie pas une notification en corrigeant une
  faute de frappe — mais il est désormais **déclaré**, et non subi.

  ## Les deux règles que ce composant fait respecter à l'écran

  1. **« Confidentiel » exige un périmètre restreint.** Sur un périmètre qui
     concerne déjà tous les résidents, il n'y a rien à restreindre : la case est
     désactivée, et le texte dit pourquoi. Une case inerte sans explication laisse
     l'utilisateur croire à un bug (`standards/11`, accessibilité).
  2. **« Confidentiel » interdit l'affiche de hall.** Une affiche est punaisée
     dans un hall et lue par n'importe qui : il n'y a aucun contrôle d'accès
     derrière, contrairement au message WhatsApp dont le lien renvoie vers
     l'application. Le blocage vaut dans les deux sens — cocher « Confidentiel »
     sur une actualité déjà retenue pour le hall l'en retire.

  ⚠️ Ces deux règles sont **aussi** tenues côté serveur
  (`api/app/routers/publications/commun.py`, `appliquer_confidentialite`). Celles
  d'ici ne sont qu'un confort d'écran : c'est le serveur qui décide.
-->
<script lang="ts">
	import AlerteEpinglage from './AlerteEpinglage.svelte';
	import CanauxNotification from './CanauxNotification.svelte';
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
	/** Canaux de notification et affiche de hall : création seulement. */
	export let complet = false;
	export let whatsapp = false;
	export let syndic = false;
	export let cs = false;
	export let annonceHall = false;

	//  Identifiants uniques : deux formulaires peuvent coexister à l'écran (la
	//  création est ouverte pendant qu'une actualité est dépliée), et deux
	//  `aria-describedby` pointant sur le même id ne décrivent plus rien.
	const suffixe = Math.random().toString(36).slice(2, 8);
	const idAideConfidentiel = `aide-confidentiel-${suffixe}`;
	const idAideHall = `aide-hall-${suffixe}`;

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
	//  Et la symétrie de la règle 2, dans le sens « je coche Confidentiel ».
	$: if (confidentiel && annonceHall) annonceHall = false;
</script>

<div class="cases">
	<label class="checkbox-field"><input type="checkbox" bind:checked={epingle} /> Épingler</label>
	<label class="checkbox-field"><input type="checkbox" bind:checked={urgente} /> &#x1F6A8; Urgent</label>
	<label class="checkbox-field">
		<input type="checkbox" bind:checked={brouillon} />
		✏️ Brouillon{complet ? ' (invisible pour les résidents)' : ''}
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

{#if complet}
	<CanauxNotification
		bind:whatsapp
		bind:syndic
		bind:cs
		aideWhatsapp={confidentiel
			? "Le groupe est commun à toute la copropriété : le message ne portera ni le titre ni le contenu, seulement le périmètre concerné et un lien vers l'application."
			: "Le message est publié sur le groupe WhatsApp ; l'image jointe part avec."}
	/>

	<!--  L'annonce de hall n'est PAS un canal de notification : elle produit
	      une affiche PDF. Elle reste donc hors de `CanauxNotification`,
	      dont le contrat est « qui est prévenu ? ». -->
	<div class="bloc-hall">
		<label
			class="checkbox-field"
			class:desactivee={confidentiel}
			title={confidentiel
				? "Indisponible : une actualité confidentielle ne peut pas être affichée dans un hall."
				: "Génère l'affiche PDF à afficher dans le hall et l'envoie au CS du périmètre"}
		>
			<input
				type="checkbox"
				bind:checked={annonceHall}
				disabled={confidentiel}
				aria-describedby={confidentiel ? idAideHall : undefined}
			/>
			<span class="ico">&#x1F4C4;</span>
			<span>Créer une annonce Hall</span>
		</label>
	</div>

	{#if confidentiel}
		<p class="aide" id={idAideHall}>
			&#x1F4C4; L'affiche de hall est indisponible sur une actualité confidentielle : une
			affiche est punaisée dans un hall et lue par n'importe qui, sans connexion. Le message
			WhatsApp, lui, reste possible — il renvoie vers l'application, qui applique la règle.
		</p>
	{:else if annonceHall}
		<p class="aide">
			&#x1F4C4; Une affiche PDF sera générée à partir du titre, du contenu, du périmètre et de
			l'image de cette actualité, puis envoyée aux membres du CS du périmètre. Elle sera
			consultable dans <strong>Espace CS → Annonces Hall</strong>. Un brouillon ne déclenche
			rien tant qu'il n'est pas publié.
		</p>
	{/if}
{/if}

<style>
	.cases {
		display: flex;
		gap: 1.5rem;
		flex-wrap: wrap;
		margin-bottom: 1rem;
	}
	/*  `:global` parce que `.checkbox-field` est une classe partagée du thème —
	    même raison que dans `CanauxNotification.svelte`. */
	.cases :global(.checkbox-field),
	.bloc-hall :global(.checkbox-field) {
		display: flex;
		align-items: center;
		gap: .4rem;
		font-size: .875rem;
		cursor: pointer;
	}
	/*  Une case grisée doit se VOIR grisée, pas seulement refuser le clic. */
	.cases .desactivee,
	.bloc-hall .desactivee {
		opacity: .5;
		cursor: not-allowed;
	}
	.bloc-hall {
		margin-bottom: 1rem;
	}
	.ico {
		font-size: 1.1em;
		line-height: 1;
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
