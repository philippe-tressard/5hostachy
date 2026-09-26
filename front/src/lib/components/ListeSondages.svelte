<!--
  La liste des sondages — le `{#each}` et la carte, écrits **une seule fois**.

  ## Pourquoi ce composant existe (#515, 02/09/2026)

  L'onglet en rend maintenant **deux** : les sondages courants, et les Archives
  repliées — 30 jours après la date de clôture, règle du site portée par
  `app/utils/archivage.py`.

  🔴 Recopier le bloc `{#each}` sous la section repliée aurait fait soixante-dix
  lignes de carte en double. C'est ce que le rang 1 interdit, et ce qui est arrivé
  six fois au fil des tickets (#431). Troisième extraction de la même forme sur le
  même écran, après `ListeAnnonces` (18/08) et `ListeIdees` (ce jour) — les trois
  rubriques de Communauté ont enfin la même structure.

  ⚠️ Ce composant ne décide de RIEN : `s.cloture` et `s.archivee` sont tous deux
  calculés par le serveur. Le premier l'est depuis #468, après que la liste eut
  recalculé la clôture en JavaScript et divergé sur le fuseau ; le second l'est
  pour la même raison.

  Les gestes — arrêter, supprimer — restent chez le parent : c'est lui qui parle à
  l'API et recharge la liste.
-->
<script lang="ts">
	import BadgeNouveau from '$lib/components/BadgeNouveau.svelte';
	import MarqueIA from '$lib/components/MarqueIA.svelte';
	import { fmtDateShort } from '$lib/date';
	import BoutonLien from '$lib/components/BoutonLien.svelte';
	import EnteteCarte from '$lib/components/EnteteCarte.svelte';
	import { safeHtml } from '$lib/sanitize';
	import BadgePerimetre from '$lib/components/BadgePerimetre.svelte';
	import { concerneTousLesResidents, destinatairesLabel } from '$lib/destinataires';
	import { currentUser, isAdmin } from '$lib/stores/auth';

	/** Les sondages à rendre, déjà filtrés par l'appelant. */
	export let sondages: any[] = [];
	export let arreterSondage: (s: any, e: Event) => void;
	export let supprimerSondage: (s: any, e: Event) => void;
	/**  Corriger son sondage (#783). Même condition que « Stopper » : l'auteur
	 *   ou un admin, et **pas** un sondage clôturé — le serveur le refuse, et un
	 *   bouton qui déclencherait un refus serait pire qu'absent. */
	export let modifierSondage: (s: any, e: Event) => void;
</script>

{#each sondages as s (s.id)}
	<!--  🔴 Un BLOC, et un lien qui en couvre la surface (#1329) : la carte était
	      un `<a>` qui contenait des boutons — HTML invalide, et un lecteur
	      d'écran y annonçait un lien géant. Le lien s'étire sous le contenu, les
	      boutons passent au-dessus. -->
	<div class="sondage-card card">
		<a class="lien-sondage" href="/sondages/{s.id}" aria-label="Ouvrir le sondage : {s.question}"
		></a>
		<!--  L'EN-TÊTE DU SITE (#794). Cette carte était la SIXIÈME et dernière à
		      composer le sien à la main : titre en `<strong>`, date en
		      `<small style="…">`, badge « New » avec quatre propriétés CSS écrites
		      en ligne. Les cinq autres — annonce, idée, ticket, actualité,
		      événement — passent par `EnteteCarte` depuis le 18/08/2026.

		      ⚠️ `ListeIdees` portait ce jour-là le commentaire « seule carte du
		      produit dans ce cas ». C'était faux au moment où il a été écrit : le
		      sondage l'était aussi. Une correction posée sur l'écran qui l'a
		      révélée, sans passer les voisins en revue.

		      `basculable` reste faux : la carte mène à la fiche par son lien
		      étiré ; un bouton de dépliage n'y aurait rien à déplier. -->
		<EnteteCarte titre={s.question} date={fmtDateShort(s.cree_le)}>
			<svelte:fragment slot="titre-suffixe">
				<MarqueIA assiste={s.assiste_ia} />
				<BadgeNouveau le={s.cree_le} />
			</svelte:fragment>
			<svelte:fragment slot="tags">
				<span class="badge {s.cloture ? 'badge-gray' : 'badge-green'}"
					>{s.cloture ? '🔒 Clôturé' : 'Ouvert'}</span
				>
				{#if s.cloture_le && !s.cloture}
					<span class="badge badge-gray">Clôture le {fmtDateShort(s.cloture_le)}</span>
				{/if}
				<span class="badge badge-gray"
					>{s.nb_votants ?? 0} votant{(s.nb_votants ?? 0) !== 1 ? 's' : ''}</span
				>
				<!--  Ciblage affiché comme PARTOUT ailleurs : 🔹 pour le périmètre
				      logique (jamais 📍, réservé au lieu physique), et rien du tout
				      quand le ciblage est le défaut — le redire n'apprend rien. -->
				<BadgePerimetre perimetre={s.perimetre_cible} ton="blue" />
				{#if !concerneTousLesResidents(s.public_cible)}
					<span class="badge badge-orange">{destinatairesLabel(s.public_cible)}</span>
				{/if}
			</svelte:fragment>
			<svelte:fragment slot="actions">
				<!--  🔗 EN PREMIER : la seule action que TOUT le monde a. Sa position ne
				      doit pas dépendre des droits du lecteur. Même ordre que l'annonce
				      et l'idée. Un sondage a sa page : on copie SON adresse. -->
				<BoutonLien chemin="/sondages/{s.id}" quoi="le sondage" />
				{#if ($currentUser?.id === s.auteur_id || $isAdmin) && !s.cloture}
					<button
						class="btn-icon"
						aria-label="Modifier ce sondage"
						title="Modifier"
						on:click={(e) => modifierSondage(s, e)}>&#x270F;&#xFE0F;</button
					>
					<button
						class="btn-icon-warn"
						aria-label="Stopper ce sondage"
						title="Stopper"
						on:click={(e) => arreterSondage(s, e)}>⏹️</button
					>
				{/if}
				{#if $currentUser?.id === s.auteur_id || $isAdmin}
					<button
						class="btn-icon-danger"
						aria-label="Supprimer"
						title="Supprimer"
						on:click={(e) => supprimerSondage(s, e)}>&#x1F5D1;️</button
					>
				{/if}
			</svelte:fragment>
		</EnteteCarte>
		{#if s.description}
			<div class="sondage-desc rich-content clamp-3">{@html safeHtml(s.description)}</div>
		{/if}
	</div>
{/each}

<style>
	.sondage-card {
		position: relative;
		/*  Plus de `display: flex` à deux colonnes : les actions vivaient dans une
		    COLONNE à droite, qui prenait sa largeur au titre. `EnteteCarte` les
		    place sur la ligne des tags, comme les cinq autres cartes (#794). */
		display: block;
		padding: 1rem 1.25rem;
		margin-bottom: 0.5rem;
		text-decoration: none;
		color: var(--color-text);
		transition: border-color 0.12s;
	}
	@media (hover: hover) and (pointer: fine) {
		.sondage-card:hover {
			border-color: var(--color-primary);
		}
	}
	.lien-sondage {
		position: absolute;
		inset: 0;
		border-radius: inherit;
	}
	/*  Les gestes au-dessus du lien étiré : sinon il prendrait leurs clics. */
	.sondage-card :global(button) {
		position: relative;
		z-index: 1;
	}
	.sondage-desc {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		margin: 0.2rem 0 0.3rem;
	}
</style>
