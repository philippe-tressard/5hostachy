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
<script lang="ts">
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';

	export let prestForm: any;
	export let prestContacts: any[] = [];
	export let typesPrestataire: readonly { val: string; label: string; desc?: string }[] = [];
	export let equipements: readonly { val: string; label: string }[] = [];
</script>

<div>
	<div class="form-grid">
		<label class="field">Nom *<input bind:value={prestForm.nom} required /></label>
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
	<div style="margin-top:.75rem">
		<div style="font-size:.85rem;font-weight:600;margin-bottom:.35rem">
			Contact{prestContacts.length > 1 ? 's' : ''}
		</div>
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
</div>

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
