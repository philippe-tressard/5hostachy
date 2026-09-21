<!--
  Le formulaire d'un événement de calendrier.

  Extrait de `calendrier/+page.svelte` le 15/08/2026 : le fichier dépassait le
  plafond de modularité et le garde-fou a refusé qu'il grossisse en recevant le
  chevron et le survol de #362. La règle est « on découpe le fichier QUAND on y
  touche » — c'est ce qui est fait ici, et la frontière est nette : ce bloc n'est
  QUE de la saisie, la décision (`save`, `resetForm`) reste dans la page.

  Les champs passent par `.field`, dont `app.css` porte le style. Ils étaient
  écrits à la main dans une grille maison, et un sélecteur cassé depuis la v1.0
  les laissait SANS aucun style — apparence native du navigateur, blancs à
  bordure noire, là où tout le site est gris et arrondi (#372). Le défaut était
  masqué par la modale ; le passage à la boîte dans la page l'a révélé.
-->
<script lang="ts">
	import { contexteAssistant, perimetreContexte } from '$lib/assistant';
	import { typeEvenementLabel } from '$lib/evenements';
	import CadreFormulaire from '$lib/components/CadreFormulaire.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import WorkflowPastilles from '$lib/components/WorkflowPastilles.svelte';
	import { sectionPresente, type Etat } from '$lib/entites/types';
	import { EVENEMENT } from '$lib/entites/evenement';
	import { createEventDispatcher, onMount } from 'svelte';

	import { admin as adminApi, calendrier as calApi } from '$lib/api';
	import {
		chargerResidents,
		lotDepuisSaisie,
		nomCopie,
		saisieDepuis,
		type ResidentProposable,
	} from '$lib/saisi-pour';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';

	const dispatch = createEventDispatcher<{ annule: void }>();

	/** L'objet de saisie, lié en deux sens : la page porte son cycle de vie. */
	export let form: any;

	/**  🔴 CE QUI RAMÈNE LE FORMULAIRE À L'ÉCRAN — signalé le 13/09/2026 :
	 *
	 *   > « quand je clique sur le crayon du kanban, j'avais l'impression que
	 *   >   rien ne se passe : l'écran d'édition apparaît hors écran. »
	 *
	 *   Le calendrier rend son formulaire **après** le kanban, tout en bas de la
	 *   page. Éditer depuis une carte de la dernière colonne ouvrait donc un
	 *   formulaire à plusieurs écrans de distance, sans rien bouger : le geste
	 *   paraissait sans effet.
	 *
	 *   ⚠️ Le mécanisme existait déjà — `FormulaireCreation.cle`, relayé par
	 *   `CadreFormulaire` —, et ce formulaire-ci était le seul de la chaîne à ne
	 *   pas le transmettre. Une prop non relayée ne se voit pas : elle prend la
	 *   valeur par défaut, et le comportement manque en silence.
	 *
	 *   ⚠️ `FormulaireCreation` ne défile QUE si le cadre est hors de la bande
	 *   visible : un formulaire ouvert sous les yeux ne fait pas sauter la page. */
	export let cle: unknown = undefined;
	export let photosUrls: string[] = [];
	export let fichiersUrls: string[] = [];
	export let types: { val: string; label: string }[] = [];
	export let prestataires: any[] = [];
	export let submitting = false;
	/** Périmètre ciblé, lié en deux sens comme `form`. */
	export let formPerimetreCible: string[] = [];
	/**  Épinglage à l'OUVERTURE : sans lui, l'avertissement de plafond compterait
	 *   une seconde fois un événement déjà épinglé. */
	export let epingleInitial = false;
	/**  Colonnes du kanban. Passées en prop et NON importées : elles sont une
	 *   constante locale de la page, pas un module partagé — les dupliquer ici
	 *   créerait la deuxième liste qui dérive. */
	export let kanbanCols: { id: string; label: string }[] = [];
	/** Appelé à la soumission. La page garde la décision d'enregistrer. */
	export let onSubmit: () => void;
	/**  Corrige-t-on un événement existant, ou en crée-t-on un ? La page le sait
	 *   (`editId`), le formulaire non — il reçoit le même `form` dans les deux cas.
	 *   C'est le seul discriminant du cadre ici : création et édition ne divergent
	 *   sur AUCUNE section (recouvrement de 100 %, mesuré par #432). La prop existe
	 *   pour que ce fait soit **déclaré et vérifié**, et non simplement vrai. */
	export let modeEdition = false;

	//  ── 2. Saisi pour (15/09/2026) ──────────────────────────────────────────
	//
	//  ⚠️ Les trois VALEURS vivent dans `form` : la page compose sa charge utile
	//  par `{ ...form }`, donc tout ce qui y est part, et tout ce qui n'y est pas
	//  ne part pas. Seul le MODE est local — il ne se transmet pas, il se déduit
	//  (`modeDepuis`), et le serveur n'en a que faire.
	let saisiPour = saisieDepuis(form);
	let residentsSaisiPour: ResidentProposable[] = [];

	//  ⚠️ Recalculé quand le formulaire CHANGE d'événement (`cle`), et **pas** à
	//  chaque frappe : `$: saisiPour = saisieDepuis(form)` écraserait le choix que
	//  l'utilisateur vient de faire. C'est le changement d'objet qui déclenche.
	let cleVue: unknown = cle;
	$: if (cle !== cleVue) {
		cleVue = cle;
		saisiPour = saisieDepuis(form);
	}

	//  🔴 L'état rejoint `form`, que la page envoie par `{ ...form }` : sans ce
	//  report, la saisie resterait locale et ne partirait JAMAIS — en silence.
	//  `Object.assign` MUTE l'objet lié plutôt que de le réassigner : réassigner
	//  relancerait ce bloc à l'infini.
	$: Object.assign(form, lotDepuisSaisie(saisiPour));

	onMount(async () => {
		residentsSaisiPour = await chargerResidents(adminApi.utilisateurs);
	});

	/**  🔴 La présence d'une section ne se décide plus ici : elle se lit dans la
	 *   déclaration `EVENEMENT`, via `sectionPresente(EVENEMENT, etat, …)`. Les six
	 *   sections de `ChampsCommuns` étaient posées **en dur** — ce que `lint:etats`
	 *   refuse, mais sans jamais le voir : le contrôle ignore les fichiers qui
	 *   n'importent aucune entité. L'écran n'était pas conforme, il était hors de
	 *   portée du contrôle (#432). */
	$: etat = (modeEdition ? 'edition' : 'creation') as Etat;

	/**  LE CADRE du formulaire — il dépend du geste (`ux-patterns` §14 bis, arbitré
	 *   à l'écran le 30/08/2026) : *« en édition, le format modal est plus net que
	 *   le dépliement sur une même fenêtre »*.
	 *
	 *   🔴 **Pourquoi le cadre est posé ICI et non dans la page.**
	 *   `FormulaireContrat` écrit l'inverse — *« mettre le cadre ici obligerait le
	 *   composant à connaître le geste »* — et c'est juste POUR LUI : il ne reçoit
	 *   pas le geste. Ce composant-ci, si : `modeEdition` est une de ses propriétés
	 *   depuis #432, et elle est lue trois lignes plus haut pour choisir l'état. La
	 *   prémisse ne tient donc pas, et la règle qu'on en tire est plus générale que
	 *   les deux : **le cadre se pose là où le geste est connu.**
	 *
	 *   ⚠️ Ce qu'il en aurait coûté dans la page : deux branches montant le même
	 *   formulaire avec les mêmes seize propriétés, dont quatre liaisons
	 *   bidirectionnelles que Svelte 4 ne sait pas répandre — deux copies qui
	 *   divergent au premier champ ajouté. C'est la duplication que l'extraction de
	 *   ce composant, le 15/08/2026, avait justement supprimée.
	 *
	 *   🔒 `lint:formulaires` lit `lib/components/` depuis ce lot (#640, point 1).
	 *   Sans cela, poser le cadre ici sortait la modale du champ du contrôle :
	 *   convertir un écran serait revenu à se désarmer. */
	$: titreCadre = modeEdition ? 'Modifier l’événement' : 'Nouvel événement';

	//  L'aperçu de ce qui partira, avant de confirmer (#498) — signalé comme
	//  fonctionnalité CRITIQUE le 31/08/2026, après qu'un envoi soit parti sans
	//  que personne ait pu le voir. Le serveur compose par les mêmes fonctions
	//  que l'envoi ; cet appel ne fait que lui donner le brouillon.
	//  🔴 LA RÉFÉRENCE À LA SECTION, et le drapeau qui dit s'il y a matière à
	//  diffuser. Sans eux, `demanderApercu` ne sert À RIEN : la fonction est
	//  fournie, la modale sait s'ouvrir — et personne ne l'ouvre. C'est l'erreur
	//  du 31/08/2026, constatée par l'utilisateur en RECEVANT le mail.
	let refDiffusion: any = null;
	//  « Envoyer une copie à … » — la case vit dans `CanauxNotification`, qui
	//  porte la règle et son pourquoi. Elle s'affichait ici sans être lue (31/08).
	let envoyerAuteur = false;
	//  Ce que l'assistant IA reçoit pour COMPRENDRE le texte — à ne pas réécrire
	//  (#985) : type, date, lieu, périmètre. `form.assiste_ia` part avec la
	//  charge utile de la page, qui étale `form`.
	$: assistant = contexteAssistant('événement', {
		Type: typeEvenementLabel(form.type),
		Date: form.debut,
		Lieu: form.lieu,
		Périmètre: perimetreContexte(formPerimetreCible),
	});

	$: aUneDiffusion = form.envoyer_syndic || form.envoyer_cs || form.partager_whatsapp;

	/**  Le geste de soumission : aperçu d'abord si un canal est coché.
	 *
	 *   Il s'intercale ICI et non dans `onSubmit`, qui appartient à la page et
	 *   reste le seul chemin d'enregistrement — appelé par le formulaire comme par
	 *   la confirmation de la modale.
	 */
	function soumettre() {
		if (refDiffusion?.ouvrirSiDiffusion(aUneDiffusion)) return;
		onSubmit();
	}

	/** Enregistrer depuis la modale d'aperçu : on la ferme, puis on enregistre. */
	function confirmerEnvoi() {
		refDiffusion?.fermerApercu();
		onSubmit();
	}

	const brouillonApercu = () =>
		calApi.apercuDiffusion({
			titre: form.titre,
			description: form.description,
			type: form.type,
			debut: form.debut || undefined,
			perimetre: formPerimetreCible.join(','),
			photos_urls: photosUrls,
			fichiers_urls: fichiersUrls,
			envoyer_syndic: form.envoyer_syndic,
			envoyer_cs: form.envoyer_cs,
			envoyer_auteur: envoyerAuteur,
			partager_whatsapp: form.partager_whatsapp,
		});
</script>

<!--
	Un seul montage du formulaire, deux cadres possibles — et le CHOIX du cadre
	n'est plus écrit ici. `CadreFormulaire` le porte pour les six formulaires qui
	en ont besoin : il s'y écrivait cinq fois, et les copies avaient commencé à
	diverger (02/09/2026).

	Ce qui reste ici : `edition`, qui déclare le GESTE. Ce n'est pas décoratif —
	`lint:formulaires` l'exige, et c'est lui qui distingue « créer » de
	« corriger », ce que rien dans le balisage ne permettrait de deviner.
-->
<CadreFormulaire
	edition={modeEdition}
	titre={titreCadre}
	{cle}
	on:fermer={() => dispatch('annule')}
>
	<!--  ⚠️ Plus de `class:modal-body` ici : `CadreFormulaire` enveloppe lui-même
	      le contenu sur la classe par défaut (02/09/2026). Le laisser en
	      poserait un SECOND, et le padding serait compté deux fois. -->
	<div>
		<form on:submit|preventDefault={soumettre}>
			<!--  1. Titre. -->
			<SectionFormulaire premiere>
				<div class="field champ-large">
					<label for="ev-titre">Titre *</label>
					<input id="ev-titre" bind:value={form.titre} required />
				</div>
			</SectionFormulaire>

			<!--  2. Champs spécifiques de l'événement. -->
			{#if sectionPresente(EVENEMENT, etat, 'nature')}
				<SectionFormulaire titre="Détails">
					<div class="form-grid">
						<div class="field">
							<label for="ev-type">Type</label>
							<select id="ev-type" bind:value={form.type}>
								{#each types as t (t.val)}<option value={t.val}>{t.label}</option>{/each}
							</select>
						</div>
						<div class="field">
							<label for="ev-debut">Date de début *</label>
							<input id="ev-debut" type="date" bind:value={form.debut} required />
						</div>
						<div class="field">
							<label for="ev-heure">Heure (optionnelle)</label>
							<input id="ev-heure" type="time" bind:value={form.debut_heure} />
						</div>
						<div class="field">
							<label for="ev-fin">Fin</label>
							<input id="ev-fin" type="datetime-local" bind:value={form.fin} />
						</div>
						<div class="field">
							<label for="ev-lieu">Lieu</label>
							<input id="ev-lieu" bind:value={form.lieu} />
						</div>
						<div class="field">
							<label for="ev-prestataire">Prestataire</label>
							<select id="ev-prestataire" bind:value={form.prestataire_id}>
								<option value="">— Aucun —</option>
								{#each prestataires.filter((p) => p.actif !== false) as p (p.id)}
									<option value={String(p.id)}>{p.nom}</option>
								{/each}
							</select>
						</div>
						{#if form.prestataire_id && form.type !== 'maintenance_recurrente'}
							<div class="field">
								<label for="ev-frequence">Fréquence (optionnelle)</label>
								<select id="ev-frequence" bind:value={form.frequence_type}>
									<option value="">— Pas de récurrence —</option>
									<option value="fois_par_an">× / an</option>
									<option value="mois">Tous les N mois</option>
									<option value="semaines">Toutes les N semaines</option>
								</select>
							</div>
							{#if form.frequence_type}
								<div class="field">
									<label for="ev-frequence-valeur">Valeur</label>
									<input
										id="ev-frequence-valeur"
										type="number"
										min="1"
										bind:value={form.frequence_valeur}
										placeholder="ex: 2"
									/>
								</div>
							{/if}
						{/if}
					</div>
				</SectionFormulaire>
			{/if}

			<!--  3. Workflow — où en est cet événement.
	      🔴 LE KANBAN *EST* LE WORKFLOW (18/08/2026) : ses colonnes répondent
	      exactement à la question de la section 3 du cadre — « où en est cet
	      objet ? ». La section s'appelait « Suivi Kanban », ce qui nommait
	      l'écran où on le voit plutôt que la notion ; et avant cela elle était
	      rangée dans la DIFFUSION, qui dit qui le voit et non où il en est.
	      Aucun second champ d'état n'a été créé : deux notions de suivi sur le
	      même objet se contredisent au premier écart. -->
			<!--  3 à 10 : ordre, intitulés et séparations hérités du composant partagé.
	      Leur PRÉSENCE, elle, se lit dans la déclaration — plus aucune n'est
	      posée en dur (R4).

	      🔴 Le WORKFLOW et l'ÉPINGLAGE l'ont rejoint le 12/09/2026, signalés à
	      l'écran. Le premier tenait son rang à la main, au-dessus de cet appel ;
	      le second était une case écrite ICI, dans la Diffusion, avec son propre
	      glyphe — alors que `$lib/options-publication` porte la notion et que
	      tous les autres écrans la rendent dans « Options de publication ».
	      Deux écarts, une seule cause : un ordre écrit dans une documentation ne
	      se tient pas seul. -->
			<ChampsCommuns
				entite={EVENEMENT}
				avecSaisiPour
				{residentsSaisiPour}
				bind:saisiPour
				avecOptions={sectionPresente(EVENEMENT, etat, 'diffusion')}
				objet="événement"
				optionsRendues={['epingle', 'brouillon']}
				dejaEpingle={epingleInitial}
				bind:epingle={form.epingle}
				bind:brouillon={form.reserve_cs}
				epingleInterdit={form.affichable
					? ''
					: 'Un événement absent du fil d’activité ne peut pas y être épinglé.'}
				avecWorkflow={sectionPresente(EVENEMENT, etat, 'suivi')}
				demanderApercu={brouillonApercu}
				bind:refDiffusion
				envoiEnCours={submitting}
				on:envoyer={confirmerEnvoi}
				idPrefixe="ev"
				avecPerimetre={sectionPresente(EVENEMENT, etat, 'qui_le_voit')}
				bind:perimetre={formPerimetreCible}
				avecDescription={sectionPresente(EVENEMENT, etat, 'description')}
				bind:description={form.description}
				{assistant}
				bind:titreObjet={form.titre}
				bind:assisteIA={form.assiste_ia}
				descriptionPlaceholder="Description de l'événement…"
				avecPhotos={sectionPresente(EVENEMENT, etat, 'pieces_jointes')}
				bind:photos={photosUrls}
				avecDocuments={sectionPresente(EVENEMENT, etat, 'pieces_jointes')}
				bind:documents={fichiersUrls}
				avecDiffusion={sectionPresente(EVENEMENT, etat, 'diffusion')}
				bind:whatsapp={form.partager_whatsapp}
				bind:syndic={form.envoyer_syndic}
				bind:cs={form.envoyer_cs}
				bind:auteur={envoyerAuteur}
				auteurNom={nomCopie(form)}
			>
				<svelte:fragment slot="workflow">
					<!--  🔴 PASTILLES, jamais un `<select>` nu (R3, #423). Norme posée sur
			      Tickets, constatée, puis étendue ici (R5).
			      ⚠️ « Pas de suivi Kanban » est une pastille comme les autres, et elle
			      est active par défaut : l'absence de suivi est un choix qui se voit,
			      pas une option vide en tête d'une liste déroulante. La section n'est
			      donc PAS requise — un événement peut légitimement n'avoir aucun
			      suivi, à la différence de l'état d'un ticket.

			      ⚠️ Le mot « Kanban » est dans le libellé depuis le 19/08/2026,
			      demandé à l'écran. Sans lui, « Pas de suivi » se lisait comme « ce
			      dossier n'est pas suivi » — alors que les six autres pastilles
			      nomment des COLONNES du Kanban, et que l'événement reste évidemment
			      suivi par son fil d'historique. -->
					<div class="field champ-large">
						<!--  🔴 PASTILLES, jamais un `<select>` nu (R3, #423). Norme posée sur
			      Tickets, constatée, puis étendue ici (R5).
			      ⚠️ « Pas de suivi Kanban » est une pastille comme les autres, et elle
			      est active par défaut : l'absence de suivi est un choix qui se voit,
			      pas une option vide en tête d'une liste déroulante. La section n'est
			      donc PAS requise — un événement peut légitimement n'avoir aucun
			      suivi, à la différence de l'état d'un ticket.

			      ⚠️ Le mot « Kanban » est dans le libellé depuis le 19/08/2026,
			      demandé à l'écran. Sans lui, « Pas de suivi » se lisait comme « ce
			      dossier n'est pas suivi » — alors que les six autres pastilles
			      nomment des COLONNES du Kanban, et que l'événement reste évidemment
			      suivi par son fil d'historique. -->
						<WorkflowPastilles
							valeur={form.statut_kanban ?? ''}
							idTitre="ev-kanban-titre"
							options={[
								{ value: '', label: '— Pas de suivi Kanban' },
								...kanbanCols.map((c) => ({ value: c.id, label: c.label })),
							]}
							on:choisir={(e) => (form.statut_kanban = e.detail)}
						/>
					</div>
				</svelte:fragment>
				<svelte:fragment slot="diffusion">
					<div class="field champ-large">
						<label class="case">
							<input
								type="checkbox"
								bind:checked={form.affichable}
								disabled={form.type === 'maintenance_recurrente'}
							/>
							<span>Afficher dans le fil d'activité du tableau de bord</span>
						</label>
						{#if form.type === 'maintenance_recurrente'}
							<p class="aide sous-case">
								Les maintenances récurrentes restent hors du fil d'activité : elles se suivent dans
								le Kanban.
							</p>
						{/if}
					</div>
				</svelte:fragment>
			</ChampsCommuns>

			<!--  « Annuler » est À CÔTÉ d'« Enregistrer » — norme du 18/08/2026, posée sur
	      Tickets puis étendue. L'en-tête de page ne porte plus de seconde commande
	      d'annulation (#367). -->
			<PiedFormulaire enCours={submitting} on:annule />
		</form>
	</div>
</CadreFormulaire>

<style>
	/*  Mêmes règles, même raison que dans `FormulairePrestation` : le balisage
	    part avec ses styles, sinon la grille reste dans la page et le formulaire
	    s'affiche en une colonne écrasée (#344, reproduit le 15/08/2026). */
	.form-grid {
		grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr));
	}
	.form-grid .field {
		margin-bottom: 0;
	}

	/*  Une case et son libellé : ils étaient écrits en `style=` en ligne, avec un
	    `width:auto` posé à la main sur chaque `<input type="checkbox">` pour
	    annuler le `width:100%` des champs de saisie. Nommés ici, ils cessent
	    d'être à réécrire — c'est la même famille de défaut que le sélecteur nu
	    qui a étiré les cases de l'écran Communauté (16/08/2026). */
	/*  `.aide-case` est passée dans app.css le 17/08/2026 : FormulaireSondage en
	    avait besoin, et Svelte scope les styles — la reprendre ici en aurait fait
	    une seconde définition libre de diverger. */
</style>
