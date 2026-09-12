<!--
  Les CHAMPS d'un prestataire — nom, type, spécialité, contacts.

  Extraits de `prestataires/+page.svelte` le 11/09/2026, pour la même raison que
  `ChampsContrat` avant eux : le formulaire doit pouvoir s'ouvrir à DEUX endroits
  — en tête de page pour une création, dans la carte pour une correction — et un
  bloc de champs recopié aux deux endroits aurait divergé au premier ajout.

  🔴 Il ne porte ni `<form>`, ni pied de formulaire, ni titre : ce sont des
  décisions de l'appelant, qui seul sait s'il crée ou s'il corrige. Les y mettre
  ferait de ce composant un écran, et il n'en est pas un.
-->
<script context="module" lang="ts">
	//  Partagé par toutes les instances : c'est ce qui rend les identifiants
	//  uniques d'un rendu à l'autre.
	let compteur = 0;
</script>

<script lang="ts">
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import { PRESTATAIRE } from '$lib/entites/prestataire';
	import { sectionPresente, type Etat } from '$lib/entites/types';

	export let prestForm: any;
	export let prestContacts: any[] = [];
	export let typesPrestataire: readonly { val: string; label: string; desc?: string }[] = [];
	export let equipements: readonly { val: string; label: string }[] = [];

	//  Un identifiant par instance : les deux rendus — création en tête de page et
	//  correction dans la carte — coexistent, et deux `id` identiques feraient
	//  pointer les deux libellés sur le premier champ.
	const idNom = `prest-nom-${++compteur}`;

	/**  Création ou correction. Les deux rendent les mêmes sections ici — et c'est
	 *   la DÉCLARATION qui le dit, pas une absence de condition : un prestataire
	 *   n'a ni workflow ni diffusion, donc rien qui varie d'un état à l'autre. */
	export let etat: Etat = 'creation';
</script>

<!--  ══ 1. TITRE ══ Le nom SEUL : ce qui qualifie l'objet est en section 2
      (§0, arbitré le 18/08/2026). Il partageait la grille avec le type et la
      spécialité — quatre champs d'un bloc, sans rien pour dire lequel nomme
      l'entreprise et lesquels la décrivent. -->
<!--  ══ 1. NOM ══ La section n'a pas de titre : le champ porte le sien, comme
      sur les dix autres écrans (12/09/2026). Voir `ChampsContrat`. -->
<SectionFormulaire premiere>
	<div class="field champ-large">
		<label for={idNom}>Nom *</label>
		<input id={idNom} bind:value={prestForm.nom} required />
	</div>
</SectionFormulaire>

<!--  ══ 2. CHAMPS SPÉCIFIQUES ══ Ce qui décrit l'entreprise. -->
{#if sectionPresente(PRESTATAIRE, etat, 'specifiques')}
	<SectionFormulaire titre="L'entreprise">
		<div class="form-grid">
			<!--  🔴 Six entrées portant chacune une description : c'est le cas
					      qui a fait donner un sous-texte à `Pastille` (#491, seuil arbitré
					      à 6). Le FILTRE de cette même liste la montre depuis le 29/08 —
					      le formulaire, lui, gardait un `<select>` où la description ne
					      s'affichait nulle part. Deux rendus du même objet, et c'est
					      celui qui sert à CHOISIR qui perdait ce qui aide à choisir.
					      `champ-large` : dix pastilles à sous-texte dans une colonne de
					      grille s'empileraient une par ligne (`ux-patterns` §9 bis). -->
			<ChoixPastilles
				options={typesPrestataire}
				bind:valeur={prestForm.type_prestataire}
				tous={false}
				libelle="Type"
				libelleVisible
				requis
				avecDetail
			/>
			<label class="field"
				>Spécialité *
				<select bind:value={prestForm.specialite} required>
					<option value="">— Sélectionner —</option>
					{#each equipements as e (e.val)}<option value={e.val}>{e.label}</option>{/each}
				</select>
			</label>
			<label class="field">Email<input type="email" bind:value={prestForm.email} /></label>
		</div>
	</SectionFormulaire>
{/if}

<!--  Les CONTACTS : une section à part, parce que c'est une liste répétable et
      non un champ de plus. Elle n'est pas au cadre des neuf — un prestataire est
      un carnet d'adresses, et ses personnes SONT son contenu.

      ⚠️ Son intitulé passait par un `<div>` habillé en ligne
      (`font-size:.85rem;font-weight:600`) : la troisième écriture d'un titre de
      section, celle que `SectionFormulaire` existe pour supprimer. -->
<SectionFormulaire titre={prestContacts.length > 1 ? 'Contacts' : 'Contact'}>
	<div>
		{#each prestContacts as _contact, i (_contact)}
			<div
				style="border:1px solid var(--color-border);border-radius:6px;padding:.6rem;margin-bottom:.5rem;background:var(--color-bg)"
			>
				<div style="display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.35rem">
					<input
						style="flex:2;min-width:140px"
						bind:value={prestContacts[i].telephone}
						placeholder="Téléphone *"
					/>
					<input
						style="flex:1;min-width:100px"
						bind:value={prestContacts[i].prenom}
						placeholder="Prénom"
					/>
					<input
						style="flex:1;min-width:100px"
						bind:value={prestContacts[i].nom}
						placeholder="Nom"
					/>
				</div>
				<div style="display:flex;gap:.4rem;flex-wrap:wrap;align-items:center">
					<input
						style="flex:1;min-width:120px"
						bind:value={prestContacts[i].fonction}
						placeholder="Fonction"
					/>
					<input
						style="flex:1;min-width:140px"
						type="email"
						bind:value={prestContacts[i].email}
						placeholder="Email"
					/>
					{#if prestContacts.length > 1}
						<button
							type="button"
							class="btn btn-sm btn-outline"
							style="color:#dc2626;border-color:#dc2626;flex-shrink:0"
							on:click={() => (prestContacts = prestContacts.filter((_, j) => j !== i))}>−</button
						>
					{/if}
				</div>
			</div>
		{/each}
		<button
			type="button"
			class="btn btn-sm btn-outline"
			on:click={() =>
				(prestContacts = [
					...prestContacts,
					{ telephone: '', prenom: '', nom: '', fonction: '', email: '' },
				])}>+ Nouveau contact</button
		>
	</div>
</SectionFormulaire>

<style>
	/*  Une grille plus SERRÉE que la norme — 180 px de colonne minimale au lieu de
	    la valeur globale, et un gap de .65rem. Elle vivait dans
	    `prestataires/+page.svelte`, où elle s'appliquait à TOUS les `.form-grid`
	    de la page ; l'extraction du 11/09/2026 l'a laissée derrière son balisage,
	    et `lint:css-orphelin` l'a vue.

	    ⚠️ Elle est recopiée ici ET dans `OngletConsommations` — non par négligence :
	    Svelte scope au fichier, un `:global()` depuis l'un contaminerait tout le
	    site (#562). La remonter dans `styles/champs.css` changerait la grille de
	    TOUS les formulaires du produit, ce qui est une décision d'interface à
	    prendre devant l'écran, pas un effet de bord d'une extraction.

	    ⚠️ Elle ne part PAS dans `OngletConsommations`, qui l'héritait pourtant de
	    la même page : ses trois champs tiennent dans la grille de la charte, et la
	    recopier là-bas aurait dupliqué une règle pour entériner un héritage
	    accidentel — une variante qui n'apporte rien (`standards/02` §4 bis).
	    Seuls la répartition et l'espacement : la peau des contrôles est partie le
	    28/08/2026 — le pourquoi vit dans `check-styles-nus.mjs`, volet C. */
	.form-grid {
		grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr));
		gap: 0.65rem;
	}
</style>
