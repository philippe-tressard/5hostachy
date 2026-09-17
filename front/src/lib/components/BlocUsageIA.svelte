<!--
  Un USAGE de l'assistant IA dans l'administration (#984, 17/09/2026) : son
  activation, son modèle, son prompt, son plafond de jetons — et un bouton qui
  vérifie que CE modèle parle vraiment.

  ## Un bloc, N usages

  L'onglet rend ce composant une fois par entrée de `GET /config/llm-usages` :
  ajouter un usage côté API ajoute un bloc ici, sans une ligne d'écran. C'est
  la raison d'être de ce composant — deux blocs écrits à la main auraient
  divergé au premier réglage ajouté (le catalogue des modèles, par exemple).

  ## Ce que le bloc décide, et ce qu'il ne décide pas

  - Il ÉCRIT dans `valeurs` (lié) sous les clés que l'usage lui donne
    (`usage.cles`) : c'est l'onglet qui enregistre, en un seul geste, le commun
    et tous les usages. Un bouton par bloc ferait N enregistrements partiels.
  - Le catalogue des modèles est COMMUN (il dépend de la clé, pas de l'usage) :
    il est chargé par l'onglet et passé ici, chaque bloc y choisit le sien.
  - « Rétablir le prompt d'origine » VIDE la clé : le serveur retombe alors sur
    le prompt du code (`config_llm`), et le champ le montre. Écrire l'origine
    dans le champ reviendrait au même — mais la clé porterait une copie qui
    ne suivrait plus le code.
  - Pliable (`<details>`) : Philippe veut « un bloc pliable par usage, il y en a
    deux, peut-être plus à l'avenir ». Ouvert par défaut quand l'usage est
    actif : ce qu'on a activé, on veut le voir.
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import { config as configApi, type UsageIA } from '$lib/api';

	export let usage: UsageIA;
	/** Toutes les valeurs de configuration, liées : le bloc écrit les siennes. */
	export let valeurs: Record<string, string>;
	/** Le catalogue commun des modèles, chargé par l'onglet. */
	export let catalogue: {
		etat: 'aucun' | 'encours' | 'pret' | 'indisponible';
		motif: string;
		modeles: { id: string; libelle: string }[];
	};
	/** Une clé est-elle enregistrée ? Sans elle, ni catalogue ni test. */
	export let clePosee = false;
	/** Le fournisseur est-il Azure ? (pas de catalogue, un déploiement à nommer) */
	export let azure = false;
	/** Le repère de modèle du fournisseur, pour la saisie libre. */
	export let modeleRepere = '';
	/** L'onglet charge le catalogue ; le bloc ne fait que le demander. */
	export let chargerModeles: () => void;

	$: cles = usage.cles;
	$: actif = valeurs[cles.actif] === '1';
	$: modele = valeurs[cles.modele] ?? '';
	$: prompt = valeurs[cles.prompt] ?? '';
	$: promptOrigine = !prompt.trim();
	$: maxJetons = Number(valeurs[cles.max_jetons]) || usage.max_jetons_defaut;

	//  Le modèle enregistré reste proposé même s'il n'est plus au catalogue :
	//  sinon la liste le remplacerait en silence par son premier élément, et un
	//  simple Enregistrer changerait le modèle sans que personne l'ait demandé.
	$: choixModeles =
		catalogue.etat === 'pret' && modele && !catalogue.modeles.some((m) => m.id === modele)
			? [{ id: modele, libelle: `${modele} (enregistré)` }, ...catalogue.modeles]
			: catalogue.modeles;

	function poser(cle: string, valeur: string) {
		valeurs = { ...valeurs, [cle]: valeur };
	}

	function retablirPrompt() {
		poser(cles.prompt, '');
	}

	let test: { etat: 'aucun' | 'encours' | 'ok' | 'ko'; message: string } = {
		etat: 'aucun',
		message: '',
	};

	async function tester() {
		test = { etat: 'encours', message: '' };
		try {
			const r = await configApi.llmTest(usage.code);
			test = {
				etat: 'ok',
				message: `${r.fournisseur} · ${r.modele} — réponse « ${r.reponse} » en ${r.duree_ms} ms`,
			};
		} catch (e: any) {
			test = { etat: 'ko', message: e?.message ?? 'Le test a échoué' };
		}
	}
</script>

<details class="bloc-usage" open={actif}>
	<summary class="bloc-usage-resume">
		<Icon name="zap" size={16} />
		<span class="bloc-usage-titre">{usage.libelle}</span>
		<span class="badge" class:badge-green={actif} class:badge-gray={!actif}
			>{actif ? 'Activé' : 'Désactivé'}</span
		>
	</summary>
	<p class="aide bloc-usage-description">{usage.description}</p>

	<SectionFormulaire premiere titre="Activation">
		<label class="field case">
			<input
				type="checkbox"
				checked={actif}
				on:change={(e) => poser(cles.actif, e.currentTarget.checked ? '1' : '0')}
			/>
			Activer cet usage
			<span class="aide">
				Désactivé, l’icône ✨ de cet usage n’apparaît nulle part et aucun appel n’est facturé.
				L’activation globale, dans le bloc Commun, coupe tous les usages d’un geste.
			</span>
		</label>
	</SectionFormulaire>

	<SectionFormulaire titre="Modèle">
		<div class="form-grid">
			<label class="field">
				Modèle *
				{#if catalogue.etat === 'pret'}
					<select value={modele} on:change={(e) => poser(cles.modele, e.currentTarget.value)}>
						<option value="">— choisir un modèle —</option>
						{#each choixModeles as m (m.id)}
							<option value={m.id}>{m.libelle}</option>
						{/each}
					</select>
				{:else}
					<input
						type="text"
						value={modele}
						placeholder={modeleRepere}
						on:input={(e) => poser(cles.modele, e.currentTarget.value.trim())}
					/>
				{/if}
				<div class="ligne-modele">
					{#if !azure}
						<button
							class="btn btn-outline btn-sm"
							type="button"
							disabled={catalogue.etat === 'encours' || !clePosee}
							on:click={chargerModeles}
						>
							{catalogue.etat === 'encours' ? 'Lecture…' : 'Voir les modèles disponibles'}
						</button>
					{/if}
				</div>
				<span class="aide">
					{#if catalogue.etat === 'pret'}
						{choixModeles.length} modèle{choixModeles.length > 1 ? 's' : ''} accessible{choixModeles.length >
						1
							? 's'
							: ''} avec cette clé, du plus récent au plus ancien. Chaque usage a SON modèle : un modèle
						plus capable rend un texte plus fidèle, et coûte plus cher par appel.
					{:else if catalogue.etat === 'indisponible'}
						{catalogue.motif} Saisissez l’<strong>identifiant d’API</strong> à la main — pas le nom commercial.
					{:else if !clePosee}
						Enregistrez d’abord une clé dans le bloc Commun : la liste des modèles se lit avec elle.
					{:else}
						L’<strong>identifiant d’API</strong>, pas le nom commercial. Obligatoire : un usage sans
						modèle ne peut pas appeler.
						{azure
							? 'Sur Azure, indiquez le nom de votre déploiement.'
							: 'Le bouton ci-dessus demande au fournisseur ce que votre clé peut appeler.'}
					{/if}
				</span>
			</label>
			<label class="field">
				Longueur maximale de la réponse
				<input
					type="number"
					value={maxJetons}
					min="200"
					max="32000"
					step="500"
					on:input={(e) => poser(cles.max_jetons, e.currentTarget.value)}
				/>
				<span class="aide">
					En jetons, et c’est un plafond de <strong>coût</strong> autant que de longueur : seuls les
					jetons réellement produits sont facturés. Un modèle récent raisonne avant d’écrire, et ce
					raisonnement compte dans le plafond — une réponse coupée vient de ce champ, pas du modèle.
					Valeur d’origine : {usage.max_jetons_defaut.toLocaleString()}.
				</span>
			</label>
		</div>
	</SectionFormulaire>

	<SectionFormulaire titre="Prompt">
		<div class="field champ-large">
			<label for="prompt-{usage.code}">Consigne donnée au modèle</label>
			<textarea
				id="prompt-{usage.code}"
				rows="14"
				value={promptOrigine ? usage.prompt_defaut : prompt}
				on:input={(e) => poser(cles.prompt, e.currentTarget.value)}></textarea>
			<div class="ligne-modele">
				<button
					class="btn btn-outline btn-sm"
					type="button"
					disabled={promptOrigine}
					on:click={retablirPrompt}
				>
					Rétablir le prompt d’origine
				</button>
				{#if promptOrigine}
					<span class="badge badge-gray">Prompt d’origine</span>
				{:else}
					<span class="badge badge-orange">Prompt modifié</span>
				{/if}
			</div>
			<span class="aide">
				C’est le contexte que reçoit le modèle avant le texte à traiter : le ton, les interdits, la
				structure attendue. Vous pouvez y ajouter des consignes ou modifier le gabarit. La matière —
				la fiche, les documents, la description saisie — est ajoutée par l’application, et le <strong
					>format de réponse</strong
				> que l’application sait relire est imposé par elle : un prompt réécrit ne peut pas le casser.
			</span>
		</div>
	</SectionFormulaire>

	<SectionFormulaire titre="Vérification">
		<p class="aide" style="margin-bottom:.6rem">
			Ce test pose une vraie question au modèle de <strong>cet usage</strong> et attend sa réponse.
			⚠️ Il porte sur la configuration <strong>enregistrée</strong> : cliquez d’abord sur « Enregistrer
			» si vous venez de modifier un champ. L’usage n’a pas besoin d’être activé.
		</p>
		<div class="ligne-test">
			<button
				class="btn btn-outline"
				type="button"
				on:click={tester}
				disabled={test.etat === 'encours' || !clePosee}
			>
				{test.etat === 'encours' ? 'Test en cours…' : '🔌 Tester la connexion'}
			</button>
			{#if test.etat === 'ok'}
				<span class="verdict ok">✅ {test.message}</span>
			{:else if test.etat === 'ko'}
				<span class="verdict ko">⚠️ {test.message}</span>
			{/if}
		</div>
	</SectionFormulaire>
</details>

<style>
	/*  Le bloc pliable d'un usage : un cadre dans la carte de l'onglet, jamais une
	    seconde carte — deux bordures pleines pour un seul objet est le défaut
	    de #425. */
	.bloc-usage {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.6rem 0.9rem;
		margin-top: 0.9rem;
	}
	.bloc-usage-resume {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
		font-weight: 700;
		list-style: none;
	}
	.bloc-usage-resume::-webkit-details-marker {
		display: none;
	}
	.bloc-usage-resume::before {
		content: '›';
		display: inline-block;
		transition: transform 0.15s;
		color: var(--color-text-muted);
	}
	.bloc-usage[open] > .bloc-usage-resume::before {
		transform: rotate(90deg);
	}
	.bloc-usage-titre {
		flex: 1;
	}
	.bloc-usage-description {
		margin: 0.5rem 0 0.9rem;
	}
	/*  La rangée qui porte un bouton sous son champ. Un `<div>` plutôt qu'un
	    frère du `<label>` : le bouton appartient au champ. */
	.ligne-modele {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		margin-top: 0.35rem;
	}
	.ligne-test {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}
	.verdict {
		font-size: 0.88rem;
	}
	.verdict.ok {
		color: var(--color-success);
	}
	.verdict.ko {
		color: var(--color-danger);
	}
</style>
