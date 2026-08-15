<!--
  Formulaire de création d'une publication (conseil syndical).

  Extrait de `actualites/+page.svelte` (#356) : la page dépassait le plafond de
  500 lignes. Ce bloc y est le plus autonome — une dizaine de champs, leur état,
  et un seul appel de création. Rien de cet état n'était lu ailleurs dans la page.

  ⚠️ Ce formulaire n'est PAS celui d'édition, qui vit toujours dans la page. Ils
  se ressemblent (titre, contenu, état, options) mais l'édition ne touche ni au
  périmètre, ni aux destinataires, ni aux pièces jointes. Les fusionner supposerait
  de trancher ce que « modifier une publication » doit permettre — c'est une
  question de produit, pas de refactorisation, et elle n'est pas tranchée.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import OptionsPublication from '$lib/components/OptionsPublication.svelte';
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import PerimetrePicker from '$lib/components/PerimetrePicker.svelte';
	import DestinatairePicker from '$lib/components/DestinatairePicker.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { publications as pubsApi, documents as docsApi, ApiError, type Publication } from '$lib/api';
	import { perimetreDefautListe } from '$lib/utils';
	import { richEmpty } from '$lib/publications';

	const dispatch = createEventDispatcher<{ cree: Publication }>();

	let titre = '';
	let contenu = '';
	let urgente = false;
	let epingle = false;
	let brouillon = false;
	let partagerWhatsapp = false;
	let envoyerSyndic = false;
	let envoyerCs = false;
	let annonceHall = false;
	let confidentiel = false;
	let statut = 'publie';
	let saving = false;
	//  Les photos sont téléversées AVANT la création (endpoint générique), comme
	//  pour les tickets et les événements : leurs URLs partent dans la charge utile.
	//  C'est ce qui supprime la danse « créer en brouillon → téléverser → publier »
	//  qui n'existait que parce que l'image arrivait après coup.
	let photos: string[] = [];
	let pendingFiles: File[] = [];
	let fileInputKey = 0;
	let perimetreCible: string[] = perimetreDefautListe();
	let publicCible: string[] = ['résidents'];

	function handleFilesChange(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		pendingFiles = input.files ? Array.from(input.files) : [];
	}

	function reinitialiser() {
		titre = ''; contenu = ''; urgente = false; epingle = false;
		brouillon = false; statut = 'publie'; partagerWhatsapp = false; envoyerSyndic = false;
		envoyerCs = false; annonceHall = false; confidentiel = false;
		perimetreCible = perimetreDefautListe();
		photos = [];
		pendingFiles = []; fileInputKey++;
	}

	async function publish() {
		if (!titre.trim() || richEmpty(contenu)) return;
		saving = true;
		try {
			//  Les photos partent avec la création : plus rien à retarder pour elles.
			//  Restent les DOCUMENTS, encore persistés en entités `Document` propres
			//  aux publications (les tickets et les événements utilisent
			//  `fichiers_urls`) — eux seuls imposent encore de publier après coup,
			//  pour que l'affiche de hall les voie. Divergence connue, à traiter.
			const publierApresDocuments = !brouillon && annonceHall && pendingFiles.length > 0;
			let pub = await pubsApi.create({
				titre, contenu, urgente, epingle,
				perimetre_cible: perimetreCible, public_cible: publicCible,
				brouillon: publierApresDocuments ? true : brouillon,
				photos_urls: photos,
				statut: statut || 'publie',
				partager_whatsapp: partagerWhatsapp,
				envoyer_syndic: envoyerSyndic,
				envoyer_cs: envoyerCs,
				annonce_hall: annonceHall,
				confidentiel,
			});
			if (pendingFiles.length > 0) {
				for (const f of pendingFiles) {
					try { await docsApi.uploadForPublication(f.name, pub.id, f); } catch { /* ignoré */ }
				}
			}
			if (publierApresDocuments) {
				pub = await pubsApi.update(pub.id, { brouillon: false });
			}
			toast('success', pub.brouillon ? 'Brouillon enregistré' : 'Publication créée');
			reinitialiser();
			dispatch('cree', pub);
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { saving = false; }
	}
</script>

<div class="card largeur-saisie" style="margin-bottom:1.5rem">
	<h2 style="font-size:1rem;font-weight:600;margin-bottom:1rem">Nouvelle publication</h2>
	<form on:submit|preventDefault={publish}>
		<div class="field">
			<label for="new-titre">Titre *</label>
			<input id="new-titre" type="text" bind:value={titre} required maxlength="200" />
		</div>
		<div class="field">
			<label id="perimetre-label">Périmètre *</label>
			<PerimetrePicker bind:value={perimetreCible} />
		</div>
		<div class="field">
			<label>Destinataires *</label>
			<DestinatairePicker bind:value={publicCible} />
		</div>
		<div class="field">
			<label for="actualite-contenu">Contenu *</label>
			<RichEditor id="actualite-contenu" bind:value={contenu} placeholder="Contenu de l'actualité…" minHeight="120px" />
		</div>
		<div class="field">
			<label for="actualite-photos">Photos</label>
			<FichiersUpload id="actualite-photos" bind:urls={photos} max={6} mode="photos" />
		</div>
		<div class="field">
			<label>Documents</label>
			{#key fileInputKey}
				<input type="file" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.zip,.txt" on:change={handleFilesChange} style="font-size:.85rem" />
			{/key}
			{#if pendingFiles.length > 0}
				<span style="font-size:.8rem;color:var(--color-text-muted)">📎 {pendingFiles.length} fichier{pendingFiles.length > 1 ? 's' : ''} sélectionné{pendingFiles.length > 1 ? 's' : ''}</span>
			{/if}
		</div>
		<div class="field">
			<label for="new-statut">État</label>
			<select id="new-statut" bind:value={statut}>
				<option value="publie">&#x1F535; Publié</option>
				<option value="en_cours">&#x1F7E1; En cours</option>
				<option value="resolu">&#x1F7E2; Résolu</option>
				<option value="annule">⚫ Annulé</option>
			</select>
		</div>
		<OptionsPublication
			complet
			{perimetreCible}
			bind:epingle
			bind:urgente
			bind:brouillon
			bind:confidentiel
			bind:whatsapp={partagerWhatsapp}
			bind:syndic={envoyerSyndic}
			bind:cs={envoyerCs}
			bind:annonceHall
		/>
		<div class="form-actions">
			<button type="submit" class="btn btn-primary" disabled={saving}>
				{saving ? 'Envoi…' : (brouillon ? 'Enregistrer brouillon' : 'Publier')}
			</button>
		</div>
	</form>
</div>
