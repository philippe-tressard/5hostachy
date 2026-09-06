<!--
  **L'inventaire d'un bail** — ce qui a été remis au locataire, et les gestes
  qui le tiennent à jour.

  ## 🔴 Pourquoi ce composant (#806, 06/09/2026)

  Le tableau existait dans `mon-lot`, avec deux gestes : marquer un objet rendu,
  et le supprimer. Il manquait celui **par lequel tout commence** — enregistrer
  un objet.

  Et le constat était plus large que le ticket ne le disait : `BailCreateMulti`
  ne porte **aucun objet**. `POST /bailleur/baux/{id}/objets` était donc la seule
  façon d'en enregistrer un, et aucun écran ne l'appelait. Autrement dit,
  l'inventaire d'un bail créé depuis l'interface affichait **toujours** « Aucun
  objet enregistré », et les deux boutons présents portaient sur des lignes qui
  ne pouvaient pas exister.

  C'est le cas exact de `sondages.modifier` (#783) : chemin serveur complet,
  testé, déployé, et inatteignable — sauf qu'ici il manquait le geste de
  création, pas seulement celui de correction.

  ## Créer et corriger emploient LE MÊME formulaire

  `ux-patterns` §14 bis : la boîte dans la page, pour les deux gestes, par
  `CadreFormulaire`. Ce qui le rend possible sans divergence, c'est
  l'enrichissement de `ObjetUpdate` côté serveur — `type` et `remis_le` y ont été
  ajoutés le même jour. Un schéma plus pauvre que son jumeau force l'écran à
  diverger, et la divergence devient une dette à déclarer (motif `api`, R4) :
  autant ne pas la créer.

  ⚠️ Ce qui reste hors du formulaire : **le statut et la date de retour**. Un
  retour se prononce par son propre geste (`↩`), qui pose les deux ensemble. Les
  ouvrir ici donnerait deux chemins vers le même fait, dont un capable d'écrire
  « rendu » sans date.

  ## Ce que ce composant emporte, et pourquoi il parle à l'API

  Les objets sont une sous-entité **entièrement contenue** dans le bail : le
  parent n'a rien à en savoir sinon que la liste a changé (`on:change`). Y
  laisser les appels aurait dispersé quatre gestes sur deux fichiers, dont un de
  1 600 lignes — c'est le contraire de ce que l'extraction cherche.

  ⚠️ Les trois tables de libellés (`typeLabel`, `statutObjetBadge`,
  `statutObjetLabel`) partent AVEC le balisage qui les emploie : les laisser
  derrière aurait produit un tableau nu, le défaut de `standards/02` §4 ter.

  ## 🔴 Ce fichier n'est PAS mesuré par `lint:css-orphelin` (#810)

  Il porte `class="badge {statutObjetBadge[objet.statut] ?? …}"`. Devant une
  classe interpolée, Svelte ne peut pas résoudre ce qui sera rendu : il cesse de
  déclarer des sélecteurs inutilisés **pour tout le fichier**.

  C'est en sortant ce tableau de `mon-lot` que dix sélecteurs morts depuis
  longtemps y sont apparus d'un coup — l'écran entier était aveuglé par cette
  seule ligne. Le contrôle annonce désormais sa portée réelle (142/172 fichiers),
  et la dette est suivie en #810.

  ⚠️ L'interpolation n'est pas fautive pour autant : c'est la table qui est la
  source unique du couple statut → badge. L'éclater en cinq `class:` recréerait
  la duplication que la table supprime. Le sujet est le CONTRÔLE, pas ce code.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { bailleur as bailApi, ApiError, type ObjetRemis } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { fmtDate } from '$lib/date';
	import CadreFormulaire from '$lib/components/CadreFormulaire.svelte';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import Modale from '$lib/components/Modale.svelte';

	/** Le bail dont on tient l'inventaire. */
	export let bailId: number;
	export let objets: ObjetRemis[] = [];
	/**  Faux sur un bail terminé : l'inventaire se lit encore, il ne se modifie
	 *   plus. C'est la condition qui gouvernait déjà la colonne d'actions. */
	export let modifiable = true;

	const dispatch = createEventDispatcher<{ change: ObjetRemis[] }>();

	//  Les quatre types — une liste de 4, donc des pastilles (`ux-patterns`, seuil
	//  des listes courtes). `ChoixPastilles` la rend, plutôt qu'un `<select>` nu.
	const TYPES = [
		{ val: 'cle', label: '\u{1F511} Clé' },
		{ val: 'telecommande', label: '\u{1F4E1} Télécommande' },
		{ val: 'vigik', label: '\u{1F3F7}\u{FE0F} Vigik' },
		{ val: 'autre', label: '\u{1F4E6} Autre' },
	] as const;

	const typeLabel: Record<string, string> = Object.fromEntries(TYPES.map((t) => [t.val, t.label]));

	const statutObjetBadge: Record<string, string> = {
		en_possession: 'badge-green',
		rendu: 'badge-blue',
		perdu: 'badge-red',
		non_remis: 'badge-gray',
	};

	const statutObjetLabel: Record<string, string> = {
		en_possession: 'En possession',
		rendu: 'Rendu',
		perdu: 'Perdu',
		non_remis: 'Non remis',
	};

	//  ── La saisie ────────────────────────────────────────────────────────────
	//  `null` = fermée · `{id: null}` = création · `{id: n}` = correction. Un seul
	//  état pour les deux gestes : c'est ce que dit `ux-patterns` §14 bis, et
	//  c'est ce qui empêche d'ouvrir les deux à la fois.
	let saisie: { id: number | null } | null = null;
	let enregistrement = false;

	let fType = 'cle';
	let fLibelle = '';
	let fQuantite = 1;
	let fReference = '';
	let fRemisLe = '';
	let fNotes = '';

	function ouvrirCreation() {
		saisie = { id: null };
		fType = 'cle';
		fLibelle = '';
		fQuantite = 1;
		fReference = '';
		fRemisLe = '';
		fNotes = '';
	}

	function ouvrirCorrection(o: ObjetRemis) {
		//  Un second clic sur la même ligne referme — même geste que les cartes
		//  d'annonce et d'idée.
		if (saisie?.id === o.id) {
			saisie = null;
			return;
		}
		saisie = { id: o.id };
		fType = o.type;
		fLibelle = o.libelle;
		fQuantite = o.quantite;
		fReference = o.reference ?? '';
		fRemisLe = o.remis_le ?? '';
		fNotes = o.notes ?? '';
	}

	async function enregistrer() {
		if (!saisie) return;
		enregistrement = true;
		//  ⚠️ Les champs vides partent en `null`, jamais en chaîne vide : le
		//  serveur distingue « pas de référence » de « référence égale à rien », et
		//  c'est `null` qui s'affiche « — » à la relecture.
		const corps = {
			type: fType,
			libelle: fLibelle.trim(),
			quantite: fQuantite,
			reference: fReference.trim() || null,
			remis_le: fRemisLe || null,
			notes: fNotes.trim() || null,
		};
		try {
			if (saisie.id === null) {
				const cree = await bailApi.ajouterObjet(bailId, corps);
				objets = [...objets, cree];
				toast('success', 'Objet ajouté à l’inventaire.');
			} else {
				const maj = await bailApi.updateObjet(bailId, saisie.id, corps);
				objets = objets.map((o) => (o.id === maj.id ? maj : o));
				toast('success', 'Objet corrigé.');
			}
			saisie = null;
			dispatch('change', objets);
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Enregistrement impossible');
		} finally {
			enregistrement = false;
		}
	}

	//  ── Le retour ────────────────────────────────────────────────────────────
	//  ⚠️ Il reste en MODALE, contrairement au formulaire ci-dessus. Ce n'est pas
	//  un oubli : `mon-lot` porte quatre modales (terminer un bail, gérer les
	//  accès…), et n'en convertir qu'une donnerait deux paradigmes dans le même
	//  écran — exactement ce que #367 a supprimé pour la création. Leur conversion
	//  est un lot à part, comme celle de `prestataires` déjà déclarée dans
	//  `lint:formulaires`.
	let objetRetour: ObjetRemis | null = null;
	let retourDate = '';
	let retourPerdu = false;

	async function confirmerRetour() {
		if (!objetRetour) return;
		try {
			const maj = await bailApi.retourObjet(objetRetour.bail_id, objetRetour.id, {
				rendu_le: retourDate || null,
				perdu: retourPerdu,
			});
			objets = objets.map((o) => (o.id === maj.id ? maj : o));
			objetRetour = null;
			toast('success', retourPerdu ? 'Objet marqué perdu' : 'Retour enregistré');
			dispatch('change', objets);
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	async function supprimer(o: ObjetRemis) {
		if (!confirm(`Supprimer "${o.libelle}" ?`)) return;
		try {
			await bailApi.supprimerObjet(bailId, o.id);
			objets = objets.filter((x) => x.id !== o.id);
			if (saisie?.id === o.id) saisie = null;
			toast('success', 'Objet supprimé');
			dispatch('change', objets);
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}
</script>

<div>
	<div class="inv-entete">
		<div class="inv-titre">
			Inventaire ({objets.length} objet{objets.length !== 1 ? 's' : ''})
		</div>
		{#if modifiable}
			<button
				type="button"
				class="btn btn-primary btn-xs"
				on:click={() => (saisie && saisie.id === null ? (saisie = null) : ouvrirCreation())}
			>
				{saisie && saisie.id === null ? '✕ Annuler' : '+ Ajouter un objet'}
			</button>
		{/if}
	</div>

	<!--  La boîte de saisie, une seule pour les deux gestes — et posée AVANT le
	      tableau : le formulaire d'une ligne qu'on corrige doit rester visible
	      quand le tableau est long (#787, « c'est tout en bas, et on ne voit
	      pas »). -->
	{#if saisie}
		{#key saisie.id}
			<CadreFormulaire
				encadre={false}
				titre={saisie.id === null ? 'Nouvel objet remis' : 'Corriger l’objet'}
				cle={saisie.id}
				on:fermer={() => (saisie = null)}
			>
				<form class="largeur-saisie" on:submit|preventDefault={enregistrer}>
					<ChoixPastilles
						options={TYPES}
						bind:valeur={fType}
						tous={false}
						libelle="Type d’objet"
						libelleVisible
						requis
					/>

					<div class="form-grid">
						<label class="field champ-large">
							Libellé *
							<input type="text" bind:value={fLibelle} required maxlength="120" />
						</label>
						<label class="field">
							Quantité
							<input type="number" bind:value={fQuantite} min="1" max="99" />
						</label>
						<label class="field">
							Référence
							<input type="text" bind:value={fReference} maxlength="60" />
						</label>
						<label class="field">
							Remis le
							<input type="date" bind:value={fRemisLe} />
						</label>
						<label class="field champ-large">
							Notes
							<textarea bind:value={fNotes} rows="2" maxlength="500"></textarea>
						</label>
					</div>

					<div class="form-actions">
						<button type="button" class="btn" on:click={() => (saisie = null)}>Annuler</button>
						<button type="submit" class="btn btn-primary" disabled={enregistrement}>
							{enregistrement ? 'Enregistrement…' : 'Enregistrer'}
						</button>
					</div>
				</form>
			</CadreFormulaire>
		{/key}
	{/if}

	{#if objets.length === 0}
		<p class="inv-vide">
			Aucun objet enregistré.
			{#if modifiable}
				Ajoutez les clés, badges et télécommandes remis au locataire : c’est cet inventaire qui fera
				foi à la sortie.
			{/if}
		</p>
	{:else}
		<div class="table-wrap">
			<table class="table" style="font-size:0.85rem">
				<thead>
					<tr>
						<th>Type</th>
						<th>Libellé</th>
						<th>Qté</th>
						<th>Référence</th>
						<th>Statut</th>
						<th>Remis le</th>
						<th>Rendu le</th>
						{#if modifiable}<th></th>{/if}
					</tr>
				</thead>
				<tbody>
					{#each objets as objet (objet.id)}
						<tr>
							<td>{typeLabel[objet.type] ?? objet.type}</td>
							<td>{objet.libelle}</td>
							<td style="text-align:center">{objet.quantite}</td>
							<td>{objet.reference ?? '—'}</td>
							<td>
								<span class="badge {statutObjetBadge[objet.statut] ?? 'badge-gray'}">
									{statutObjetLabel[objet.statut] ?? objet.statut}
								</span>
							</td>
							<td>{fmtDate(objet.remis_le)}</td>
							<td>{fmtDate(objet.rendu_le)}</td>
							{#if modifiable}
								<td>
									<!--  Ordre des actions : ✏️ puis 🗑️, le retour venant en tête
									      parce qu'il est le geste propre à cette ligne
									      (`ux-patterns` §3 pour l'ordre général). -->
									<div class="inv-actions">
										{#if objet.statut === 'en_possession'}
											<button
												type="button"
												class="btn btn-xs"
												title="Enregistrer retour / perte"
												aria-label="Enregistrer le retour de {objet.libelle}"
												on:click={() => {
													objetRetour = objet;
													retourDate = '';
													retourPerdu = false;
												}}>↩</button
											>
										{/if}
										<button
											type="button"
											class="btn btn-xs"
											title="Corriger"
											aria-label="Corriger {objet.libelle}"
											aria-pressed={saisie?.id === objet.id}
											on:click={() => ouvrirCorrection(objet)}>&#x270F;&#xFE0F;</button
										>
										<button
											type="button"
											class="btn btn-xs btn-danger"
											title="Supprimer"
											aria-label="Supprimer {objet.libelle}"
											on:click={() => supprimer(objet)}>✕</button
										>
									</div>
								</td>
							{/if}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

{#if objetRetour}
	<Modale
		edition
		titre={`Retour — ${objetRetour.libelle}`}
		styleBoite="width:min(380px,95vw)"
		on:fermer={() => (objetRetour = null)}
	>
		<div class="modal-body">
			<div class="field">
				<label for="ro-date">Date de retour</label>
				<input id="ro-date" type="date" bind:value={retourDate} />
			</div>
			<label class="inv-case">
				<input type="checkbox" bind:checked={retourPerdu} />
				Marquer comme perdu
			</label>
		</div>
		<div class="modal-footer">
			<button class="btn" on:click={() => (objetRetour = null)}>Annuler</button>
			<button class="btn {retourPerdu ? 'btn-danger' : 'btn-primary'}" on:click={confirmerRetour}>
				{retourPerdu ? 'Perdu' : 'Retour confirmé'}
			</button>
		</div>
	</Modale>
{/if}

<style>
	.inv-entete {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-bottom: 0.5rem;
	}
	.inv-titre {
		font-weight: 600;
		font-size: 0.9rem;
	}
	.inv-vide {
		font-size: 0.83rem;
		color: var(--color-text-muted);
	}
	.inv-actions {
		display: flex;
		gap: 0.35rem;
	}
	/*  ⚠️ Qualifié, jamais `input` nu : un sélecteur d'élément dans un composant
	    atteint toutes les cases de la page hôte (`ux-patterns` §9 octies, et
	    `npm run lint:styles` le refuse). */
	.inv-case {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.9rem;
	}
</style>
