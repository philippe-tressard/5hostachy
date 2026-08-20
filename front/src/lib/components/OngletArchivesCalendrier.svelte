<!--
  **L'onglet « Archives » du calendrier** — actualités archivées, prestations
  réalisées et événements passés, groupés par ANNÉE puis par MOIS.

  ## Pourquoi ce composant (#516)

  Extrait de `calendrier/+page.svelte` quand le garde-fou de modularité a refusé
  qu'elle grossisse d'une ligne d'import (#453). Le refus disait vrai : cet
  onglet est autonome, et son rendu est le seul du site à porter deux niveaux.

  ## 🔴 Il n'emploie PAS `ArchivesParAnnee`, et c'est déclaré

  Cinq écrans l'ont adopté le 20/08 (Actualités, Tickets, Espace CS, Petites
  annonces, Accès & sécurité). Celui-ci non, pour une raison de fond : il groupe
  par année **puis par mois**, parce qu'il mélange trois types d'objets sur une
  échelle de temps longue — un groupement par année seule y donnerait des
  paquets de plusieurs dizaines de lignes sans repère.

  ⚠️ Ce qui EST commun, et ce qui doit le rester : le **mot**. Le libellé de
  l'onglet vient de `TITRE_ARCHIVES` (`$lib/archives`), comme partout ailleurs.
  Le ticket demandait d'unifier le vocabulaire ; le rendu, lui, a le droit de
  suivre la nature de ce qu'il montre — à condition de le dire, ce que fait ce
  commentaire.

  ## Les styles voyagent avec le balisage

  `.archive-year-section`, `.archive-year-header`, `.month-group`… décrivent ce
  que ce fichier rend. Svelte scope les styles au composant qui rend l'élément :
  les laisser dans la page aurait livré l'onglet nu (v2.67.11).
-->
<script lang="ts">
	import RangeeCalendrier from '$lib/components/RangeeCalendrier.svelte';
	import { isAdmin } from '$lib/stores/auth';
	import { fmtDateShort, fmtDateLong } from '$lib/date';
	import { fmtMontant } from '$lib/utils';

	/** Tous les objets archivés, tous types confondus. */
	export let allArchiveItems: any[] = [];
	/** Le groupement année ▸ mois, calculé par la page qui connaît ses trois types. */
	export let archiveByYear: [number, [string, any[]][]][] = [];
	/** Les années dépliées — liées, la page les initialise depuis les données. */
	export let expandedArchiveYears: Set<number> = new Set();

	//  Les gestes restent chez la page : ils appellent l'API et rechargent les
	//  listes. Les dupliquer ici donnerait deux vérités sur l'état d'un objet.
	export let prestataireNom: (id: number) => string;
	export let typeLabel: (type: string) => string;
	export let formatDate: (d: string) => string;
	export let deleteArchivedPub: (item: any) => void;
	export let deleteEv: (id: number) => void;
</script>

{#if allArchiveItems.length === 0}
	<div class="empty-state">
		<h3>Aucune archive</h3>
		<p>Les éléments archivés apparaîtront ici.</p>
	</div>
{:else}
	{#each archiveByYear as [year, monthGroups]}
		<div class="archive-year-section">
			<button class="archive-year-header" on:click={() => { if (expandedArchiveYears.has(year)) expandedArchiveYears.delete(year); else expandedArchiveYears.add(year); expandedArchiveYears = expandedArchiveYears; }}>
				<span class="archive-year-label">&#x1F4C5; {year}</span>
				<span class="archive-year-count">{monthGroups.reduce((s, [, items]) => s + items.length, 0)} élément{monthGroups.reduce((s, [, items]) => s + items.length, 0) > 1 ? 's' : ''}</span>
				<span class="chevron" class:open={expandedArchiveYears.has(year)}>›</span>
			</button>
			{#if expandedArchiveYears.has(year)}
				{#each monthGroups as [mois, items]}
					<div class="month-group" style="padding-left:.75rem">
						<div class="month-label">{mois}</div>
						{#each items as item}
							{#if item._kind === 'pub'}
								<!--  Publication archivée. Les trois rangées d'archives et celle des
								      maintenances passent par `RangeeCalendrier` : la structure
								      *type · corps · date · actions* était recopiée quatre fois, et
								      c'est ce partage qui interdisait de découper la page (#432). -->
								<RangeeCalendrier archive bordure="#0ea5e9"
									typeTexte="&#x1F4F0;" badgeType={{ texte: 'Actualité', couleur: '#0ea5e9' }}
									titre={item.titre} description={item.contenu}
									dates={[{ texte: fmtDateShort(item._date) },
										...(item.auteur_nom ? [{ texte: item.auteur_nom, attenue: true }] : [])]}
									perimetre={item.perimetre_cible}
									avecActions={$isAdmin}>
									<svelte:fragment slot="actions">
										<button class="btn-icon-danger" aria-label="Supprimer définitivement" title="Supprimer définitivement" on:click={() => deleteArchivedPub(item)}>&#x1F5D1;️</button>
									</svelte:fragment>
								</RangeeCalendrier>
							{:else if item._kind === 'devis'}
								<!-- Prestation réalisée -->
								<RangeeCalendrier archive bordure="#7c3aed"
									typeTexte="&#x1F3C1;" badgeType={{ texte: 'Prestation', couleur: '#7c3aed' }}
									titre={item.titre} description={item.notes}
									metas={prestataireNom(item.prestataire_id) ? [`\u{1F3AF} ${prestataireNom(item.prestataire_id)}`] : []}
									dates={[...(item.date_prestation ? [{ texte: fmtDateShort(item.date_prestation) }] : []),
										...(item.montant_estime ? [{ texte: fmtMontant(item.montant_estime), attenue: true }] : [])]} />
							{:else}
								<!-- Événement archivé -->
								<RangeeCalendrier archive bordure="#10b981" urgent={item.type === 'coupure'}
									typeTexte={typeLabel(item.type)} badgeType={{ texte: 'Événement', couleur: '#10b981' }}
									titre={item.titre} description={item.description}
									metas={item.lieu ? [`\u{1F4CD} ${item.lieu}`] : []}
									dates={[{ texte: formatDate(item.debut) },
										...(item.fin ? [{ texte: `→ ${formatDate(item.fin)}`, attenue: true }] : [])]}
									perimetre={item.perimetre}
									pied={(item.mis_a_jour_le ? `Mise à jour le ${fmtDateLong(item.mis_a_jour_le)}` : `Publié le ${fmtDateLong(item.cree_le)}`)
										+ (item.auteur_nom ? ` · ${item.auteur_nom}` : '')}
									avecActions={$isAdmin}>
									<svelte:fragment slot="actions">
										<button class="btn-icon-danger" aria-label="Supprimer définitivement" title="Supprimer définitivement" on:click={() => deleteEv(item.id)}>&#x1F5D1;️</button>
									</svelte:fragment>
								</RangeeCalendrier>
							{/if}
						{/each}
					</div>
				{/each}
			{/if}
		</div>
	{/each}
{/if}

<style>
	/*  🔴 Ces règles VOYAGENT avec le balisage qu'elles habillent. Svelte scope
	    les styles au composant qui les rend : les laisser dans la page aurait
	    livré l'onglet NU en production — c'est la panne des pastilles de la
	    v2.67.11, et `lint:classes-nues` l'a attrapée ici avant le commit.

	    `.month-group` et `.month-label` sont RECOPIÉES depuis la page, qui les
	    emploie encore pour la vue « liste ». Ce n'est pas un oubli : deux
	    portées Svelte distinctes ne peuvent pas partager une règle scopée, et
	    les remonter dans `app.css` en ferait des règles globales pour deux
	    usages qui n'ont pas de raison de rester identiques.

	    `.chevron` vient d'`app.css` — elle est déjà globale, et c'est ce qui
	    rend ce découpage sûr. */
	.archive-year-section { margin-bottom: .5rem; border: 1px solid var(--color-border); border-radius: var(--radius); overflow: hidden; }
	.archive-year-header { width: 100%; display: flex; align-items: center; gap: .75rem; padding: .65rem 1rem; background: var(--color-surface); border: none; cursor: pointer; font-size: .95rem; font-weight: 600; text-align: left; }
	.archive-year-header:hover { background: var(--color-bg); }
	.archive-year-label { flex: 1; }
	.archive-year-count { font-size: .8rem; font-weight: 400; color: var(--color-text-muted); }
	.month-group { margin-bottom: 1.5rem; }
	.month-label { font-size: .8rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--color-text-muted); margin-bottom: .5rem; }
</style>
