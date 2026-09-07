<script lang="ts">
	import { onMount } from 'svelte';
	import { copropriete as coproprieteApi } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { siteNomStore } from '$lib/stores/pageConfig';
	import Icon from '$lib/components/Icon.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import SectionContratReference from '$lib/components/SectionContratReference.svelte';
	import { fmtDateShort as fmtDate } from '$lib/date';

	$: _siteNom = $siteNomStore;

	//  UNIQUEMENT les champs que `CoproprieteUpdate` accepte. Sept autres
	//  figuraient ici — `code_postal`, `ville`, les quatre du syndic et
	//  `assurance_numero` — qui n'existent ni dans le schéma ni dans le modèle :
	//  Pydantic les jetait en silence, et le formulaire promettait donc un
	//  enregistrement qui n'avait pas lieu (signalé à l'usage le 13/08/2026).
	//  `assurance_numero` était le plus traître : le champ existe, sous le nom
	//  `assurance_numero_police`. Une lettre de plus et il ne s'enregistrait pas.
	//
	//  🔴 Les TROIS champs d'assurance ont quitté ce formulaire (#490) : ils
	//  décrivaient un contrat avec un prestataire, notion que le projet possède
	//  déjà. Les laisser ici referait exactement la faute décrite ci-dessus —
	//  un formulaire qui promet un enregistrement que le serveur n'accepte plus.
	let form: any = {
		nom: '',
		adresse: '',
		nb_lots_total: '',
		nb_lots_principaux: '',
		nb_parkings_communs: '',
		annee_construction: '',
		numero_immatriculation: '',
		//  Les deux DÉSIGNATIONS, seuls champs que la fiche écrit sur une section
		//  adossée à un contrat. `null` = aucun contrat désigné.
		assurance_contrat_id: null,
		syndic_contrat_id: null,
	};
	/**  Ce que la fiche AFFICHE des deux sections adossées à un contrat.
	 *
	 *   🔴 Lu, jamais réécrit — sauf la DÉSIGNATION (`*_contrat_id`), qui dit
	 *   lequel des contrats existants fait foi. Saisir ici la compagnie ou le
	 *   cabinet recréerait le doublon que #490 a supprimé.
	 *
	 *   ⚠️ Un seul objet pour les deux sections : deux objets auraient donné deux
	 *   façons de lire la même réponse. */
	let fiche: any = {};
	let loading = true;
	let saving = false;

	onMount(async () => {
		try {
			const data = await coproprieteApi.get();
			if (data) {
				Object.keys(form).forEach((k) => {
					if (data[k] !== undefined) form[k] = data[k] ?? '';
				});
				//  Lu, jamais réécrit — cf. le commentaire de `fiche`.
				fiche = data;
				form.assurance_contrat_id = data.assurance_contrat_id ?? null;
				form.syndic_contrat_id = data.syndic_contrat_id ?? null;
			}
		} catch {
			/* first time — empty form */
		} finally {
			loading = false;
		}
	});

	async function save() {
		saving = true;
		try {
			const payload = { ...form };
			//  Un champ numérique vide doit partir à `null`, jamais à `''` : Pydantic
			//  refuse la chaîne vide sur un `Optional[int]` et l'enregistrement échoue
			//  en silence côté écran. La règle était recopiée par champ — le troisième
			//  ajout est le bon moment pour cesser de la recopier.
			for (const champ of ['nb_lots_total', 'nb_lots_principaux', 'annee_construction']) {
				payload[champ] = payload[champ] === '' ? null : Number(payload[champ]);
			}
			//  ⚠️ La réponse du PATCH est RELUE, pas ignorée : changer le contrat
			//  désigné change tout ce que les deux sections affichent. Garder
			//  l'ancien affichage montrerait l'assureur précédent sous le nouveau
			//  choix, jusqu'au prochain rechargement de page.
			fiche = await coproprieteApi.update(payload);
			toast('success', 'Fiche enregistrée');
		} catch {
			toast('error', 'Erreur lors de la sauvegarde');
		} finally {
			saving = false;
		}
	}
</script>

<svelte:head><title>Admin — Fiche copropriété — {_siteNom}</title></svelte:head>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else}
	<section class="card config-section">
		<h2 class="config-section-title">
			<Icon name="building-2" size={17} />Fiche de la copropriété
		</h2>
		<form on:submit|preventDefault={save}>
			<SectionFormulaire premiere icone="settings" titre="Identité">
				<div class="form-grid largeur-saisie">
					<label class="field">
						<span>Nom de la résidence *</span>
						<input bind:value={form.nom} required />
					</label>
					<label class="field">
						<span>Adresse</span>
						<input bind:value={form.adresse} />
					</label>
					<!--  Les DEUX décomptes de la fiche du registre national (ANAH). Un seul
			      champ obligeait à choisir lequel perdre, et le chiffre saisi ne
			      disait pas lequel il était : 195 ou 63 pour la même résidence. Les
			      libellés reprennent mot pour mot ceux de la fiche, pour qu'on
			      recopie sans avoir à interpréter. -->
					<label
						class="field"
						title="Le « Nombre de lots » de la fiche d'immatriculation : tous les lots, caves et parkings compris."
					>
						<span>Nombre de lots — total, caves et parkings compris</span>
						<input type="number" min="1" bind:value={form.nb_lots_total} />
					</label>
					<label
						class="field"
						title="Le décompte qui porte les seuils réglementaires, et qui dit combien de foyers vivent ici."
					>
						<span>Dont lots d'habitation, commerces et bureaux</span>
						<input type="number" min="1" bind:value={form.nb_lots_principaux} />
					</label>
					<label class="field">
						<span>Année de construction</span>
						<input type="number" min="1800" max="2100" bind:value={form.annee_construction} />
					</label>
					<label class="field" style="grid-column:1/-1">
						<span>N° immatriculation (ANAH)</span>
						<input bind:value={form.numero_immatriculation} placeholder="ex : D75010800001" />
					</label>
				</div>
			</SectionFormulaire>

			<!--  🔴 DEUX SECTIONS, UN SEUL COMPOSANT (#553).
	      L'assurance et le syndic posent la même question — lequel des contrats
	      existants cette fiche désigne-t-elle ? — et affichent la même chose.
	      Les écrire deux fois aurait donné deux sections libres de diverger au
	      premier enrichissement demandé d'un seul côté.

	      ⚠️ On DÉSIGNE ici, on MODIFIE dans Prestataires → Contrats. Le
	      sélecteur ne crée ni ne modifie un contrat : il dit lequel fait foi. -->
			<SectionContratReference
				titre="Assurance"
				icone="shield"
				section="assurance"
				bind:contratId={form.assurance_contrat_id}
				documentId={fiche.assurance_document_id ?? null}
				lignes={[
					['Compagnie', fiche.assurance_compagnie],
					['Téléphone', fiche.assurance_telephone],
					['Courriel', fiche.assurance_email],
					['N° de police', fiche.assurance_numero_police],
					['Début', fiche.assurance_debut ? fmtDate(fiche.assurance_debut) : null],
					[
						'Échéance',
						fiche.assurance_echeance
							? fmtDate(fiche.assurance_echeance) +
								(fiche.assurance_reconduit ? ' (reconduit tacitement)' : '')
							: null,
					],
				]}
			>
				<svelte:fragment slot="renvoi">
					L'assurance est un <strong>contrat</strong> : elle se modifie dans
					<a href="/prestataires/contrats">Prestataires → Contrats</a>, avec son prestataire, son
					échéance et son attestation.
				</svelte:fragment>
			</SectionContratReference>

			<!--  ⚠️ L'INTERLOCUTEUR ne vient PAS du prestataire, mais de l'annuaire
	      (`MembreSyndic`). Le prestataire porte le CABINET, l'annuaire garde les
	      PERSONNES — et c'est de l'annuaire que partent les courriels, lu par dix
	      modules côté serveur. Recopier ces personnes dans les contacts du
	      prestataire aurait donné deux listes des mêmes gens : la faute de #490
	      transposée au circuit des notifications, où elle ne se verrait que le
	      jour où un message ne partirait pas. -->
			<!--  ⚠️ L'ICÔNE EST VÉRIFIÉE DANS LE CATALOGUE avant d'être écrite.
	      `briefcase` — le premier choix — n'existe pas dans
	      `$lib/icones-svg.json` : `Icon` serait retombé EN SILENCE sur
	      `help-circle`, et la section aurait porté un point d'interrogation sans
	      qu'aucun contrôle ne le dise. `users-round` dit « un cabinet, des
	      gens », et il est là. -->
			<SectionContratReference
				titre="Syndic"
				icone="users-round"
				section="syndic"
				bind:contratId={form.syndic_contrat_id}
				documentId={fiche.syndic_document_id ?? null}
				lignes={[
					['Cabinet', fiche.syndic_cabinet],
					['Téléphone', fiche.syndic_telephone],
					['Courriel', fiche.syndic_email],
					['N° de mandat', fiche.syndic_numero_mandat],
					['Début', fiche.syndic_debut ? fmtDate(fiche.syndic_debut) : null],
					//  Un mandat ne se reconduit pas : échu, il appelle une AG (#628).
					[
						'Mandat',
						fiche.syndic_echeance
							? fmtDate(fiche.syndic_echeance) +
								(fiche.syndic_echu ? ' — ÉCHU, à renouveler en AG' : '')
							: null,
					],
					['Interlocuteur', fiche.syndic_interlocuteur],
					['Courriel direct', fiche.syndic_interlocuteur_email],
				]}
			>
				<svelte:fragment slot="renvoi">
					Le cabinet et son mandat se modifient dans
					<a href="/prestataires/contrats">Prestataires → Contrats</a>. Ses
					<strong>membres</strong>, eux, vivent dans
					<a href="/espace-cs">Espace CS &rsaquo; Annuaire</a> — c'est de là que partent les courriels
					au cabinet.
				</svelte:fragment>
			</SectionContratReference>

			<!--  🔴 `.form-actions` — l'action principale va à DROITE (app.css,
	      `justify-content: flex-end`). Le bouton était dans un `<div>` NU, donc
	      collé à gauche : c'est ce que #501 signalait.

	      ⚠️ Pas de bouton « Annuler » ici, et c'est délibéré : AUCUN onglet
	      d'administration n'en porte. En ajouter un sur celui-ci recréerait la
	      divergence que ce lot corrige — l'écran rejoint les autres, il ne les
	      devance pas. -->
			<div class="largeur-saisie form-actions">
				<button class="btn btn-primary" type="submit" disabled={saving}>
					{saving ? 'Enregistrement…' : 'Enregistrer'}
				</button>
			</div>
		</form>
	</section>
{/if}

<style>
	/*  L'assurance en LECTURE : une liste de définitions, pas un formulaire.
	    La forme dit le régime — on lit ici, on modifie ailleurs (#490). */
	/*  ⚠️ Sur téléphone, deux colonnes serrent les valeurs longues (un nom de
	    compagnie, un numéro de police) au point de les couper mot à mot. La
	    liste passe alors en une colonne — `standards/11` §10. */
	@media (max-width: 560px) {
	}
	/*  `.form-section` et `.section-title` vivaient ici : ils REDÉFINISSAIENT la
	    carte et le titre de sous-section que `card` / `config-section-title` et
	    `SectionFormulaire` portent déjà (anatomie v2.94.0). Deux définitions d'un
	    même objet ne sont pas livrables — cet écran était simplement resté hors
	    du lot qui a aligné les huit autres onglets (#501). */
	.form-grid {
		grid-template-columns: repeat(auto-fill, minmax(min(220px, 100%), 1fr));
	}
</style>
