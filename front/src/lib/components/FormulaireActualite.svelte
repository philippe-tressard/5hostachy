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
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import OptionsPublication from '$lib/components/OptionsPublication.svelte';
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
	//  Les DOCUMENTS restent différés : ils deviennent des entités `Document`
	//  rattachées à `publication_id`, qui n'existe pas tant que l'actualité n'est
	//  pas créée. `FichiersUpload` les retient en mode `differe` — même apparence
	//  que partout ailleurs, là où un `<input type="file">` nu était le seul du
	//  site à ne ressembler à rien (signalé le 16/08/2026).
	let pendingFiles: File[] = [];
	let perimetreCible: string[] = perimetreDefautListe();
	let publicCible: string[] = ['résidents'];

	function reinitialiser() {
		titre = ''; contenu = ''; urgente = false; epingle = false;
		brouillon = false; statut = 'publie'; partagerWhatsapp = false; envoyerSyndic = false;
		envoyerCs = false; annonceHall = false; confidentiel = false;
		perimetreCible = perimetreDefautListe();
		publicCible = ['résidents'];
		photos = [];
		pendingFiles = [];
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

<FormulaireCreation titre="Nouvelle publication">
	<form on:submit|preventDefault={publish}>
		<!--  1. Titre. Une actualité n'a NI champ spécifique NI workflow : elle n'a
		      pas d'étapes de vie, et son Publié/Brouillon est une décision de
		      diffusion — il est donc en section 9, pas en 3. -->
		<SectionFormulaire premiere>
			<div class="field champ-large">
				<label for="new-titre">Titre *</label>
				<input id="new-titre" type="text" bind:value={titre} required maxlength="200" />
			</div>
		</SectionFormulaire>

		<!--  4 à 9 : l'ordre, les intitulés et les séparations viennent du
		      composant partagé — voir `ChampsCommuns.svelte`. -->
		<ChampsCommuns
			idPrefixe="actualite"
			avecPerimetre bind:perimetre={perimetreCible}
			avecDestinataires bind:destinataires={publicCible}
			avecDescription descriptionRequise bind:description={contenu}
			descriptionPlaceholder="Contenu de l'actualité…"
			avecPhotos bind:photos
			avecDocuments documentsDifferes bind:documentsFichiers={pendingFiles}
			avecDiffusion
			avecCanaux={false}
		>
			<!--  Les actualités rendent leurs canaux elles-mêmes : `OptionsPublication`
			      porte en plus le confidentiel et l'affiche de hall, et les deux
			      règles qui les lient. -->
			<svelte:fragment slot="diffusion">
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
			</svelte:fragment>
		</ChampsCommuns>

		<div class="form-actions">
			<button type="submit" class="btn btn-primary" disabled={saving}>
				{saving ? 'Envoi…' : (brouillon ? 'Enregistrer brouillon' : 'Publier')}
			</button>
		</div>
	</form>
</FormulaireCreation>
