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
		} catch (e: any) {
			toast('error', e?.message ?? 'Erreur à l’enregistrement');
		} finally {
			enregistrement = false;
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
				<input type="text" bind:value={cfg.modele} placeholder={MODELES_REPERE[cfg.fournisseur]} />
				<span class="aide">
					L’<strong>identifiant d’API</strong>, pas le nom commercial : <code>gpt-4o-mini</code>,
					<code>gpt-4.1</code>, <code>claude-haiku-4-5-20251001</code>. Laissé vide, le modèle par
					défaut du fournisseur est employé. Sur Azure, indiquez le nom de votre
					<strong>déploiement</strong>.
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
				<input type="number" bind:value={cfg.max_jetons} min="200" max="8000" step="100" />
				<span class="aide">
					En jetons. C’est un plafond de <strong>coût</strong> autant que de longueur : une synthèse de
					contrat tient largement dans 1 500.
				</span>
			</label>
			<label class="field">
				Délai d’attente
				<input type="number" bind:value={cfg.delai_s} min="10" max="180" step="5" />
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
				incluses et exclues ne vivent que dans le PDF. Seul le document <strong
					>du contrat lui-même</strong
				> est transmis, jamais un autre fichier joint, et son texte est extrait côté serveur.
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
