<!--
  CanauxNotification.svelte — « Qui est prévenu ? », écriture unique.

  Les trois canaux (groupe WhatsApp, syndic, conseil syndical) étaient écrits à
  la main dans SIX formulaires : actualités, évolutions (EvolForm), calendrier,
  sondages, devis, et création de ticket. Ils avaient divergé exactement comme le
  prévoit `standards/02-factorisation.md` §2 — deux tracés SVG WhatsApp, trois
  libellés (« Partager sur le groupe », « …sur le groupe WhatsApp », « Notifier
  WhatsApp »), deux icônes d'e-mail (✉️ et 📧), trois libellés de CS — et surtout
  un écran où le canal WhatsApp manquait purement et simplement : la création
  d'un ticket. C'est ce trou-là que l'utilisateur a signalé le 08/08/2026.

  La référence retenue est celle des actualités, qui est la plus complète et la
  seule à porter le libellé métier (« le groupe » = le groupe de la copropriété).

  Props :
    whatsapp / syndic / cs – à lier avec `bind:` ; les trois cases
    compact                – formulaire dense en ligne (évolution, devis) :
                             police réduite
    aideWhatsapp           – infobulle propre au contexte (ex. « la photo part avec »)

  MISE EN FORME : une rangée simple, icône + libellé, comme les actualités. Les
  précisions (« le syndic principal recevra un e-mail ») sont en **infobulle** et
  non en texte visible : essayées sous chaque case, elles élargissaient tellement
  les trois blocs qu'ils s'enroulaient sur deux lignes ragged — vérifié au rendu
  le 08/08/2026. Seule la création de ticket les affichait avant, c'est-à-dire un
  écran sur six : les garder visibles partout, c'était garder la divergence dans
  l'autre sens.

  Aucune de ces cases n'est un choix par défaut : elles partent toujours
  décochées côté appelant. Envoyer une notification est une action délibérée.
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';

	/** Partager sur le groupe WhatsApp de la copropriété */
	export let whatsapp = false;
	/** Envoyer un e-mail au syndic principal */
	export let syndic = false;
	/** Envoyer un e-mail aux membres du conseil syndical */
	export let cs = false;
	/** Formulaire dense en ligne : police réduite */
	export let compact = false;
	/** Infobulle propre au contexte, sinon la formulation générique */
	export let aideWhatsapp = '';
	/**  🔴 M'ENVOYER UNE COPIE — la quatrième case, arbitrée le 31/08/2026.
	 *
	 *   > « pour l'auteur dans la diffusion, que cette section fasse apparaître
	 *   > une coche supplémentaire EN CLAIR et pas un envoi implicite à l'auteur »
	 *
	 *   Un envoi implicite avait été livré quelques heures plus tôt : l'auteur
	 *   recevait une copie cachée dès qu'il n'était pas déjà destinataire. C'était
	 *   commode, et c’était une décision prise à sa place — le formulaire annonçait
	 *   trois destinataires et en servait quatre.
	 *
	 *   ⚠️ Elle vit ICI et non dans un écran : cette section sert huit formulaires,
	 *   et une case posée dans l'un des huit n'aurait été offerte que là. C'est la
	 *   règle rappelée le même jour — *« les comportements demandés doivent être au
	 *   niveau des objets pour être dans toutes les pages y faisant référence »*.
	 *
	 *   ⚠️ **Décochée par défaut.** Une case cochée d'avance n'est pas un choix :
	 *   ce serait l'envoi implicite sous un autre nom. */
	export let auteur = false;
</script>

<div class="canaux" class:compact>
	<label
		class="checkbox-field"
		title={aideWhatsapp || 'Le message est publié sur le groupe WhatsApp de la copropriété.'}
	>
		<input type="checkbox" bind:checked={whatsapp} />
		<Icon name="whatsapp" size={compact ? 16 : 18} />
		<span>Partager sur le groupe</span>
	</label>

	<label class="checkbox-field" title="Le syndic principal recevra un e-mail.">
		<input type="checkbox" bind:checked={syndic} />
		<span class="ico" aria-hidden="true">&#x2709;&#xFE0F;</span>
		<span>Envoyer au syndic</span>
	</label>

	<label class="checkbox-field" title="Les membres du conseil syndical recevront un e-mail.">
		<input type="checkbox" bind:checked={cs} />
		<span class="ico" aria-hidden="true">&#x2709;&#xFE0F;</span>
		<span>Envoyer au Conseil Syndical</span>
	</label>

	<!--  EN DERNIER : les trois premières disent qui d'AUTRE est prévenu, celle-ci
	      parle de soi. L'ordre suit le sens, pas l'ordre d'ajout. -->
	<label class="checkbox-field" title="Vous recevrez une copie de ce message.">
		<input type="checkbox" bind:checked={auteur} />
		<span class="ico" aria-hidden="true">&#x2709;&#xFE0F;</span>
		<span>M'envoyer une copie</span>
	</label>
</div>

<style>
	.canaux {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		margin-bottom: 1rem;
	}
	.canaux.compact {
		gap: 0.75rem;
		margin-bottom: 0.6rem;
		font-size: 0.82rem;
	}
	/*  `:global` parce que `.checkbox-field` est une classe partagée du thème :
	    la styler localement seule laisserait Svelte la considérer inutilisée. */
	.canaux :global(.checkbox-field) {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		cursor: pointer;
		margin: 0;
		white-space: nowrap;
	}
	.canaux input[type='checkbox'] {
		width: auto;
		margin: 0;
		flex-shrink: 0;
	}
	.ico {
		font-size: 1.1em;
		line-height: 1;
	}
	/*  Sous 480 px, trois cases côte à côte deviennent illisibles : elles
	    passent en colonne pleine largeur. Et surtout la case gagne une hauteur
	    de 44 px : en rangée, la cible tactile ne faisait que 16 à 18 px de haut
	    — mesuré au rendu le 08/08/2026 (socle 11 §10). */
	@media (max-width: 480px) {
		.canaux {
			flex-direction: column;
			gap: 0.25rem;
		}
		.canaux :global(.checkbox-field) {
			min-height: 44px;
			white-space: normal;
		}
	}
</style>
