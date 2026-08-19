<script lang="ts">
	import { onMount } from 'svelte';
	import { copropriete as coproprieteApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { siteNomStore } from '$lib/stores/pageConfig';
	import Icon from '$lib/components/Icon.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';

	$: _siteNom = $siteNomStore;

	//  UNIQUEMENT les champs que `CoproprieteUpdate` accepte. Sept autres
	//  figuraient ici — `code_postal`, `ville`, les quatre du syndic et
	//  `assurance_numero` — qui n'existent ni dans le schéma ni dans le modèle :
	//  Pydantic les jetait en silence, et le formulaire promettait donc un
	//  enregistrement qui n'avait pas lieu (signalé à l'usage le 13/08/2026).
	//  `assurance_numero` était le plus traître : le champ existe, sous le nom
	//  `assurance_numero_police`. Une lettre de plus et il ne s'enregistrait pas.
	let form: any = {
		nom: '', adresse: '', nb_lots_total: '', nb_lots_principaux: '', nb_parkings_communs: '',
		annee_construction: '', numero_immatriculation: '',
		assurance_compagnie: '', assurance_numero_police: '', assurance_echeance: ''
	};
	let loading = true;
	let saving = false;

	onMount(async () => {
		try {
			const data = await coproprieteApi.get();
			if (data) {
				Object.keys(form).forEach(k => { if (data[k] !== undefined) form[k] = data[k] ?? ''; });
			}
		} catch { /* first time — empty form */ }
		finally { loading = false; }
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
			await coproprieteApi.update(payload);
			toast('success', 'Fiche enregistrée');
		} catch { toast('error', 'Erreur lors de la sauvegarde'); }
		finally { saving = false; }
	}
</script>

<svelte:head><title>Admin — Fiche copropriété — {_siteNom}</title></svelte:head>


{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else}
<section class="card config-section">
<h2 class="config-section-title"><Icon name="building-2" size={17} />Fiche de la copropriété</h2>
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
			<label class="field" title="Le « Nombre de lots » de la fiche d'immatriculation : tous les lots, caves et parkings compris.">
				<span>Nombre de lots — total, caves et parkings compris</span>
				<input type="number" min="1" bind:value={form.nb_lots_total} />
			</label>
			<label class="field" title="Le décompte qui porte les seuils réglementaires, et qui dit combien de foyers vivent ici.">
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

	<SectionFormulaire icone="shield" titre="Assurance">
		<div class="form-grid largeur-saisie">
			<label class="field">
				<span>Compagnie</span>
				<input bind:value={form.assurance_compagnie} />
			</label>
			<label class="field">
				<span>N° de contrat</span>
				<input bind:value={form.assurance_numero_police} />
			</label>
			<label class="field">
				<span>Échéance</span>
				<input type="date" bind:value={form.assurance_echeance} />
			</label>
		</div>
	</SectionFormulaire>

	<!--  La section « Syndic » vivait ici et n'enregistrait RIEN : ses quatre champs
	      n'existent ni dans `CoproprieteUpdate` ni dans le modèle `Copropriete`,
	      donc Pydantic les jetait en silence. Le syndic se décrit dans l'Annuaire,
	      sur `SyndicInfo` et `MembreSyndic` — et c'est cette donnée-là qui sert
	      réellement : `utils/destinataires.interlocuteurs_syndic()` s'en sert pour
	      choisir à qui partent les e-mails du cabinet. Deux saisies pour une seule
	      notion, dont une inerte. -->
	<p class="renvoi">
		Le syndic se décrit dans <a href="/espace-cs">Espace CS &rsaquo; Annuaire</a> :
		c'est de là que partent les e-mails au cabinet.
	</p>

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
	.renvoi { font-size: .85rem; color: var(--color-text-muted); margin: 0 0 1.5rem; }
	/*  `.form-section` et `.section-title` vivaient ici : ils REDÉFINISSAIENT la
	    carte et le titre de sous-section que `card` / `config-section-title` et
	    `SectionFormulaire` portent déjà (anatomie v2.94.0). Deux définitions d'un
	    même objet ne sont pas livrables — cet écran était simplement resté hors
	    du lot qui a aligné les huit autres onglets (#501). */
	.form-grid { grid-template-columns: repeat(auto-fill, minmax(min(220px, 100%), 1fr)); }
</style>
