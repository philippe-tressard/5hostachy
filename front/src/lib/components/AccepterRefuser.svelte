<!--
  Le geste « accepter · refuser avec motif » d'une ligne à traiter (#817).

  ## Pourquoi ce composant

  Il était écrit **trois fois** dans `admin/+page.svelte` — comptes en attente,
  commandes d'accès, demandes de modification de profil. Trois listes, un seul
  geste : un bouton qui accepte, un bouton qui ouvre un champ de motif, et le
  couple « Annuler · Confirmer » qui s'y accroche.

  🔴 Et la troisième avait DÉRIVÉ, comme dérive toujours la copie qu'on ne
  compare à rien :

  | | comptes | accès | demandes de profil |
  |---|---|---|---|
  | annuler | « Annuler » | « Annuler » | **« ✕ »** |
  | champ | `.input-sm` | `.input-sm` | **six propriétés en dur** |
  | accepter | charte | charte | **`background:#16a34a`** — hors charte |
  | rangée | `.refus-inline` | `.refus-inline` | **`style="display:flex…"`** |

  Rien de tout cela n'avait de raison : ce sont trois écritures d'une même
  chose, et la dernière était simplement la plus récente.

  ## Ce qui reste en props, et pourquoi

  Les **libellés** : « Valider → », « Accepter », « ✓ Approuver » ne disent pas
  la même chose — on valide un compte, on accepte une commande, on approuve une
  demande. Le libellé nomme l'OBJET, il ne décrit pas le geste ; l'uniformiser
  aurait appauvri l'écran au lieu de le rendre cohérent.

  Ce qui n'a **aucune** raison de varier ne varie plus : l'annulation, la
  charte, la disposition, et l'ordre des deux boutons.

  ## L'état est INTERNE, et c'est le vrai gain

  La page portait six variables pour cela — `refusOpen`/`refusMotif`,
  `cmdRefusOpen`/`cmdMotif`, `refusDemandeOpen`/`refusDemande` — trois paires de
  `Record<number, …>` indexées par identifiant, uniquement parce que le balisage
  était rendu dans une boucle. Une instance par ligne rend ces tables inutiles :
  chaque composant tient son propre état, et il n'y a plus d'identifiant à
  synchroniser.
-->
<script lang="ts">
	/** Le bouton d'acceptation — « Accepter », « Valider → », « ✓ Approuver »… */
	export let libelleAccepter = 'Accepter';
	/** Le bouton qui ouvre le motif — « Refuser », « ✗ Rejeter »… */
	export let libelleRefuser = 'Refuser';
	export let placeholderMotif = 'Motif du refus';
	export let onAccepter: () => void;
	/** Reçoit le motif saisi, vide si l'administrateur n'en a pas donné. */
	export let onRefuser: (motif: string) => void;

	let ouvert = false;
	let motif = '';

	function annuler() {
		ouvert = false;
		motif = '';
	}
</script>

<button class="btn btn-primary btn-sm" on:click={onAccepter}>{libelleAccepter}</button>
{#if !ouvert}
	<button class="btn btn-danger btn-sm" on:click={() => (ouvert = true)}>{libelleRefuser}</button>
{:else}
	<div class="refus-inline">
		<input type="text" class="input-sm" placeholder={placeholderMotif} bind:value={motif} />
		<button class="btn btn-outline btn-sm" on:click={annuler}>Annuler</button>
		<button class="btn btn-danger btn-sm" on:click={() => onRefuser(motif)}>Confirmer</button>
	</div>
{/if}

<style>
	/*  🔴 Cette règle VOYAGE avec le balisage qu'elle habille : laissée dans la
	    page, elle y serait devenue orpheline (#796).

	    `.input-sm` sert encore trois fois dans `/admin` : il est MONTÉ dans la
	    charte plutôt que recopié ici — deux écritures d'une même règle divergent
	    au premier ajustement, et c'est le remède que `.header-summary` a déjà
	    appliqué au même problème.

	    ⚠️ `.btn-sm` : le composant prend celui de la CHARTE, alors que `/admin`
	    en redéfinit une version plus dense (déclarée dans
	    `check-charte-recomposee.regles.mjs`). Deux pixels d'écart avec les
	    boutons voisins de l'onglet « Utilisateurs », et c'est le bon sens de
	    l'écart : la dette est la redéfinition, pas la charte. */
	.refus-inline {
		display: flex;
		gap: 0.4rem;
		align-items: center;
		flex-wrap: wrap;
	}
</style>
