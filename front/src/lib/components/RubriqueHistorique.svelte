<!--
  RubriqueHistorique.svelte — LE FIL, écrit une fois.

  ## Vocabulaire (cadre #430, tranché le 17/08/2026)

  **Historique** = le fil. **Évolution** = une entrée du fil. « Commentaire » est
  abandonné : le mot est trop étroit, l'entrée pouvant porter un changement
  d'état, des pièces jointes et une diffusion. C'est déjà le vocabulaire du code
  (`TicketEvolution`, `EvolForm`), et l'adopter *supprime* un troisième registre.

  ⚠️ Le cadre parle d'évolutions ; **l'écran parle de gestes** — « Commenter »,
  « Changer l'état », « Modifier ». « Ajouter une évolution » ne veut rien dire
  pour un résident, et ce composant n'écrit donc ce mot nulle part.

  ## Pourquoi il naît (#431)

  Le fil était rendu **à la main six fois** dans le produit, dont **trois fois
  dans les deux seuls fichiers des tickets** : la liste (carte active), la liste
  (carte d'archive) et la fiche. Le CSS `.evol-list` était redéfini quatre fois.

  Et ces copies avaient **déjà divergé** :

  | Écart | Où |
  |---|---|
  | pièces jointes des évolutions **absentes** | un des deux fils de l'Espace CS |
  | marge haute du fil perdue | fiche du ticket |
  | « Voir les N **entrées** » / « Voir les N **évolutions** » | liste / fiche |
  | une réponse rendue en texte riche / réduite à « Nouvelle réponse (…) » | liste / fiche |

  La dernière n'est pas cosmétique : sur la liste, le fil est le SEUL endroit où
  le contenu d'une réponse apparaît. Retenu : le texte riche, partout — c'est la
  forme qui ne perd jamais d'information.

  ## R5 — cette rubrique ne s'est PAS généralisée dans ce lot

  Trois recopies sur six sont remplacées ici. Les trois autres (Espace CS ×2,
  Actualités) attendent que celle-ci se fasse constater à l'écran : *une rubrique
  se propose sur un écran, se fait constater, puis se généralise*. Jamais
  l'inverse — c'est la pastille partie nue en production qui a fait écrire cette
  règle.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import PiecesJointes from './PiecesJointes.svelte';
	import { safeDescription } from '$lib/sanitize';
	import { fmtDatetime } from '$lib/date';
	import { perimetreLabel } from '$lib/perimetres';
	import { evolutionIcone } from '$lib/evolutions';

	/**  Une entrée du fil. Volontairement structurel et non `TicketEvolution` :
	     les actualités ont leur propre type d'évolution, et cette rubrique doit
	     pouvoir les recevoir sans que le composant connaisse une seule entité. */
	interface Entree {
		id: number;
		type: string;
		contenu?: string;
		ancien_statut?: string;
		nouveau_statut?: string;
		auteur_id?: number;
		auteur_nom?: string;
		cree_le: string;
		fichiers_urls?: string[];
		/** Le périmètre que cette entrée déclare, quand elle en déclare un (#497). */
		perimetre_cible?: string[];
	}

	export let evolutions: Entree[] = [];
	/** Libellés du workflow — `STATUT_TICKET_LABELS` et rien d'autre (#415). */
	export let statutLabels: Record<string, string> = {};
	/** En-tête de la rubrique. Vide : le fil s'insère dans un bloc déjà nommé. */
	export let titre = '';
	/** Texte affiché quand le fil est vide. Vide : la rubrique ne rend rien. */
	export let vide = '';
	/** Au-delà de ce nombre d'entrées, le fil se replie sur `apercu`. */
	export let seuil = 7;
	export let apercu = 5;
	/**  L'écran autorise-t-il la correction ? Interrupteur GÉNÉRAL : un écran de
	 *   pure lecture le laisse à `false`. Il ne dit pas QUI peut corriger — cela
	 *   se décide par entrée, ci-dessous. */
	export let peutModifier = false;
	/**  Qui regarde, et est-il administrateur ? La règle du serveur est « l'auteur
	 *   de l'entrée, ou un admin » ; sans ces deux valeurs, l'écran ne peut que
	 *   l'approximer — et il l'approximait par « membre du CS », donc trop large :
	 *   le crayon s'affichait sur l'entrée d'un autre, le clic partait, le serveur
	 *   répondait 403, et l'écran annonçait « Accès refusé » pour un geste qu'il
	 *   avait lui-même proposé.
	 *
	 *   ⚠️ Le serveur refait le contrôle : ceci n'est qu'un confort d'écran
	 *   (`standards/03` §1). Cacher un bouton n'a jamais protégé quoi que ce soit.
	 */
	export let currentUserId: number | undefined = undefined;
	export let estAdmin = false;
	/** Entrée actuellement ouverte en correction — le parent porte l'état. */
	export let enEdition: number | null = null;

	const dispatch = createEventDispatcher<{ modifier: number; supprimer: number }>();

	//  🔴 Les MÊMES MOTS que le serveur, et dans le même ordre — types puis
	//  identité. Une règle d'écran qui paraphrase une règle de serveur finit
	//  toujours par en dire autre chose ; ici on peut au moins les comparer.
	//
	//  `reponse` est exclu : une réponse du CS n'est pas une entrée de suivi, et
	//  le serveur la refuse déjà (« ce type d'évolution ne peut pas être modifié »).
	const TYPES_CORRIGEABLES = ['commentaire', 'etat'];

	/**  Ce qui s'EFFACE — les MÊMES types que le serveur, et dans le même ordre.
	 *
	 *   ⚠️ Les transitions d'état en font partie depuis le 18/08/2026, et c'est un
	 *   arbitrage CORRIGÉ : je les avais exclues de moi-même (« un mouvement de
	 *   workflow est un fait, pas un texte qu'on rature »), alors que la demande
	 *   était « une suppression pour les historiques », sans distinction. L'absence
	 *   a été constatée dès la première entrée d'état rencontrée.
	 *
	 *   Ce qui la rend acceptable : supprimer l'entrée NE CHANGE PAS l'état du
	 *   ticket — `statut` vit dans sa propre colonne, le fil n'en est que le récit.
	 *   Le coût est une perte de traçabilité, pas une incohérence.
	 *
	 *   ⚠️ Les RÉPONSES restent hors de portée : elles appartiennent à leur auteur,
	 *   souvent un résident. Les effacer supprimerait la parole de quelqu'un
	 *   d'autre — ce n'est pas la même chose que retirer une ligne écrite par le
	 *   système ou par soi-même. Le serveur les refuse (`422`), et l'écran dit la
	 *   même chose que lui, ni plus ni moins (ux-patterns §15). */
	const TYPES_EFFACABLES = ['commentaire', 'etat'];

	/**  🔴 Effacer est réservé à l'ADMINISTRATEUR (18/08/2026, demandé à l'écran :
	 *   « bon pour l'admin seul »).
	 *
	 *   Corriger son propre commentaire est un geste ordinaire, ouvert à son auteur.
	 *   Effacer ne l'est pas : cela fait disparaître une trace que d'autres ont pu
	 *   lire, et sur laquelle ils ont pu agir. Même frontière que la suppression d'un
	 *   ticket, et même règle que « archiver n'est pas supprimer ».
	 *
	 *   La capacité est née d'un besoin réel : deux entrées « Correction : … »
	 *   s'étaient inscrites sur un ticket alors qu'une seule catégorie avait changé,
	 *   et RIEN ne permettait de les retirer — pas même à l'admin. Un fil est une
	 *   mémoire ; une mémoire qui garde des faits inventés vaut moins qu'une mémoire
	 *   trouée. */
	function peutEffacer(evol: Entree): boolean {
		return estAdmin && TYPES_EFFACABLES.includes(evol.type);
	}

	function peutCorriger(evol: Entree): boolean {
		if (!peutModifier || !TYPES_CORRIGEABLES.includes(evol.type)) return false;
		if (estAdmin) return true;
		//  Sans `auteur_id` on ne peut pas trancher : on n'affiche pas un bouton
		//  dont on ignore s'il aboutira. Un contrôle qui ne peut pas mesurer ne
		//  conclut pas au vert (`standards/04` §2).
		return evol.auteur_id !== undefined && evol.auteur_id === currentUserId;
	}

	let deplie = false;

	//  Le plus récent en premier : on vient lire ce qui vient d'arriver.
	$: triees = [...evolutions].sort(
		(a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime(),
	);
	$: replie = triees.length > seuil && !deplie;
	$: visibles = replie ? triees.slice(0, apercu) : triees;
</script>

{#if titre || $$slots.action}
	<div class="hist-entete">
		{#if titre}<h2 class="hist-titre">{titre}</h2>{/if}
		<slot name="action" />
	</div>
{/if}

{#if triees.length === 0}
	{#if vide}<p class="hist-vide">{vide}</p>{/if}
{:else}
	<div class="evol-list">
		{#each visibles as evol, i (evol.id)}
			{#if i > 0}<hr class="evol-sep" />{/if}
			<div class="evol-item evol-{evol.type}">
				<!--  🔴 L'icône vient de `$lib/evolutions`, plus d'une chaîne écrite ici.
				      Elle valait 📝 pour un commentaire alors que le bouton qui le crée
				      dit « 💬 Commenter » — signalé à l'écran le 19/08/2026 : *« pourquoi
				      mon commentaire a une icône de type relance ? »*. La bulle était
				      prise par `reponse`. Le geste et son résultat portent désormais le
				      même signe. -->
				<span class="evol-icon">{evolutionIcone(evol.type)}</span>
				<div class="evol-body">
					<div class="evol-ligne-meta">
						<span class="evol-meta">{fmtDatetime(evol.cree_le)}{#if evol.auteur_nom} · {evol.auteur_nom}{/if}</span>
						<!--  🔴 LES DEUX ICÔNES DANS UN MÊME GROUPE, cadré à droite
						      (18/08/2026, signalé à l'écran). Elles étaient enfants directs
						      d'une ligne en `space-between` : à DEUX enfants — la méta et le
						      crayon — cela donnait bien « méta à gauche, crayon à droite » ;
						      la corbeille en a fait un TROISIÈME, et `space-between` l'a
						      réparti au milieu. Le style n'avait pas changé, c'est son
						      contenu qui avait cessé de lui correspondre.

						      Groupées, elles suivent la norme de l'en-tête de carte : ✏️ puis
						      🗑️, collées, à l'extrémité droite (ux-patterns §3). -->
						{#if enEdition !== evol.id && (peutCorriger(evol) || peutEffacer(evol))}
							<span class="evol-actions">
								{#if peutCorriger(evol)}
									<!--  Le CRAYON SEUL, comme partout ailleurs sur le site : ce
									      bouton portait « ✏️ Modifier » et était le dernier à écrire
									      le mot. Le sens vit dans `title` et `aria-label`. -->
									<button type="button" class="btn-icon evol-modifier" aria-label="Modifier cette entrée"
										title="Modifier" on:click={() => dispatch('modifier', evol.id)}>&#x270F;&#xFE0F;</button>
								{/if}
								{#if peutEffacer(evol)}
									<!--  La corbeille EN DERNIER parce qu'elle est irréversible. -->
									<button type="button" class="btn-icon-danger evol-modifier" aria-label="Supprimer cette entrée"
										title="Supprimer cette entrée" on:click={() => dispatch('supprimer', evol.id)}>&#x1F5D1;&#xFE0F;</button>
								{/if}
							</span>
						{/if}
					</div>

					{#if evol.type === 'etat'}
						<span class="evol-text">
							Statut : <strong>{statutLabels[evol.ancien_statut ?? ''] || 'Aucun'}</strong>
							→ <strong>{statutLabels[evol.nouveau_statut ?? ''] || evol.nouveau_statut}</strong>
						</span>
					{/if}

					<!--  Le périmètre PRÉCISÉ par cette entrée (#497). Il se lit sur la même
					      ligne que le changement d'état, parce que c'est le même genre de
					      fait : ce que cette entrée a changé au dossier.
					      🔹 = périmètre logique, jamais 📍 qui désigne un lieu physique. Et
					      il est TOUJOURS affiché quand l'entrée en déclare un, même s'il
					      vaut « résidence » — la règle « pas de badge sur le périmètre par
					      défaut » vaut pour l'ÉTAT d'un objet, pas pour un CHANGEMENT :
					      élargir un ticket à toute la résidence est un fait qui se dit. -->
					{#if evol.perimetre_cible?.length}
						<span class="evol-text evol-perimetre">
							Périmètre précisé : <strong>&#x1F539; {perimetreLabel(evol.perimetre_cible)}</strong>
						</span>
					{/if}

					{#if enEdition === evol.id}
						<!--  Le formulaire de correction vient de l'écran hôte : la rubrique
						      ne connaît ni l'API ni l'entité qu'elle affiche. -->
						<div class="evol-edition"><slot name="edition" {evol} /></div>
					{:else}
						{#if evol.contenu}
							<div class="evol-content rich-content">{@html safeDescription(evol.contenu)}</div>
						{/if}
						<!--  🔴 GRAND FORMAT, et c'est un REVIREMENT (18/08/2026).
						      `ux-patterns` §11 rangeait les fils d'évolutions du côté
						      « vignette », avec un argument juste : elle signale la photo
						      sans casser le rythme de lecture d'une liste qu'on survole.

						      L'écran l'a réfuté, capture à l'appui : un fil d'Historique
						      ne s'atteint qu'en DÉPLIANT une carte. Quand on l'a sous les
						      yeux, on a déjà demandé à voir — et sur un événement de
						      calendrier, les photos du suivi sont TOUT le contenu (« voici
						      les anomalies relevées »), réduites à trois timbres-poste de
						      72 px là où le même dossier, s'il avait été un ticket, les
						      montrait en grand avec son compteur « 1 / 3 ».

						      La règle de §11 ne change pas, sa lecture si : le critère est
						      « survole-t-on, ou a-t-on demandé à voir ? », et un fil déplié
						      est du second côté. `compact` reste — il ne concerne que la
						      typographie des liens de documents. -->
						{#if evol.fichiers_urls?.length}
							<div class="evol-pj"><PiecesJointes urls={evol.fichiers_urls} format="grand" compact /></div>
						{/if}
					{/if}
				</div>
			</div>
		{/each}

		{#if replie}
			<hr class="evol-sep" />
			<button type="button" class="evol-more" on:click={() => (deplie = true)}>
				Voir les {triees.length - apercu} entrées plus anciennes
			</button>
		{/if}
	</div>
{/if}

<style>
	.hist-entete {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: .5rem;
		margin-bottom: .5rem;
	}
	.hist-titre { font-size: 1rem; font-weight: 600; margin: 0; }
	.hist-vide { font-size: .85rem; color: var(--color-text-muted); }

	/*  ⚠️ Ces classes sont définies ICI, avec le balisage qui les porte. Les
	    laisser dans le `<style>` des pages hôtes ne les atteindrait pas : Svelte
	    scope le style au composant qui l'écrit, et c'est très exactement la panne
	    qui a envoyé des pastilles nues en production (v2.67.11). La marge haute
	    (`margin-top`) revient au parent, qui seul sait ce que le fil suit. */
	.evol-list { border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden; }
	.evol-sep { margin: 0; border: none; border-top: 1px solid var(--color-border); }
	.evol-item { display: flex; gap: .5rem; padding: .5rem .75rem; font-size: .82rem; }
	.evol-icon { flex-shrink: 0; font-size: .9rem; margin-top: .1rem; }
	.evol-body { display: flex; flex-direction: column; gap: .15rem; flex: 1; min-width: 0; }
	.evol-ligne-meta { display: flex; align-items: flex-start; justify-content: space-between; gap: .5rem; }
	/*  Le groupe d'actions : collées entre elles, et poussé à droite par le
	    `space-between` de la ligne — quel que soit le NOMBRE de boutons. */
	.evol-actions { display: flex; gap: .3rem; flex-shrink: 0; }
	.evol-meta { font-size: .75rem; color: var(--color-text-muted); }
	.evol-text { color: var(--color-text); line-height: 1.5; }
	/*  Le périmètre précisé se lit SOUS le changement d'état quand les deux sont
	    là : deux faits, deux lignes, plutôt qu'une phrase qui les enchaîne. */
	.evol-perimetre { display: block; margin-top: .15rem; }
	.evol-content { margin-top: .2rem; color: var(--color-text); line-height: 1.6; font-size: .85rem; }
	.evol-content :global(p) { margin: 0 0 .3em; }
	.evol-pj { margin-top: .4rem; }
	.evol-edition {
		margin: .4rem 0;
		border: 1px solid var(--color-border);
		border-radius: 8px;
		padding: .75rem;
		background: var(--color-bg);
	}
	.evol-modifier {
		border: 1px solid var(--color-border);
		background: var(--color-bg-alt);
		color: var(--color-text);
		cursor: pointer;
		padding: .15rem .4rem;
		font-size: .75rem;
		flex-shrink: 0;
		border-radius: 5px;
		line-height: 1.4;
	}
	/*  Les trois teintes de fond disent le TYPE d'entrée sans lire un badge. */
	.evol-etat { background: #f0f9ff; }
	.evol-reponse { background: #f0fdf4; }
	.evol-commentaire { background: #fafafa; }

	.evol-more {
		width: 100%;
		background: none;
		border: none;
		padding: .45rem;
		font-size: .8rem;
		color: var(--color-primary);
		cursor: pointer;
		text-align: center;
	}
	.evol-more:hover { background: var(--color-bg); }
</style>
