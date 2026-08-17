<!--
  Le formulaire de création d'un ticket — extrait de la page dédiée
  `tickets/nouveau` le 16/08/2026.

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

  ⚠️ AUCUN bouton d'annulation ici. La commande vit dans l'en-tête de page, où le
  bouton d'ouverture bascule en « ✕ Annuler » — deux commandes pour un formulaire
  est précisément le défaut relevé sur la modale du calendrier (#367).
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
	import { STATUT_TICKET_OPTIONS } from '$lib/tickets';

	const dispatch = createEventDispatcher<{ cree: Ticket }>();

	let titre = '';
	let description = '';
	let categorie = 'panne';
	let statut = 'ouvert';
	//  Workflow du ticket, VISIBLE de tous dès la création : c'est une information
	//  capitale pour le suivi, et la masquer laissait croire qu'un ticket n'a pas
	//  d'état tant que le CS ne l'a pas touché. Seul le CS peut la MODIFIER — un
	//  résident verrait sinon son signalement partir « Résolu », donc hors du
	//  suivi, sans que personne l'ait regardé. Le serveur refait le contrôle :
	//  liste blanche réservée au CS (socle 03 §1 — ce que l'interface grise n'est
	//  qu'un confort). Les options viennent de `$lib/tickets` — quatrième copie
	//  de cette liste jusqu'au 17/08/2026 (#415).
	let perimetreCible: string[] = perimetreDefautListe();
	let destinataireSyndic = false;
	let destinataireCs = false;
	let partagerWhatsapp = false;
	// Photos et documents sont téléversés dès leur sélection, avant que le ticket
	// existe : `POST /uploads/fichier` rend l'URL immédiatement. Les envoyer avec
	// la création est ce qui permet à l'e-mail syndic/CS de partir avec — quand
	// les photos étaient téléversées APRÈS, l'e-mail était déjà construit et
	// partait sans elles, sans que rien ne le signale.
	let photosUrls: string[] = [];
	let fichiersUrls: string[] = [];
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
		if ($isCS) {
			try {
				const all = await adminApi.utilisateurs();
				usersActifs = all.filter((u: any) => u.actif).sort((a: any, b: any) =>
					`${a.prenom} ${a.nom}`.localeCompare(`${b.prenom} ${b.nom}`)
				);
			} catch { /* ignore */ }
		}
	});

	const categories = [
		{ value: 'panne', label: '\u{1F6E0}️ Panne', description: 'Équipement défectueux, ascenseur, chauffage…' },
		{ value: 'nuisance', label: '\u{1F4E2} Nuisance', description: 'Bruit, odeur, parking…' },
		{ value: 'question', label: '❓ Question', description: 'Information, procédure…' },
		{ value: 'urgence', label: '\u{1F6A8} Urgence', description: 'Inondation, panne majeure, danger immédiat' },
		{ value: 'bug', label: '\u{1F41B} Bug', description: 'Problème technique sur le site ou l’application' },
	];

	const richEmpty = (html: string) => !html || html.replace(/<[^>]+>/g, '').trim() === '';

	async function submit() {
		if (!titre.trim() || richEmpty(description)) {
			error = 'Titre et description sont obligatoires.';
			return;
		}
		if ($isCS && modeSaisiPour === 'exterieur' && !saisiPourNom.trim()) {
			error = 'Veuillez saisir le nom de la personne.';
			return;
		}
		error = '';
		loading = true;
		try {
			const payload: any = {
				titre,
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
			error = e instanceof ApiError ? e.message : 'Erreur lors de la création';
		} finally {
			loading = false;
		}
	}
</script>

{#if categorie === 'urgence'}
	<div class="alert alert-error largeur-saisie" style="margin-bottom:1rem">
		&#x1F6A8; <strong>Urgence</strong> — Le conseil syndical et le syndic seront notifiés immédiatement.
		En cas de danger immédiat, composez le <strong>15 (SAMU), 17 (Police) ou 18 (Pompiers)</strong>.
	</div>
{/if}

{#if error}
	<div class="alert alert-error largeur-saisie">{error}</div>
{/if}

<FormulaireCreation titre="Signaler un problème">
	<form on:submit|preventDefault={submit}>
		<SectionFormulaire premiere>
		<fieldset class="field" style="border:none;padding:0;margin:0">
			<legend style="font-size:.875rem;font-weight:500;margin-bottom:.5rem;color:var(--color-text)">Catégorie *</legend>
			<div class="cat-grid">
				{#each categories as cat}
					<label class="cat-option" class:selected={categorie === cat.value}>
						<input type="radio" bind:group={categorie} value={cat.value} />
						<span class="cat-label">{cat.label}</span>
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
		      signalé par l'utilisateur le 16/08/2026). -->
		{#if $isCS}
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
		      dit qui le voit et où (section 9). -->
		<SectionFormulaire titre="Workflow" pour="ticket-statut">
			<div class="field champ-large">
				<select id="ticket-statut" bind:value={statut} disabled={!$isCS}>
					{#each STATUT_TICKET_OPTIONS as s}<option value={s.value}>{s.label}</option>{/each}
				</select>
				{#if !$isCS}
					<p class="aide-champ">Votre demande part en « Ouvert ». Le conseil syndical fait ensuite avancer son suivi.</p>
				{/if}
			</div>
		</SectionFormulaire>

		<!--  4 à 9 : l'ordre, les intitulés et les séparations sont hérités du
		      composant partagé — voir `ChampsCommuns.svelte`. -->
		<ChampsCommuns
			idPrefixe="ticket"
			avecPerimetre bind:perimetre={perimetreCible}
			avecDescription descriptionRequise bind:description
			descriptionPlaceholder="Décrivez le problème avec le maximum de détails (localisation, depuis quand, fréquence…)"
			avecPhotos bind:photos={photosUrls}
			avecDocuments bind:documents={fichiersUrls}
			avecDiffusion={$isCS}
			bind:whatsapp={partagerWhatsapp}
			bind:syndic={destinataireSyndic}
			bind:cs={destinataireCs}
			aideWhatsapp="Le ticket est publié sur le groupe WhatsApp ; les photos jointes partent avec."
		/>

		<!-- Pas de bouton « Annuler » ici : il vit dans l'en-tête de page (voir
		     l'en-tête de ce fichier). `.form-actions` vient d'app.css. -->
		<div class="form-actions">
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
