<!--
  L'onglet **Assistant IA** de l'administration : quel service, quelle clé, quel
  modèle — et un bouton qui vérifie que ça parle vraiment.

  Même geste et même forme qu'`OngletSmtp` : l'état et les appels réseau vivent
  ici, la page ne garde que le choix de l'onglet. Le champ secret passe par
  `ChampSecret`, extrait le même jour des deux écrans qui le portaient déjà.

  ## 🔴 La clé ne revient JAMAIS du serveur

  `llm_api_key` est déclarée dans `routers/config._SECRETS` : l'API rend un
  marqueur, jamais la valeur. L'écran sait seulement qu'une clé existe — et
  n'envoie la sienne que si elle est **non vide**, sinon un enregistrement
  ordinaire effacerait la clé posée.

  ## Ce que l'écran ne décide pas

  Ni la liste des fournisseurs, ni les modèles par défaut, ni les limites : tout
  cela vit dans `api/app/utils/llm.py`. Recopier la table ici la ferait diverger
  au premier fournisseur ajouté — c'est le défaut que ce dépôt connaît le mieux.
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { config as configApi } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChampSecret from '$lib/components/ChampSecret.svelte';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';

	/** Valeurs lues au chargement par la page (`adminCfg`). */
	export let valeurs: Record<string, string> = {};

	//  ⚠️ Trois entrées : le seuil des listes courtes (≤ 6) impose des pastilles,
	//  pas un `<select>` (`ux-patterns`, `lint:seuil-listes`).
	const FOURNISSEURS = [
		{ val: 'openai', label: 'OpenAI', desc: 'api.openai.com — GPT' },
		{ val: 'anthropic', label: 'Claude', desc: 'api.anthropic.com — Anthropic' },
		{ val: 'azure_openai', label: 'Azure OpenAI', desc: 'votre point d’accès Azure' },
	];

	/** Modèles proposés en repère — le champ reste libre, le catalogue bouge vite. */
	const MODELES_REPERE: Record<string, string> = {
		openai: 'gpt-4o-mini',
		anthropic: 'claude-haiku-4-5-20251001',
		azure_openai: 'nom de votre déploiement',
	};

	let cfg = {
		actif: false,
		fournisseur: 'openai',
		modele: '',
		base_url: '',
		api_version: '',
		max_jetons: 1500,
		delai_s: 45,
		envoi_document: true,
	};
	let cle = '';
	let clePosee = false;
	let enregistrement = false;
	let test: { etat: 'aucun' | 'encours' | 'ok' | 'ko'; message: string } = {
		etat: 'aucun',
		message: '',
	};

	//  🔴 La liste des modèles vient du FOURNISSEUR, pas d'un catalogue écrit ici
	//  (11/09/2026 — « on peut choisir un modèle plus intelligent ? »). Le champ
	//  était libre avec trois exemples en dur et le commentaire « le catalogue
	//  bouge vite » : c'était l'aveu du défaut. Un repère recopié propose ce que
	//  la clé ne peut pas appeler et cache ce qui est sorti depuis.
	//
	//  ⚠️ `catalogue.listable === false` n'est PAS une panne — Azure n'expose pas
	//  ses déploiements, et une clé peut très bien synthétiser sans avoir le droit
	//  de s'inventorier. On retombe alors sur la saisie libre, en disant pourquoi.
	let catalogue: {
		etat: 'aucun' | 'encours' | 'pret' | 'indisponible';
		motif: string;
		modeles: { id: string; libelle: string }[];
	} = { etat: 'aucun', motif: '', modeles: [] };

	//  Le modèle enregistré reste proposé même s'il n'est plus au catalogue :
	//  sinon la liste le remplacerait en silence par son premier élément, et un
	//  simple Enregistrer changerait le modèle sans que personne l'ait demandé.
	$: choixModeles =
		catalogue.etat === 'pret' && cfg.modele && !catalogue.modeles.some((m) => m.id === cfg.modele)
			? [{ id: cfg.modele, libelle: `${cfg.modele} (enregistré)` }, ...catalogue.modeles]
			: catalogue.modeles;

	$: azure = cfg.fournisseur === 'azure_openai';

	$: if (valeurs && Object.keys(valeurs).length) hydrater(valeurs);

	let hydrate = false;
	function hydrater(lues: Record<string, string>) {
		if (hydrate) return;
		hydrate = true;
		cfg = {
			actif: lues['llm_actif'] === '1',
			fournisseur: lues['llm_fournisseur'] || 'openai',
			modele: lues['llm_modele'] || '',
			base_url: lues['llm_base_url'] || '',
			api_version: lues['llm_api_version'] || '',
			max_jetons: Number(lues['llm_max_jetons']) || 1500,
			delai_s: Number(lues['llm_delai_s']) || 45,
			envoi_document: lues['llm_envoi_document'] !== '0',
		};
		clePosee = !!lues['llm_api_key'];
	}

	async function enregistrer() {
		enregistrement = true;
		try {
			const charge: Record<string, string> = {
				llm_actif: cfg.actif ? '1' : '0',
				llm_fournisseur: cfg.fournisseur,
				llm_modele: cfg.modele.trim(),
				llm_base_url: cfg.base_url.trim(),
				llm_api_version: cfg.api_version.trim(),
				llm_max_jetons: String(cfg.max_jetons),
				llm_delai_s: String(cfg.delai_s),
				llm_envoi_document: cfg.envoi_document ? '1' : '0',
			};
			//  🔴 La clé n'est envoyée QUE si l'on en a saisi une. Une chaîne vide
			//  écraserait celle qui est enregistrée — et rien ne le dirait avant la
			//  prochaine synthèse.
			if (cle) charge['llm_api_key'] = cle;
			await configApi.save(charge);
			if (cle) {
				clePosee = true;
				cle = '';
			}
			test = { etat: 'aucun', message: '' };
			toast('success', 'Configuration enregistrée');
			//  Le fournisseur ou la clé viennent peut-être de changer : le
			//  catalogue précédent ne décrit plus ce qu'on peut appeler.
			catalogue = { etat: 'aucun', motif: '', modeles: [] };
		} catch (e: any) {
			toast('error', e?.message ?? 'Erreur à l’enregistrement');
		} finally {
			enregistrement = false;
		}
	}

	async function chargerModeles() {
		catalogue = { etat: 'encours', motif: '', modeles: [] };
		try {
			const r = await configApi.llmModeles();
			catalogue = r.listable
				? { etat: 'pret', motif: '', modeles: r.modeles }
				: { etat: 'indisponible', motif: r.motif, modeles: [] };
		} catch (e: any) {
			catalogue = {
				etat: 'indisponible',
				motif: e?.message ?? 'Liste indisponible',
				modeles: [],
			};
		}
	}

	async function tester() {
		test = { etat: 'encours', message: '' };
		try {
			const r = await configApi.llmTest();
			test = {
				etat: 'ok',
				message: `${r.fournisseur} · ${r.modele} — réponse « ${r.reponse} » en ${r.duree_ms} ms`,
			};
		} catch (e: any) {
			test = { etat: 'ko', message: e?.message ?? 'Le test a échoué' };
		}
	}
</script>

<div class="card">
	<h2 class="titre-onglet">
		<Icon name="zap" size={18} /> Assistant IA (synthèse de contrat)
	</h2>

	<SectionFormulaire premiere titre="Service">
		<label class="field case">
			<input type="checkbox" bind:checked={cfg.actif} />
			Activer l’assistant
			<span class="aide">
				Désactivé, l’icône ✨ n’apparaît nulle part et aucun appel n’est facturé.
			</span>
		</label>

		<ChoixPastilles
			options={FOURNISSEURS}
			bind:valeur={cfg.fournisseur}
			tous={false}
			libelle="Fournisseur"
			libelleVisible
			requis
		/>

		<ChampSecret
			libelle="Clé d’API *"
			bind:valeur={cle}
			pose={clePosee}
			placeholder="sk-…"
			aide="Elle n’est jamais renvoyée par le serveur, même à un administrateur."
		/>

		<div class="form-grid">
			<label class="field">
				Modèle
				{#if catalogue.etat === 'pret'}
					<select bind:value={cfg.modele}>
						<option value="">Modèle par défaut du fournisseur</option>
						{#each choixModeles as m (m.id)}
							<option value={m.id}>{m.libelle}</option>
						{/each}
					</select>
				{:else}
					<input
						type="text"
						bind:value={cfg.modele}
						placeholder={MODELES_REPERE[cfg.fournisseur]}
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
							: ''} avec cette clé, du plus récent au plus ancien. Un modèle plus capable rend une synthèse
						plus fidèle, et coûte plus cher par contrat.
					{:else if catalogue.etat === 'indisponible'}
						{catalogue.motif} Saisissez l’<strong>identifiant d’API</strong> à la main — pas le nom commercial.
					{:else if !clePosee}
						Enregistrez d’abord une clé : la liste des modèles se lit avec elle.
					{:else}
						L’<strong>identifiant d’API</strong>, pas le nom commercial. Laissé vide, le modèle par
						défaut du fournisseur est employé.
						{azure
							? 'Sur Azure, indiquez le nom de votre déploiement.'
							: 'Le bouton ci-dessus demande au fournisseur ce que votre clé peut appeler.'}
					{/if}
				</span>
			</label>
			<label class="field">
				Adresse du service {azure ? '*' : ''}
				<input
					type="url"
					bind:value={cfg.base_url}
					placeholder={azure ? 'https://mon-instance.openai.azure.com' : 'adresse par défaut'}
				/>
				<span class="aide">
					{azure
						? 'Obligatoire : Azure n’a pas d’adresse publique, chaque client a la sienne.'
						: 'À renseigner seulement pour passer par un relais compatible.'}
				</span>
			</label>
			{#if azure}
				<label class="field">
					Version d’API
					<input type="text" bind:value={cfg.api_version} placeholder="2024-06-01" />
					<span class="aide">La version indiquée dans votre portail Azure.</span>
				</label>
			{/if}
		</div>
	</SectionFormulaire>

	<SectionFormulaire titre="Garde-fous">
		<div class="form-grid">
			<label class="field">
				Longueur maximale de la réponse
				<input type="number" bind:value={cfg.max_jetons} min="200" max="32000" step="500" />
				<span class="aide">
					En jetons, et c’est un plafond de <strong>coût</strong> autant que de longueur : seuls les
					jetons réellement produits sont facturés. Comptez <strong>10 000</strong> pour un modèle récent
					— il raisonne avant d’écrire, et ce raisonnement compte dans le plafond. Une synthèse coupée
					au milieu d’une section ressemble à un défaut du modèle alors que c’est ce champ.
				</span>
			</label>
			<label class="field">
				Délai d’attente
				<input type="number" bind:value={cfg.delai_s} min="10" max="300" step="5" />
				<span class="aide">
					En secondes. Au-delà, on renonce et l’écran le dit — le champ reste saisissable à la main.
				</span>
			</label>
		</div>
		<label class="field case">
			<input type="checkbox" bind:checked={cfg.envoi_document} />
			Envoyer le document du contrat au service
			<span class="aide">
				Sans lui, quatre sections de la synthèse sur sept restent vides : montants, prestations
				incluses et exclues ne vivent que dans le PDF. Sont transmis <strong
					>tous les documents du contrat</strong
				> — l’initial, ses avenants, ses conditions générales : n’en lire qu’un rendrait les montants
				faux dès le premier avenant. Rien d’autre ne part : ni pièce jointe d’un ticket, ni document d’un
				autre contrat. Le texte est extrait côté serveur, le fichier lui-même ne quitte jamais le site.
			</span>
		</label>
	</SectionFormulaire>

	<SectionFormulaire titre="Vérification">
		<p class="aide" style="margin-bottom:.6rem">
			Trois champs remplis ne prouvent rien : une clé se révoque, un modèle se renomme. Ce test pose
			une vraie question au service et attend sa réponse.
			<br />
			⚠️ Il porte sur la configuration <strong>enregistrée</strong> : cliquez d’abord sur « Enregistrer
			» si vous venez de modifier un champ. L’assistant n’a pas besoin d’être activé — on teste justement
			pour décider de l’activer.
		</p>
		<div class="ligne-test">
			<button
				class="btn btn-outline"
				type="button"
				on:click={tester}
				disabled={test.etat === 'encours'}
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

	<div class="form-actions">
		<button class="btn btn-primary" type="button" on:click={enregistrer} disabled={enregistrement}>
			{enregistrement ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</div>

<style>
	/*  La rangée qui porte le bouton de lecture du catalogue, sous le champ.
	    Un `<div>` plutôt qu'un frère du `<label>` : le bouton appartient au champ
	    Modèle, et l'en sortir le ferait dériver au premier changement de grille. */
	.ligne-modele {
		display: flex;
		margin-top: 0.35rem;
	}

	.titre-onglet {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 1rem;
		font-weight: 700;
		margin: 0 0 0.9rem;
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
