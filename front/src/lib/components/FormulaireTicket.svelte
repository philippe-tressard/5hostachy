<!--
  Le formulaire d'un ticket — celui qu'on remplit pour le CRÉER, et celui qu'on
  rouvre pour le MODIFIER. Un seul fichier pour les deux gestes.

  POURQUOI CE COMPOSANT EXISTE. `tickets/nouveau` était le dernier écran du site à
  créer un objet par **page dédiée**, le troisième paradigme que #367 avait éliminé
  partout ailleurs sans venir jusqu'ici (cf. `FormulaireCreation.svelte`, qui le
  nommait déjà comme le cas restant). Il en gardait les deux marques visibles : un
  « ← Retour » à gauche du titre là où tout le site porte « ✕ Annuler » à droite,
  et un seul bouton d'annulation en bas de formulaire.

  POURQUOI UN COMPOSANT plutôt que le formulaire recopié dans `tickets/+page.svelte` :
  cette page fait déjà 659 lignes. Y verser 280 lignes de formulaire la porterait à
  ~940, très au-delà des 500 lignes du rang 1 (`standards/02` §6). Les actualités
  ont résolu le même problème de la même façon — `FormulaireActualite.svelte` — et
  ce composant en suit le contrat à la lettre : il porte lui-même sa boîte
  `FormulaireCreation` et signale la création par l'événement `cree`.

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
	import { toast } from '$lib/components/Toast.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import { isCS } from '$lib/stores/auth';
	import { STATUT_TICKET_OPTIONS, CATEGORIES_TICKET } from '$lib/tickets';
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

	const dispatch = createEventDispatcher<{ cree: Ticket; modifie: Ticket; annule: void }>();

	let titre = ticket?.titre ?? '';
	let description = ticket?.description ?? '';
	let categorie = ticket?.categorie ?? 'panne';
	let statut = ticket?.statut ?? 'ouvert';
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
	let destinataireSyndic = false;
	let destinataireCs = false;
	let partagerWhatsapp = false;
	// Photos et documents sont téléversés dès leur sélection, avant que le ticket
	// existe : `POST /uploads/fichier` rend l'URL immédiatement. Les envoyer avec
	// la création est ce qui permet à l'e-mail syndic/CS de partir avec — quand
	// les photos étaient téléversées APRÈS, l'e-mail était déjà construit et
	// partait sans elles, sans que rien ne le signale.
	let photosUrls: string[] = [];
	//  Les documents déjà joints sont RECHARGÉS en édition : `PATCH` remplace la
	//  liste entière (`ticket.fichiers_urls = body.fichiers_urls`). Partir d'un
	//  tableau vide effacerait les pièces existantes au premier enregistrement —
	//  silencieusement, et sans qu'on ait touché à la section.
	let fichiersUrls: string[] = [...(ticket?.fichiers_urls ?? [])];
	let error = '';
	let loading = false;

	// Saisi pour (CS/Admin uniquement)
	type ModeSaisiPour = 'moi' | 'resident' | 'exterieur';
	let modeSaisiPour: ModeSaisiPour = 'moi';
	let saisiPourUserId: number | null = null;
	let saisiPourNom = '';
	let saisiPourEmail = '';
	let usersActifs: { id: number; prenom: string; nom: string; email: string }[] = [];

	onMount(async () => {
		// Rien à charger quand la section n'est pas rendue (cf. la déclaration).
		if ($isCS && sectionPresente(TICKET, etat, 'specifiques')) {
			try {
				const all = await adminApi.utilisateurs();
				usersActifs = all.filter((u: any) => u.actif).sort((a: any, b: any) =>
					`${a.prenom} ${a.nom}`.localeCompare(`${b.prenom} ${b.nom}`)
				);
			} catch { /* ignore */ }
		}
	});

	//  Les catégories viennent de `$lib/tickets` — quatrième copie de cette liste
	//  jusqu'au 17/08/2026, comme les statuts l'avaient été (#415).

	const richEmpty = (html: string) => !html || html.replace(/<[^>]+>/g, '').trim() === '';

	$: titreBoite = modeEdition
		? `Modifier le ticket #${ticket?.numero ?? ''}`
		: 'Signaler un problème';

	async function submit() {
		if (!titre.trim() || richEmpty(description)) {
			error = 'Titre et description sont obligatoires.';
			return;
		}
		if (!modeEdition && $isCS && modeSaisiPour === 'exterieur' && !saisiPourNom.trim()) {
			error = 'Veuillez saisir le nom de la personne.';
			return;
		}
		error = '';
		loading = true;
		try {
			if (ticket) {
				//  Tout ce que la déclaration rend en édition ET que `PATCH` sait
				//  écrire. `statut` n'accompagne le lot que pour le conseil syndical :
				//  le serveur répond 403 à quiconque d'autre le lui envoie, y compris
				//  à l'auteur corrigeant son propre ticket — l'envoyer inconditionnellement
				//  ferait échouer une correction de faute de frappe.
				const maj = await ticketsApi.update(ticket.id, {
					titre: titre.trim(),
					description,
					categorie,
					perimetre_cible: perimetreCible,
					fichiers_urls: fichiersUrls,
					...($isCS ? { statut } : {}),
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
				photos_urls: photosUrls,
				fichiers_urls: fichiersUrls,
			};
			if ($isCS) {
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
			error = e instanceof ApiError
				? e.message
				: modeEdition ? 'Erreur lors de l’enregistrement' : 'Erreur lors de la création';
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
		&#x1F6A8; <strong>Urgence</strong> — Le conseil syndical et le syndic seront notifiés immédiatement.
		En cas de danger immédiat, composez le <strong>15 (SAMU), 17 (Police) ou 18 (Pompiers)</strong>.
	</div>
{/if}

{#if error}
	<div class="alert alert-error largeur-saisie">{error}</div>
{/if}

<FormulaireCreation titre={titreBoite}>
	<form on:submit|preventDefault={submit}>
		<SectionFormulaire premiere>
		<fieldset class="field" style="border:none;padding:0;margin:0">
			<legend style="font-size:.875rem;font-weight:500;margin-bottom:.5rem;color:var(--color-text)">Catégorie *</legend>
			<div class="cat-grid">
				{#each CATEGORIES_TICKET as cat (cat.value)}
					<label class="cat-option" class:selected={categorie === cat.value}>
						<input type="radio" bind:group={categorie} value={cat.value} />
						<span class="cat-label">{cat.emoji} {cat.label}</span>
						<span class="cat-desc">{cat.description}</span>
					</label>
				{/each}
			</div>
		</fieldset>

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

		<!--  2. Champs spécifiques. « Saisi pour » était rendu APRÈS les pièces
		      jointes, entre les documents et la diffusion : le seul champ du site à
		      être hors de sa section. C'est un champ SPÉCIFIQUE du ticket — il
		      précède donc le workflow et le périmètre (`ux-patterns` §9 sexies,
		      signalé par l'utilisateur le 16/08/2026).
		      Sa présence par état est DÉCLARÉE (`$lib/entites/ticket`) : absente en
		      édition, motif `api` citant #431 — `TicketUpdate` accepte bien les trois
		      champs `saisi_pour_*` mais ne sait pas les EFFACER, et « En mon nom »
		      serait alors un choix sans effet, en silence. -->
		{#if $isCS && sectionPresente(TICKET, etat, 'specifiques')}
			<SectionFormulaire titre="Saisi pour">
				<div class="field champ-large saisi-pour-section">
					<div class="saisi-pour-tabs">
						<button type="button" class="tab-btn" class:active={modeSaisiPour === 'moi'} on:click={() => modeSaisiPour = 'moi'}>
							En mon nom
						</button>
						<button type="button" class="tab-btn" class:active={modeSaisiPour === 'resident'} on:click={() => modeSaisiPour = 'resident'}>
							Résident inscrit
						</button>
						<button type="button" class="tab-btn" class:active={modeSaisiPour === 'exterieur'} on:click={() => modeSaisiPour = 'exterieur'}>
							Personne extérieure
						</button>
					</div>
					{#if modeSaisiPour === 'resident'}
						<select bind:value={saisiPourUserId} style="margin-top:.5rem" aria-label="Résident concerné">
							<option value={null}>— Sélectionner un résident —</option>
							{#each usersActifs as u}
								<option value={u.id}>{u.prenom} {u.nom}{u.email ? ` (${u.email})` : ''}</option>
							{/each}
						</select>
					{:else if modeSaisiPour === 'exterieur'}
						<div style="margin-top:.5rem;display:flex;flex-direction:column;gap:.5rem">
							<input type="text" bind:value={saisiPourNom} placeholder="Nom complet *" aria-label="Nom complet de la personne" required />
							<input type="email" bind:value={saisiPourEmail} placeholder="Email (optionnel)" aria-label="Email de la personne" />
						</div>
					{/if}
				</div>
			</SectionFormulaire>
		{/if}

		<!--  3. Workflow — où en est le ticket. À distinguer de la diffusion, qui
		      dit qui le voit et où (section 9). IDENTIQUE en création et en
		      édition depuis le cadre #430 : une correction corrige l'état comme
		      elle corrige un titre, et c'est le `PATCH` qui a changé de nature
		      côté serveur (voir le bloc de commentaires du script). -->
		<SectionFormulaire titre="Workflow" pour="ticket-statut">
			<div class="field champ-large">
				<select id="ticket-statut" bind:value={statut} disabled={!$isCS}>
					{#each STATUT_TICKET_OPTIONS as s}<option value={s.value}>{s.label}</option>{/each}
				</select>
				{#if !$isCS}
					<p class="aide-champ">
						{modeEdition
							? 'Seul le conseil syndical fait avancer le suivi d’un ticket.'
							: 'Votre demande part en « Ouvert ». Le conseil syndical fait ensuite avancer son suivi.'}
					</p>
				{/if}
			</div>
		</SectionFormulaire>

		<!--  4 à 9 : l'ordre, les intitulés et les séparations sont hérités du
		      composant partagé — voir `ChampsCommuns.svelte`.
		      ⚠️ Aucune de ces sections n'est gouvernée par `modeEdition` : elles le
		      sont par la DÉCLARATION (`$lib/entites/ticket`), qui porte chaque
		      divergence avec son motif — et `npm run lint:etats` refuse qu'on
		      remette une condition en dur ici. Aujourd'hui :
		      • Photos — absente en édition, motif `api` #431 (`TicketUpdate`
		        n'accepte pas `photos_urls` : les proposer ferait disparaître la
		        sélection à l'enregistrement, en silence) ;
		      • Documents — OUVERTS à l'édition depuis #431 : `fichiers_urls` est
		        accepté, et une liste vide efface sans ambiguïté ;
		      • Diffusion — absente en édition, motif `geste` : les canaux
		        notifient, et rejouer un envoi à chaque faute de frappe rattrapée
		        est l'incident du triple envoi WhatsApp (14/08/2026). -->
		<ChampsCommuns
			idPrefixe="ticket"
			avecPerimetre={sectionPresente(TICKET, etat, 'perimetre')} bind:perimetre={perimetreCible}
			avecDescription={sectionPresente(TICKET, etat, 'description')} descriptionRequise bind:description
			descriptionPlaceholder="Décrivez le problème avec le maximum de détails (localisation, depuis quand, fréquence…)"
			avecPhotos={sectionPresente(TICKET, etat, 'photos')} bind:photos={photosUrls}
			avecDocuments={sectionPresente(TICKET, etat, 'documents')} bind:documents={fichiersUrls}
			avecDiffusion={$isCS && sectionPresente(TICKET, etat, 'diffusion')}
			bind:whatsapp={partagerWhatsapp}
			bind:syndic={destinataireSyndic}
			bind:cs={destinataireCs}
			aideWhatsapp="Le ticket est publié sur le groupe WhatsApp ; les photos jointes partent avec."
		/>

		<!-- Le bouton « Annuler » n'existe qu'en ÉDITION : en création, il vit dans
		     l'en-tête de page (voir l'en-tête de ce fichier). `.form-actions` vient
		     d'app.css. -->
		<div class="form-actions">
			{#if modeEdition}
				<button type="button" class="btn btn-outline" on:click={() => dispatch('annule')}>Annuler</button>
			{/if}
			<button type="submit" class="btn btn-primary" disabled={loading}>
				{loading ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
	</form>
</FormulaireCreation>

<style>
	.aide-champ { font-size: .8rem; color: var(--color-text-muted); line-height: 1.45; margin: .25rem 0 0; }
	.cat-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: .5rem;
	}

	.cat-option {
		display: flex;
		flex-direction: column;
		gap: .15rem;
		padding: .75rem;
		border: 2px solid var(--color-border);
		border-radius: var(--radius);
		cursor: pointer;
		transition: border-color .15s, background .15s;
	}

	.cat-option input[type="radio"] { display: none; }
	.cat-option.selected { border-color: var(--color-primary); background: var(--color-primary-light); }

	.cat-label { font-weight: 600; font-size: .9rem; }
	.cat-desc  { font-size: .78rem; color: var(--color-text-muted); }

	/*  `.intitule-champ` a disparu d'ici : « Saisi pour » est devenu le TITRE de
	    sa section (`SectionFormulaire`), qui porte déjà sa typographie. Un
	    intitulé de champ posé au-dessus d'un titre de section aurait dit deux
	    fois la même chose. */

	/* `.form-actions` n'est PAS redéfini ici : app.css le porte (l. 533). La page
	   dédiée en gardait une copie identique, donc inerte — même défaut que celui
	   nettoyé le 15/08 sur les autres écrans. */

	.saisi-pour-section {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: .75rem;
		margin-bottom: .5rem;
	}

	.saisi-pour-tabs {
		display: flex;
		gap: .25rem;
		margin-top: .5rem;
		flex-wrap: wrap;
	}

	.tab-btn {
		padding: .375rem .75rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: transparent;
		cursor: pointer;
		font-size: .85rem;
		color: var(--color-text-muted);
		transition: background .15s, color .15s, border-color .15s;
	}
	.tab-btn.active {
		background: var(--color-primary);
		color: #fff;
		border-color: var(--color-primary);
	}

	@media (max-width: 480px) { .cat-grid { grid-template-columns: 1fr; } }
</style>
