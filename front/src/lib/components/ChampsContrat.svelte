<!--
  ChampsContrat.svelte — les champs d'un contrat d'entretien, écrits UNE fois.

  ## Pourquoi (30/08/2026, #453 · #491)

  `prestataires/+page.svelte` rendait ce formulaire **deux fois** : dans la
  modale « Nouveau / Modifier contrat », et dans l'édition en ligne au sein de la
  carte du contrat. Quatre-vingt-dix lignes chacune, à l'indentation près.

  Le garde-fou de modularité a refusé un ajout de quatorze lignes à ce fichier.
  Il ne disait pas « il est trop long », il disait **« le code est au mauvais
  endroit »** (#453, la troisième des trois réponses possibles).

  ## 🔴 Les quatre divergences que la copie avait fabriquées

  Comparées ligne à ligne, indentation retirée — aucune n'est une décision :

  | | Modale | Édition en ligne |
  |---|---|---|
  | **Équipement** | présent | **ABSENT** — on ne pouvait pas le changer là |
  | Libellé | `champ-large` | `field` nu, donc écrasé dans un tiers de grille |
  | Notes, pour un lecteur d'écran | `ariaLabelledby` | **rien** — groupe sans nom |
  | Aide des notes | « Notes sur le contrat… » | « Notes… » |

  La première est un **champ manquant** : le type d'équipement appartient au
  contrat, il se saisit dans les deux rendus ou dans aucun. Le cadre #430 pose la
  question ainsi — *devant un écart entre deux états, lequel des deux a tort ?* —
  et ici c'est l'édition en ligne.

  Ce n'est pas de l'inattention : **c'est la duplication du rendu qui le
  produit**, mécaniquement, comme le crayon et la corbeille du fil de tickets
  (#431) qui avaient divergé deux fois dans les deux sens.

  ## Ce qui reste dans l'écran

  Le bloc **Documents** : sa source d'identifiant diffère (`editContratId` dans
  la modale, `c.id` dans la carte) et son enveloppe aussi (`.contrat-section`).
  Le passer ici demanderait de faire voyager la table des documents et son
  téléversement — un autre lot, et il est nommé dans #390.
-->
<script context="module" lang="ts">
	let compteur = 0;
</script>

<script lang="ts">
	import PerimetrePicker from './PerimetrePicker.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import { CONTRAT } from '$lib/entites/contrat';
	import { sectionPresente, type Etat } from '$lib/entites/types';

	/** Le formulaire lié — l'écran porte l'état et l'enregistre. */
	export let contratForm: any;
	/** Les prestataires proposables. */
	export let prestataires: any[] = [];
	/** La table des équipements (`{ val, label }`). */
	export let equipements: readonly { val: string; label: string }[] = [];
	/**  Création ou correction — c'est la DÉCLARATION qui en tire les sections
	 *   présentes, jamais une condition écrite ici (`lint:etats`). */
	export let etat: Etat = 'creation';

	//  Un identifiant par instance : les deux rendus coexistent dans la même page,
	//  et deux `id` identiques feraient pointer les deux `aria-labelledby` sur le
	//  premier — un défaut qui ne se voit qu'au lecteur d'écran.
	const idNotes = `contrat-notes-${++compteur}`;
	const idPerimetre = `contrat-perimetre-${compteur}`;
</script>

<!--  ══ 1. TITRE ══ Le titre SEUL (§0, arbitré le 18/08/2026 : ce qui qualifie
      l'objet est en section 2). Le champ s'appelait « Libellé » — signalé à
      l'écran le 12/09 : c'est « Titre » sur les huit autres entités, et un même
      objet porte le même libellé partout (R3). -->
<SectionFormulaire titre="Titre" requis pour="{idNotes}-titre">
	<label class="field champ-large" for="{idNotes}-titre">
		<input id="{idNotes}-titre" bind:value={contratForm.libelle} required />
	</label>
</SectionFormulaire>

<!--  ══ 2. CHAMPS SPÉCIFIQUES ══ Tout ce qui QUALIFIE le contrat : avec qui, sur
      quoi, depuis quand, à quel rythme. Les dates et la fréquence étaient rendues
      APRÈS le périmètre — elles passent avant, l'ordre des neuf sections ne se
      discute pas (R2). -->
<SectionFormulaire titre="Le contrat">
	<div class="form-grid">
		<label class="field"
			>Prestataire *
			<select bind:value={contratForm.prestataire_id} required>
				<option value="">— Sélectionner —</option>
				{#each prestataires as pr (pr.id)}<option value={String(pr.id)}>{pr.nom}</option>{/each}
			</select>
		</label>
		<!--  🔴 Ce champ MANQUAIT à l'édition en ligne avant le 30/08/2026 : le type
		      d'équipement d'un contrat ne s'y modifiait pas, et rien ne le disait. -->
		<label class="field"
			>Équipement
			<select bind:value={contratForm.type_equipement}>
				{#each equipements as e (e.val)}<option value={e.val}>{e.label}</option>{/each}
			</select>
		</label>
		<label class="field">N° contrat<input bind:value={contratForm.numero_contrat} /></label>
		<label class="field"
			>Début *<input type="date" bind:value={contratForm.date_debut} required /></label
		>
		<label class="field"
			>Durée initiale
			<div class="duo">
				<input
					type="number"
					min="1"
					placeholder="Ex. 12"
					bind:value={contratForm.duree_initiale_valeur}
				/>
				<select bind:value={contratForm.duree_initiale_unite}>
					<option value="mois">mois</option>
					<option value="ans">ans</option>
				</select>
			</div>
		</label>
		<label class="field"
			>Fréquence
			<select bind:value={contratForm.frequence_type}>
				<option value="">— Aucune —</option>
				<option value="semaines">Toutes les X semaines</option>
				<option value="mois">Mensuelle</option>
				<option value="fois_par_an">X fois par an</option>
				<option value="ans">Tous les X ans</option>
			</select>
		</label>
		{#if contratForm.frequence_type === 'semaines'}
			<label class="field"
				>Toutes les … sem.<input
					type="number"
					min="1"
					bind:value={contratForm.frequence_valeur}
				/></label
			>
		{:else if contratForm.frequence_type === 'fois_par_an'}
			<label class="field"
				>… fois/an<input type="number" min="1" bind:value={contratForm.frequence_valeur} /></label
			>
		{:else if contratForm.frequence_type === 'ans'}
			<label class="field"
				>Tous les … ans<input
					type="number"
					min="1"
					bind:value={contratForm.frequence_valeur}
				/></label
			>
		{/if}
		<label class="field"
			>Prochaine visite<input type="date" bind:value={contratForm.prochaine_visite} /></label
		>
	</div>
</SectionFormulaire>

<!--  ══ 4. PÉRIMÈTRE ══ « Périmètre », pas « Périmètre couvert » : c'est le même
      objet que partout ailleurs, il porte le même nom (R3, signalé le 12/09).
      La section n'a qu'un champ : son titre EST le libellé, et le champ n'écrit
      plus rien (`titre=""`) — sinon le nom paraît deux fois.

      🔴 Le périmètre n'existait PAS avant le 10/09/2026 : `batiment_id` figurait
      dans la charge utile sans que rien ne le remplisse, donc tous les contrats
      portaient `NULL` et le carnet d'entretien ne pouvait filtrer sur rien. -->
{#if sectionPresente(CONTRAT, etat, 'perimetre')}
	<SectionFormulaire titre="Périmètre" pour={idPerimetre}>
		<div role="group" aria-labelledby={idPerimetre}>
			<PerimetrePicker bind:value={contratForm.perimetre_cible} titre="" />
		</div>
		<p class="aide">
			Ce que ce contrat entretient. Il apparaîtra dans le carnet d’entretien de ce périmètre — et
			dans celui de chacun des espaces qu’il contient.
		</p>
	</SectionFormulaire>
{/if}

<!--  ══ 6. DESCRIPTION ══ C'est ici qu'atterrit la synthèse proposée par
      l'assistant IA (#899), relue et corrigée avant enregistrement. -->
{#if sectionPresente(CONTRAT, etat, 'description')}
	<SectionFormulaire titre="Description" pour={idNotes}>
		<RichEditor
			bind:value={contratForm.notes}
			ariaLabelledby={idNotes}
			placeholder="Ce que couvre le contrat, ses points d’attention…"
			minHeight="60px"
		/>
	</SectionFormulaire>
{/if}

<style>
	/*  Les deux contrôles d'une durée — un nombre et son unité — sur une ligne.
	    Ils étaient posés par un `style=` en ligne, donc invisibles à
	    `lint:styles` et impossibles à ajuster ailleurs. */
	.duo {
		display: flex;
		gap: 0.4rem;
	}
	.duo input {
		flex: 1;
	}
	.duo select {
		width: auto;
	}
</style>
