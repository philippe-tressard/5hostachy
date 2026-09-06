<!--
  Le formulaire de dépôt d'une idée — extrait de `sondages/+page.svelte` le
  16/08/2026.

  POURQUOI. La page portait TROIS formulaires de création (sondage, idée, annonce)
  et 868 lignes : le garde-fou de modularité a refusé qu'elle grossisse encore
  (`standards/02` §6). La règle est de découper quand on y touche, et c'est ce
  bloc-ci qui part — le plus autonome des trois, avec son propre état et sa propre
  responsabilité.

  Il suit le contrat de `FormulaireActualite` et `FormulaireTicket` : il porte son
  cadre (`CadreFormulaire`) et signale par un événement.

  ⚠️ Il porte DÉSORMAIS LES DEUX GESTES (#783, 06/09/2026) : déposer une idée
  et la corriger. Le cadre suit — créer dans une boîte, éditer dans une fenêtre
  (`ux-patterns` §14 bis) — et c'est `CadreFormulaire` qui le décide, pas ce
  fichier. Une seconde composante d'édition aurait dupliqué le formulaire entier.

  ⚠️ Deux défauts d'UX corrigés au passage, tous deux du même genre que ceux
  signalés par l'utilisateur sur les autres écrans :
    • le bouton « Soumettre » était posé NU dans le formulaire, donc cadré à
      GAUCHE, alors que `.form-actions` aligne à droite partout ailleurs ;
    • le champ Titre portait une mise en forme en `style=` au lieu d'hériter de
      `.field`, et n'occupait pas la ligne entière alors que c'est un texte libre
      (skill `ux-patterns` §9 bis).
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import CadreFormulaire from '$lib/components/CadreFormulaire.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import { sectionPresente, type Etat } from '$lib/entites/types';
	import { IDEE } from '$lib/entites/idee';
	import { perimetreDefautListe } from '$lib/perimetres';
	import { idees as ideesApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';

	//  L'API des idées ne rend pas de type dédié : l'événement porte l'objet créé
	//  tel quel, et la page recharge sa liste depuis le serveur.
	const dispatch = createEventDispatcher<{ cree: unknown; modifie: unknown; annule: void }>();

	/**  L'idée à corriger, ou `null` pour un dépôt. C'est la SEULE prop qui
	 *   distingue les deux gestes — tout le reste en découle. */
	export let idee: any = null;

	$: modeEdition = idee !== null;
	/**  L'état du cadre #430. Il était écrit en CONSTANTE `'creation'`, avec ce
	 *   commentaire : « corriger une idée déposée n'existe pas côté produit, et
	 *   l'écrire ainsi rend le manque visible en relecture ». Le manque a été
	 *   comblé (#783) : la constante devient une déduction. */
	$: etat = (modeEdition ? 'edition' : 'creation') as Etat;

	//  Initialisés À LA CONSTRUCTION, jamais réactifs : un `$:` écraserait la
	//  saisie en cours dès que le parent rafraîchit sa liste. C'est `{#key}` chez
	//  l'appelant qui remonte le composant d'une idée à l'autre — même contrat que
	//  `FormulaireAnnonce`.
	let form = { titre: idee?.titre ?? '', description: idee?.description ?? '' };
	let perimetreCible: string[] = [...(idee?.perimetre_cible ?? perimetreDefautListe())];
	//  Section 5 (#782). Vide = tous les résidents, ici comme côté serveur.
	let publicCible: string[] = [...(idee?.public_cible ?? [])];
	let submitting = false;

	async function enregistrer() {
		if (!form.titre || !form.description) {
			toast('error', 'Titre et description obligatoires');
			return;
		}
		submitting = true;
		try {
			if (modeEdition) {
				//  ⚠️ Le ciblage n'est PAS renvoyé : `IdeeUpdate` ne l'accepte pas.
				//  Restreindre après coup masquerait l'idée à des gens qui l'ont déjà
				//  votée — même décision que pour le sondage. L'envoyer quand même
				//  serait ignoré par le serveur, et ferait croire ici que ça marche.
				const maj = await ideesApi.modifier(idee.id, { ...form });
				toast('success', 'Idée mise à jour');
				dispatch('modifie', maj);
				return;
			}
			const creee = await ideesApi.create({
				...form,
				perimetre_cible: perimetreCible,
				public_cible: publicCible,
			});
			form = { titre: '', description: '' };
			perimetreCible = perimetreDefautListe();
			publicCible = [];
			toast('success', 'Idée soumise !');
			dispatch('cree', creee);
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			submitting = false;
		}
	}
</script>

<CadreFormulaire edition={modeEdition} titre={modeEdition ? 'Modifier l’idée' : 'Nouvelle idée'}>
	<form on:submit|preventDefault={enregistrer}>
		<label class="field champ-large">
			Titre *
			<input
				bind:value={form.titre}
				placeholder="Ex. Vélos électriques en libre-service"
				required
			/>
		</label>
		<!--  4 et 6 : le PÉRIMÈTRE et la description, hérités du composant partagé.
		      Le périmètre est arrivé le 18/08/2026 (migration 0153) — l'idée était la
		      dernière entité de la Communauté sans aucune notion de lieu, alors que
		      « un local à vélos dans le bâtiment 3 » et « l'éclairage du parking » ne
		      concernent pas les mêmes voisins.

		      La section 5 (destinataires) s'est ouverte le 06/09 (#782) ; les sections
		      2, 7, 8 et 9 restent `sansObjet`. C'est la DÉCLARATION qui le dit et qui
		      les fait disparaître — jamais une condition écrite ici. -->
		<ChampsCommuns
			idPrefixe="idee"
			avecPerimetre={sectionPresente(IDEE, etat, 'perimetre')}
			bind:perimetre={perimetreCible}
			avecDestinataires={sectionPresente(IDEE, etat, 'destinataires')}
			bind:destinataires={publicCible}
			avecDescription={sectionPresente(IDEE, etat, 'description')}
			descriptionRequise
			bind:description={form.description}
			descriptionPlaceholder="Décrivez votre idée…"
		/>
		<!--  « Annuler » est À CÔTÉ d'« Enregistrer » — norme du 18/08/2026, posée
		      sur Tickets, constatée, puis étendue. L'en-tête de page ne porte plus
		      de seconde commande d'annulation (#367). -->
		<div class="form-actions">
			<button type="button" class="btn btn-outline" on:click={() => dispatch('annule')}
				>Annuler</button
			>
			<button class="btn btn-primary" disabled={submitting}
				>{submitting ? 'Enregistrement…' : 'Enregistrer'}</button
			>
		</div>
	</form>
</CadreFormulaire>
