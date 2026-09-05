<!--
  Le formulaire d'un ticket — celui qu'on remplit pour le CRÉER, et celui qu'on
  rouvre pour le MODIFIER. Un seul fichier pour les deux gestes.

  POURQUOI CE COMPOSANT EXISTE. `tickets/nouveau` était le dernier écran du site à
  créer un objet par **page dédiée**, le troisième paradigme que #367 avait éliminé
  partout ailleurs sans venir jusqu'ici (cf. `FormulaireCreation.svelte`, qui le
  nommait déjà comme le cas restant). Il en gardait les deux marques visibles : un
  « ← Retour » à gauche du titre là où tout le site porte « ✕ Annuler » à droite,
  et un seul bouton d'annulation en bas de formulaire.

  POURQUOI UN COMPOSANT plutôt que le formulaire recopié dans la page : celle-ci
  ferait ~940 lignes, très au-delà du rang 1 (`standards/02` §6). Il suit le
  contrat de `FormulaireActualite` : il porte sa boîte et signale par `cree`.

  ## POURQUOI IL SERT AUSSI L'ÉDITION (17/08/2026, #425)

  Le crayon ✏️ d'une carte de ticket ouvrait un SECOND formulaire, écrit à la main
  dans la page : aucune section nommée, « Périmètre » écrit deux fois, des `style=`
  en ligne recomposant `.field`, et un avertissement d'accessibilité désactivé par
  `svelte-ignore` au lieu d'être corrigé. Le remettre au standard aurait produit
  **deux formulaires corrects pour le même objet**, donc deux libellés, deux ordres
  de champs et deux jeux de règles libres de diverger au premier lot suivant.
  Arbitré par l'utilisateur :

  > « je préfère que tu rendes paramétrable avec les valeurs déjà saisies le
  >   formulaire d'édition plutôt que de le dupliquer »

  D'où la prop `ticket` : `null` = création, un ticket = édition de ses valeurs.
  C'est le contrat qu'`EvolForm` porte déjà pour les évolutions (`editMode` +
  valeurs initiales), servi par quatre écrans.

  ⚠️ AUCUN bouton d'annulation EN CRÉATION. La commande vit dans l'en-tête de page,
  où le bouton d'ouverture bascule en « ✕ Annuler » — deux commandes pour un
  formulaire est précisément le défaut relevé sur la modale du calendrier (#367).
  En ÉDITION il n'y a pas d'en-tête pour la porter (le formulaire s'ouvre dans la
  carte du ticket) : le bouton est alors rendu ici, comme le fait `EvolForm`.
-->
<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { perimetreDefautListe } from '$lib/perimetres';
	import { tickets as ticketsApi, admin as adminApi, ApiError, type Ticket } from '$lib/api';
	import ChampSaisiPour from '$lib/components/ChampSaisiPour.svelte';
	import ChampConfidentiel from '$lib/components/ChampConfidentiel.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import WorkflowPastilles from '$lib/components/WorkflowPastilles.svelte';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import { isCS } from '$lib/stores/auth';
	import { STATUT_TICKET_OPTIONS, CATEGORIES_TICKET, type ModeSaisiPour } from '$lib/tickets';
	import type { Etat } from '$lib/entites/types';
	import { sectionPresente } from '$lib/entites/types';
	import { TICKET } from '$lib/entites/ticket';

	/**  Le ticket à MODIFIER, avec ses valeurs déjà saisies. `null` (défaut) =
	 *   création. Le mode ne change pas pendant la vie du composant : l'appelant le
	 *   remonte à neuf (`{#key}`) quand il passe d'un ticket à l'autre, exactement
	 *   comme il le fait pour `EvolForm`. */
	export let ticket: Ticket | null = null;

	const modeEdition = ticket !== null;

	/**  L'état du cadre #430 que ce formulaire rend. C'est LUI qui décide des
	 *   sections, via `sectionPresente(TICKET, etat, …)` — plus aucune condition
	 *   `!modeEdition` ne gouverne une section ici, et `npm run lint:etats` le
	 *   refuse. Le mode ne change pas pendant la vie du composant. */
	const etat: Etat = modeEdition ? 'edition' : 'creation';

	//  `CATEGORIES_TICKET` parle en `value`/`description`, `ChoixPastilles` en
	//  `val`/`desc` : l'adaptation se fait ICI, chez l'appelant, et non par une
	//  variante du composant — la table est verrouillée côté API par
	//  `test_statuts_tickets.py`, et une variante ajoutée pour accueillir un
	//  écart existant ne factorise pas, elle entérine (R3 bis).
	const OPTIONS_CATEGORIE = CATEGORIES_TICKET.map((c) => ({
		val: c.value,
		label: `${c.emoji} ${c.label}`,
		desc: c.description,
	}));

	const dispatch = createEventDispatcher<{ cree: Ticket; modifie: Ticket; annule: void }>();

	let titre = ticket?.titre ?? '';
	let description = ticket?.description ?? '';
	let categorie = ticket?.categorie ?? 'panne';
	let statut = ticket?.statut ?? 'ouvert';
	//  🔒 Confidentiel (#710) — le CS seul le pose, et le serveur le revérifie.
	let confidentiel = ticket?.confidentiel ?? false;
	//  Workflow du ticket, VISIBLE de tous dès la création : c'est une information
	//  capitale pour le suivi, et la masquer laissait croire qu'un ticket n'a pas
	//  d'état tant que le CS ne l'a pas touché. Seul le CS peut la MODIFIER — un
	//  résident verrait sinon son signalement partir « Résolu », donc hors du
	//  suivi, sans que personne l'ait regardé. Le serveur refait le contrôle :
	//  liste blanche réservée au CS (socle 03 §1 — ce que l'interface grise n'est
	//  qu'un confort). Les options viennent de `$lib/tickets` — quatrième copie
	//  de cette liste jusqu'au 17/08/2026 (#415).
	//
	//  ✅ EN ÉDITION AUSSI, depuis le cadre #430 (17/08/2026). L'édition CORRIGE :
	//  une erreur, un oubli, un complément — et l'état s'y corrige comme les
	//  autres champs. Le motif invoqué la veille (« l'état se change depuis le
	//  fil, pour qu'il y laisse une trace ») n'existe pas dans le cadre : les
	//  trois motifs sont `geste`, `hérité` et `api`, et aucun ne couvrait
	//  celui-là.
	//
	//  La trace ne se perd pas pour autant — c'est le SERVEUR qui a changé :
	//  `PATCH /tickets/{id}` n'écrit plus une transition de workflow mais une
	//  **correction** (`crud.py`). Corriger une faute de frappe n'apparaît donc
	//  plus dans l'Historique comme une étape du suivi, et le changement d'état
	//  volontaire garde le sien, via les évolutions.

	//  Copie défensive du périmètre : le tableau vient du ticket affiché dans la
	//  liste. Lié tel quel, une sélection abandonnée resterait visible sur la carte
	//  alors que rien n'a été enregistré.
	let perimetreCible: string[] = [...(ticket?.perimetre_cible ?? perimetreDefautListe())];
	//  ✅ La DIFFUSION est rouverte à l'édition (18/08/2026, arbitrage utilisateur) :
	//  le conseil syndical doit pouvoir décider d'envoyer au syndic un ticket déjà
	//  saisi. Les cases reprennent les valeurs enregistrées — « telle qu'à la
	//  création ».
	//
	//  ⚠️ Ce qui rend la réouverture SANS RISQUE vit côté serveur : seule la
	//  transition décoché → coché envoie. Un canal déjà coché ne repart pas à chaque
	//  enregistrement — sinon corriger une faute de frappe rejouerait l'envoi, et
	//  c'est l'incident du triple envoi WhatsApp du 14/08/2026.
	let destinataireSyndic = ticket?.destinataire_syndic ?? false;
	let destinataireCs = ticket?.destinataire_cs ?? false;
	let envoyerAuteur = false;
	//  ⚠️ Le partage WhatsApp est un ACTE, pas un champ : `Ticket` n'a pas cette
	//  colonne (à la différence de `Publication`). La case repart donc DÉCOCHÉE à
	//  chaque ouverture — il n'y a pas d'état à restaurer, seulement un envoi à
	//  demander. La cocher publie sur le groupe, une fois.
	let partagerWhatsapp = false;
	// Photos et documents sont téléversés dès leur sélection, avant que le ticket
	// existe : `POST /uploads/fichier` rend l'URL immédiatement. Les envoyer avec
	// la création est ce qui permet à l'e-mail syndic/CS de partir avec — quand
	// les photos étaient téléversées APRÈS, l'e-mail était déjà construit et
	// partait sans elles, sans que rien ne le signale.
	//  RECHARGÉES en édition depuis le 18/08/2026, comme les documents : `PATCH`
	//  remplace la liste entière, donc partir d'un tableau vide effacerait les photos
	//  existantes au premier enregistrement — silencieusement.
	let photosUrls: string[] = [...(ticket?.photos_urls ?? [])];
	//  Les documents déjà joints sont RECHARGÉS en édition : `PATCH` remplace la
	//  liste entière (`ticket.fichiers_urls = body.fichiers_urls`). Partir d'un
	//  tableau vide effacerait les pièces existantes au premier enregistrement —
	//  silencieusement, et sans qu'on ait touché à la section.
	let fichiersUrls: string[] = [...(ticket?.fichiers_urls ?? [])];
	let error = '';
	let loading = false;

	// Saisi pour (CS/Admin uniquement) — la saisie vit dans `ChampSaisiPour`.
	//  L'état initial vient du ticket : la section est ouverte à l'édition depuis que
	//  le serveur sait EFFACER les `saisi_pour_*` (il lit la PRÉSENCE du champ, pas
	//  sa non-nullité). L'ouvrir sans pré-remplir aurait proposé « En mon nom » sur un
	//  ticket saisi pour quelqu'un — et l'aurait effacé au premier enregistrement.
	let modeSaisiPour: ModeSaisiPour = ticket?.saisi_pour_user_id
		? 'resident'
		: ticket?.saisi_pour_nom
			? 'exterieur'
			: 'moi';
	let saisiPourUserId: number | null = ticket?.saisi_pour_user_id ?? null;
	let saisiPourNom = ticket?.saisi_pour_nom ?? '';
	let saisiPourEmail = ticket?.saisi_pour_email ?? '';
	let usersActifs: { id: number; prenom: string; nom: string; email: string }[] = [];

	onMount(async () => {
		// Rien à charger quand la section n'est pas rendue (cf. la déclaration).
		if ($isCS && sectionPresente(TICKET, etat, 'specifiques')) {
			try {
				const all = await adminApi.utilisateurs();
				usersActifs = all
					.filter((u: any) => u.actif)
					.sort((a: any, b: any) => `${a.prenom} ${a.nom}`.localeCompare(`${b.prenom} ${b.nom}`));
			} catch {
				/* ignore */
			}
		}
	});

	//  Les catégories viennent de `$lib/tickets` — quatrième copie de cette liste
	//  jusqu'au 17/08/2026, comme les statuts l'avaient été (#415).

	const richEmpty = (html: string) => !html || html.replace(/<[^>]+>/g, '').trim() === '';

	//  ── L'aperçu avant diffusion (#498) ───────────────────────────────────────
	//  Il ne s'interpose QUE si un canal est coché : sans diffusion il n'y a rien
	//  à prévisualiser, et une modale de plus serait une étape gratuite entre
	//  l'utilisateur et son ticket.
	//  ⚠️ Création seulement. En édition, cocher un canal renvoie l'objet tel
	//  qu'il est déjà : c'est un geste différent, il aura son propre lot.
	$: aUneDiffusion = destinataireSyndic || destinataireCs || partagerWhatsapp;
	//  L'état et la modale vivent dans `SectionDiffusion` depuis le 20/08/2026 —
	//  l'aperçu appartient à l'objet Diffusion, pas à ses appelants (#498). Ne
	//  reste ici que le BROUILLON, que ce formulaire seul connaît.
	let refDiffusion: any = null;
	const brouillonApercu = () =>
		ticketsApi.apercuDiffusion({
			titre: titre.trim(),
			description,
			categorie,
			perimetre_cible: perimetreCible,
			photos_urls: photosUrls,
			fichiers_urls: fichiersUrls,
			destinataire_syndic: destinataireSyndic,
			destinataire_cs: destinataireCs,
			partager_whatsapp: partagerWhatsapp,
			envoyer_auteur: envoyerAuteur,
		});

	$: titreBoite = modeEdition
		? `Modifier le ticket #${ticket?.numero ?? ''}`
		: 'Signaler un problème';

	/** Contrôles de saisie — communs à la soumission directe et à l'aperçu. */
	function saisieValide(): boolean {
		if (!titre.trim() || richEmpty(description)) {
			error = 'Titre et description sont obligatoires.';
			return false;
		}
		if ($isCS && modeSaisiPour === 'exterieur' && !saisiPourNom.trim()) {
			error = 'Veuillez saisir le nom de la personne.';
			return false;
		}
		error = '';
		return true;
	}

	/**  Le geste de soumission : aperçu d'abord si un canal est coché.
	 *
	 *   L'aperçu s'intercale ICI et non dans `submit` : celui-ci reste le chemin
	 *   d'enregistrement, appelé aussi bien par le formulaire que par la
	 *   confirmation de la modale. Deux chemins qui créeraient le ticket chacun de
	 *   leur côté finiraient par diverger. */
	function soumettre() {
		if (!saisieValide()) return;
		if (!modeEdition && refDiffusion?.ouvrirSiDiffusion(aUneDiffusion)) return;
		void submit();
	}

	async function submit() {
		if (!saisieValide()) return;
		refDiffusion?.fermerApercu();
		loading = true;
		try {
			if (ticket) {
				//  Tout ce que la déclaration rend en édition ET que `PATCH` sait
				//  écrire. `statut` n'accompagne le lot que pour le conseil syndical :
				//  le serveur répond 403 à quiconque d'autre le lui envoie, y compris
				//  à l'auteur corrigeant son propre ticket — l'envoyer inconditionnellement
				//  ferait échouer une correction de faute de frappe.
				//  Tout ce que la déclaration rend en édition — les neuf sections. Les
				//  trois `saisi_pour_*` partent TOUJOURS ensemble, y compris à `null` :
				//  c'est leur PRÉSENCE qui dit au serveur d'écrire, et c'est ce qui
				//  permet de revenir à « En mon nom ».
				const maj = await ticketsApi.update(ticket.id, {
					titre: titre.trim(),
					description,
					categorie,
					perimetre_cible: perimetreCible,
					photos_urls: photosUrls,
					fichiers_urls: fichiersUrls,
					...($isCS
						? {
								statut,
								confidentiel,
								destinataire_syndic: destinataireSyndic,
								destinataire_cs: destinataireCs,
								partager_whatsapp: partagerWhatsapp,
								saisi_pour_user_id: modeSaisiPour === 'resident' ? saisiPourUserId : null,
								saisi_pour_nom: modeSaisiPour === 'exterieur' ? saisiPourNom.trim() || null : null,
								saisi_pour_email:
									modeSaisiPour === 'exterieur' ? saisiPourEmail.trim() || null : null,
							}
						: {}),
				});
				toast('success', 'Ticket modifié');
				dispatch('modifie', maj);
				return;
			}
			const payload: any = {
				titre: titre.trim(),
				description,
				categorie,
				perimetre_cible: perimetreCible,
				destinataire_syndic: destinataireSyndic,
				destinataire_cs: destinataireCs,
				partager_whatsapp: partagerWhatsapp,
				envoyer_auteur: envoyerAuteur,
				photos_urls: photosUrls,
				fichiers_urls: fichiersUrls,
			};
			if ($isCS) {
				//  Le Workflow était DÉCORATIF à la création : les pastilles s'affichaient,
				//  se cliquaient, et `statut` ne partait pas — le ticket repartait toujours
				//  en « Ouvert » (#435). Le serveur l'accepte pourtant depuis le 16/08, avec
				//  une liste blanche DÉRIVÉE de l'énumération et réservée au CS ; seule la
				//  charge utile l'avait oublié. Comme en édition, il n'accompagne le lot que
				//  pour le CS : un résident ne doit pas ouvrir un ticket déjà « Résolu ».
				payload.statut = statut;
				payload.confidentiel = confidentiel;
				if (modeSaisiPour === 'resident' && saisiPourUserId) {
					payload.saisi_pour_user_id = saisiPourUserId;
				} else if (modeSaisiPour === 'exterieur') {
					if (saisiPourNom.trim()) payload.saisi_pour_nom = saisiPourNom.trim();
					if (saisiPourEmail.trim()) payload.saisi_pour_email = saisiPourEmail.trim();
				}
			}
			const t = await ticketsApi.create(payload);
			toast('success', `Ticket ${t.numero} créé avec succès`);
			dispatch('cree', t);
		} catch (e) {
			error =
				e instanceof ApiError
					? e.message
					: modeEdition
						? 'Erreur lors de l’enregistrement'
						: 'Erreur lors de la création';
		} finally {
			loading = false;
		}
	}
</script>

<!--  L'avertissement n'est rendu qu'en création : c'est l'envoi du ticket qui
      notifie. Requalifier un ticket existant en « Urgence » ne déclenche aucune
      alerte — l'afficher ici promettrait une notification qui ne partira pas. -->
{#if !modeEdition && categorie === 'urgence'}
	<div class="alert alert-error largeur-saisie" style="margin-bottom:1rem">
		&#x1F6A8; <strong>Urgence</strong> — Le conseil syndical et le syndic seront notifiés
		immédiatement. En cas de danger immédiat, composez le
		<strong>15 (SAMU), 17 (Police) ou 18 (Pompiers)</strong>.
	</div>
{/if}

{#if error}
	<div class="alert alert-error largeur-saisie">{error}</div>
{/if}

<FormulaireCreation titre={titreBoite} encadre={!modeEdition}>
	<form on:submit|preventDefault={soumettre}>
		<!--  1. Titre — et lui seul. La catégorie était rendue ICI, et AVANT le
		      titre : le premier champ de la première section n'était pas le titre.
		      Arbitré par l'utilisateur le 18/08/2026 — elle qualifie le ticket, elle
		      est donc un champ spécifique (section 2). -->
		<SectionFormulaire premiere>
			<div class="field champ-large">
				<label for="titre">Titre *</label>
				<input
					id="titre"
					type="text"
					bind:value={titre}
					required
					placeholder="Ex : Ascenseur bâtiment A en panne"
					maxlength="200"
				/>
			</div>
		</SectionFormulaire>

		<!--  2. Champs spécifiques — DEUX champs nommés, dans cet ordre : la
		      catégorie, puis « Saisi pour ». Ce dernier était rendu APRÈS les pièces
		      jointes, entre les documents et la diffusion : le seul champ du site à
		      être hors de sa section (signalé le 16/08/2026).
		      ⚠️ La SECTION est présente en édition — la catégorie s'y corrige comme
		      le titre —, mais « Saisi pour » n'y est pas : `TicketUpdate` ne sait pas
		      EFFACER les `saisi_pour_*`, et « En mon nom » serait un choix sans effet.
		      R4 ne déclare que des sections, pas des champs : ce motif `api` (#431)
		      vit dans la déclaration en commentaire, faute de pouvoir s'y écrire. -->
		{#if sectionPresente(TICKET, etat, 'specifiques')}
			<SectionFormulaire titre="Catégorie" requis idTitre="ticket-categorie-titre">
				<!--  🔴 `ChoixPastilles` en mode radio depuis le 30/08/2026, signalé à
				      l'écran : *« dans tickets tu ne peux pas réduire ces pastilles à la
				      même taille que nouveau prestataire »*. C'étaient des cartes maison,
				      deux fois plus hautes que les pastilles du même site pour la même
				      question posée.
				      `ux-patterns` refusait la conversion — à raison : `Pastille` rendait
				      un `<button>`, et un `radiogroup` y aurait perdu ses flèches. La
				      réponse a été d'ENRICHIR l'objet plutôt que de le contourner : la
				      pastille sait désormais porter un `<input type="radio">`, masqué à
				      l'œil mais pas à l'accessibilité. -->
				<ChoixPastilles
					options={OPTIONS_CATEGORIE}
					bind:valeur={categorie}
					tous={false}
					radio="ticket-categorie"
					libelle="Catégorie"
					avecDetail
				/>
			</SectionFormulaire>
		{/if}

		{#if $isCS && sectionPresente(TICKET, etat, 'specifiques')}
			<ChampSaisiPour
				bind:mode={modeSaisiPour}
				bind:userId={saisiPourUserId}
				bind:nom={saisiPourNom}
				bind:email={saisiPourEmail}
				residents={usersActifs}
			/>

			<ChampConfidentiel bind:confidentiel />
		{/if}

		<!--  3. Workflow — où en est le ticket. À distinguer de la diffusion, qui
		      dit qui le voit et où (section 9). IDENTIQUE en création et en
		      édition depuis le cadre #430 : une correction corrige l'état comme
		      elle corrige un titre, et c'est le `PATCH` qui a changé de nature
		      côté serveur (voir le bloc de commentaires du script). -->
		<SectionFormulaire titre="Workflow" requis idTitre="ticket-workflow-titre">
			<div class="field champ-large">
				<!--  🔴 PASTILLES, jamais un `<select>` nu (R3, #423). « Ouvert » est
				      active par défaut à la création — l'état de départ se voit, il ne
				      se devine pas. Un résident ne peut pas faire avancer le suivi :
				      la rangée est alors en lecture, et le serveur refait le contrôle
				      (liste blanche CS) — ce que l'interface interdit n'est qu'un
				      confort. -->
				<WorkflowPastilles
					options={STATUT_TICKET_OPTIONS}
					valeur={statut}
					lecture={!$isCS}
					idTitre="ticket-workflow-titre"
					on:choisir={(e) => (statut = e.detail)}
				/>
				{#if !$isCS}
					<p class="aide-champ">
						{modeEdition
							? 'Seul le conseil syndical fait avancer le suivi d’un ticket.'
							: 'Votre demande part en « Ouvert ». Le conseil syndical fait ensuite avancer son suivi.'}
					</p>
				{/if}
			</div>
		</SectionFormulaire>

		<!--  4 à 9 : ordre, intitulés et séparations hérités de `ChampsCommuns`.
		      🔴 Aucune n'est gouvernée par `modeEdition` mais par la DÉCLARATION
		      (`$lib/entites/ticket`), qui porte chaque divergence avec son motif ;
		      `lint:etats` refuse qu'on remette une condition en dur ici.
		      ⚠️ Les motifs NE SE RECOPIENT PAS : ce commentaire les listait, et
		      il avait divergé — il annonçait encore Photos en motif `api`, soldé
		      le 18/08/2026. Une copie d'une source unique est une source de plus. -->
		<ChampsCommuns
			bind:refDiffusion
			demanderApercu={brouillonApercu}
			envoiEnCours={loading}
			on:envoyer={() => void submit()}
			idPrefixe="ticket"
			avecPerimetre={sectionPresente(TICKET, etat, 'perimetre')}
			bind:perimetre={perimetreCible}
			avecDescription={sectionPresente(TICKET, etat, 'description')}
			descriptionRequise
			bind:description
			descriptionPlaceholder="Décrivez le problème avec le maximum de détails (localisation, depuis quand, fréquence…)"
			avecPhotos={sectionPresente(TICKET, etat, 'photos')}
			bind:photos={photosUrls}
			avecDocuments={sectionPresente(TICKET, etat, 'documents')}
			bind:documents={fichiersUrls}
			avecDiffusion={$isCS && sectionPresente(TICKET, etat, 'diffusion')}
			bind:whatsapp={partagerWhatsapp}
			bind:syndic={destinataireSyndic}
			bind:cs={destinataireCs}
			bind:auteur={envoyerAuteur}
			auteurNom={ticket?.auteur_nom ?? ''}
			aideWhatsapp="Le ticket est publié sur le groupe WhatsApp ; les photos jointes partent avec."
		/>

		<!--  « Annuler » est À CÔTÉ d'« Enregistrer », dans les DEUX gestes
		      (18/08/2026) : *« c'est plus logique à côté du bouton de l'action »*. Il
		      vivait en création dans l'en-tête de page et en édition ici — le même
		      geste avait deux emplacements selon l'écran.

		      ⚠️ Corollaire non négociable : l'en-tête ne porte PLUS « ✕ Annuler »
		      quand le formulaire est ouvert. Deux commandes d'annulation pour un seul
		      formulaire est le défaut relevé sur la modale du calendrier (#367) —
		      c'est la page qui masque son bouton d'ouverture. -->
		<div class="form-actions">
			<button type="button" class="btn btn-outline" on:click={() => dispatch('annule')}
				>Annuler</button
			>
			<button type="submit" class="btn btn-primary" disabled={loading}>
				{loading ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
	</form>
</FormulaireCreation>

<!--  L'aperçu s'ouvre PAR-DESSUS le formulaire, jamais à sa place : « Retour au
      formulaire » doit rendre la saisie intacte, et un formulaire démonté puis
      remonté la perdrait. C'est la moitié de l'arbitrage du 19/08. -->
<style>
	.aide-champ {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		line-height: 1.45;
		margin: 0.25rem 0 0;
	}
	/*  `.cat-grid`, `.cat-option`, `.cat-label`, `.cat-desc` retirées le 30/08/2026 :
	    les catégories passent par `ChoixPastilles`, qui porte son style. L'une
	    d'elles masquait le radio en `display:none` — donc hors tabulation ET hors
	    arbre d'accessibilité ; `Pastille` le masque par découpage, ce qui le garde
	    focusable et lu. */

	/*  `.intitule-champ` a disparu d'ici : « Saisi pour » est devenu le TITRE de
	    sa section (`SectionFormulaire`), qui porte déjà sa typographie. Un
	    intitulé de champ posé au-dessus d'un titre de section aurait dit deux
	    fois la même chose. */

	/* `.form-actions` n'est PAS redéfini ici : app.css le porte (l. 533). La page
	   dédiée en gardait une copie identique, donc inerte — même défaut que celui
	   nettoyé le 15/08 sur les autres écrans. */

	/*  `.saisi-pour-*` et `.tab-btn` sont partis avec leur balisage dans
	    `ChampSaisiPour.svelte` (#498) — les garder ici en ferait des règles
	    orphelines, c'est-à-dire la moitié du défaut que `lint:classes-nues`
	    surveille par l'autre bout. */
</style>
