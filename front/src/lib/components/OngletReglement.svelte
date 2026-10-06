<!--
  Espace CS › Règlement — poser au règlement de copropriété la question d'un résident.

  Trois blocs, dans l'ordre du geste :
  1. le TEXTE du règlement — la version en vigueur, et le chargement d'une
     nouvelle (Markdown, lu par le navigateur et envoyé comme texte) ;
  2. la QUESTION — l'assistant répond en juriste, extraits à l'appui ;
  3. l'HISTORIQUE — une question déjà posée ne se repaie pas, et une réponse
     relue peut rejoindre la FAQ (boîte ouverte dans la carte).

  L'état et les appels réseau vivent ici, la page ne garde que le choix de
  l'onglet (`svelte-patterns`, famille `Onglet<Nom>`). Le serveur décide si
  l'assistant peut répondre (`disponible`) : rien de sa configuration ne sort.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import CarteQuestionReglement from '$lib/components/CarteQuestionReglement.svelte';
	import EncartAvertissement from '$lib/components/EncartAvertissement.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import EtoileRequis from '$lib/components/EtoileRequis.svelte';
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import FormulaireFaq from '$lib/components/FormulaireFaq.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import {
		faq as faqApi,
		reglement as reglementApi,
		type EtatReglement,
		type QuestionReglement,
	} from '$lib/api';
	import { basculer } from '$lib/accordeon';
	import { fmtDatetime } from '$lib/date';
	import { cibleDuHash, revelerCible } from '$lib/deepLink';
	import { messageErreur } from '$lib/erreurs';
	import { categorieSaisie, saisieFaqVide, type SaisieFaq } from '$lib/faq';
	import { richEmpty } from '$lib/publications';
	import { ACCEPT_TEXTE_REGLEMENT } from '$lib/reglement';
	import { isAdmin } from '$lib/stores/auth';
	import { fmtNombre } from '$lib/utils';

	let etat: EtatReglement | null = null;
	let questions: QuestionReglement[] = [];
	let chargement = true;
	let erreur = '';

	let fichiers: File[] = [];
	let chargementTexte = false;

	let question = '';
	let envoi = false;

	let ouvert: number | null = null;
	let publication: number | null = null;
	let formFaq: SaisieFaq = saisieFaqVide();
	let categories: string[] = [];
	let erreurCategories = '';
	let enregistrementFaq = false;

	onMount(async () => {
		try {
			[etat, questions] = await Promise.all([reglementApi.etat(), reglementApi.questions()]);
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
		//  `#question-reglement-<id>` : une question dont on a copié le lien.
		const cible = cibleDuHash('question-reglement');
		if (cible !== null) {
			ouvert = cible;
			revelerCible(`question-reglement-${cible}`);
		}
	});

	async function chargerTexte() {
		const fichier = fichiers[0];
		if (!fichier) return;
		chargementTexte = true;
		try {
			const version = await reglementApi.charger(fichier.name, await fichier.text());
			const nouvelle = version.id !== etat?.texte?.id;
			etat = await reglementApi.etat();
			questions = await reglementApi.questions();
			fichiers = [];
			toast('success', nouvelle ? 'Texte du règlement chargé.' : 'Ce texte est déjà en vigueur.');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			chargementTexte = false;
		}
	}

	async function poser() {
		if (!question.trim()) return;
		envoi = true;
		try {
			const q = await reglementApi.poser(question.trim());
			questions = [q, ...questions];
			ouvert = q.id;
			publication = null;
			question = '';
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			envoi = false;
		}
	}

	async function ouvrirPublication(q: QuestionReglement) {
		if (publication === q.id) {
			publication = null;
			return;
		}
		formFaq = { ...saisieFaqVide(), question: q.question, reponse: q.reponse };
		publication = q.id;
		ouvert = null;
		erreurCategories = '';
		try {
			categories = await faqApi.categories();
		} catch (e) {
			erreurCategories = messageErreur(e);
		}
	}

	async function publier(q: QuestionReglement) {
		const categorie = categorieSaisie(formFaq);
		if (!formFaq.question.trim() || richEmpty(formFaq.reponse) || !categorie) {
			toast('error', 'Question, catégorie et réponse sont obligatoires.');
			return;
		}
		enregistrementFaq = true;
		try {
			const maj = await reglementApi.publierDansLaFaq(q.id, {
				categorie,
				question: formFaq.question.trim(),
				reponse: formFaq.reponse.trim(),
			});
			questions = questions.map((x) => (x.id === maj.id ? maj : x));
			publication = null;
			toast('success', 'Réponse publiée dans la FAQ.');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enregistrementFaq = false;
		}
	}
</script>

<EncartAvertissement>
	Les réponses sont un <strong>avis indicatif</strong>, rédigé par l'assistant d'après le texte de
	travail chargé ici : il ne se substitue pas aux actes authentiques, qui seuls font foi. Relisez-le
	— et vérifiez les extraits signalés ⚠️ — avant de le relayer.
</EncartAvertissement>

<EtatListe {chargement} {erreur}>
	{#if etat}
		<section class="card config-section">
			<h3 class="config-section-title">Texte du règlement</h3>
			{#if etat.texte}
				<p class="texte-courant">
					<strong>{etat.texte.titre}</strong>
					<span class="aide"
						>{etat.texte.nom_fichier} · {fmtNombre(etat.texte.nb_caracteres)} caractères · chargé le
						{fmtDatetime(etat.texte.cree_le)}{etat.texte.charge_par
							? ` par ${etat.texte.charge_par}`
							: ''}{etat.nb_versions > 1 ? ` · version ${etat.nb_versions}` : ''}</span
					>
				</p>
			{:else}
				<p class="aide">
					{$isAdmin
						? "Aucun texte n'est chargé : chargez le règlement pour pouvoir l'interroger."
						: "Aucun texte n'est chargé : l'administration doit charger le règlement avant qu'on puisse l'interroger."}
				</p>
			{/if}
			{#if $isAdmin}
				<FichiersUpload
					differe
					bind:fichiers
					max={1}
					accept={ACCEPT_TEXTE_REGLEMENT}
					types="Markdown (.md)"
					label="Choisir le fichier"
					titre={etat.texte
						? 'Charger une nouvelle version (Markdown)'
						: 'Charger le texte (Markdown)'}
				/>
				{#if fichiers.length}
					<div class="form-actions">
						<button class="btn btn-primary" disabled={chargementTexte} on:click={chargerTexte}
							>{chargementTexte ? 'Chargement…' : 'Charger ce texte'}</button
						>
					</div>
				{/if}
			{/if}
			<p class="aide">
				Le texte reste dans l'application : il n'est ni publié, ni versé au dépôt du code. Les
				questions déjà posées gardent la version qu'elles ont lue.
			</p>
		</section>

		<section class="card config-section">
			<h3 class="config-section-title">Question d'un résident</h3>
			<form on:submit|preventDefault={poser}>
				<label class="field"
					><span>Question<EtoileRequis vide={!question.trim()} /></span><textarea
						rows="3"
						maxlength="2000"
						bind:value={question}
						placeholder="Ex. : Un copropriétaire peut-il installer une climatisation sur son balcon ?"
					></textarea></label
				>
				{#if !etat.disponible}
					<EncartAvertissement compact>
						L'assistant n'est pas activé pour cet usage : Admin › Assistant IA › « Question au
						règlement de copropriété ».
					</EncartAvertissement>
				{/if}
				<div class="form-actions">
					<button
						type="submit"
						class="btn btn-primary"
						disabled={envoi || !question.trim() || !etat.disponible || !etat.texte}
						>{envoi ? 'Lecture du règlement…' : 'Poser la question'}</button
					>
				</div>
				{#if envoi}
					<p class="aide">
						L'assistant lit tout le règlement avant de répondre : comptez jusqu'à deux minutes.
					</p>
				{/if}
			</form>
		</section>
	{/if}

	<h3 class="titre-historique">Questions posées</h3>
	<EtatListe
		vide={questions.length === 0}
		titreVide="Aucune question posée"
		messageVide="Les réponses de l'assistant s'afficheront ici."
	>
		{#each questions as q (q.id)}
			<CarteQuestionReglement
				{q}
				ouvert={ouvert === q.id}
				publication={publication === q.id}
				on:basculer={() => {
					publication = null;
					ouvert = basculer(ouvert, q.id);
				}}
				on:publier={() => ouvrirPublication(q)}
			>
				<FormulaireFaq
					slot="formulaire"
					bind:form={formFaq}
					{categories}
					{erreurCategories}
					enregistrement={enregistrementFaq}
					onEnregistrer={() => publier(q)}
					on:annule={() => (publication = null)}
				/>
			</CarteQuestionReglement>
		{/each}
	</EtatListe>
</EtatListe>

<style>
	.texte-courant {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		margin: 0 0 0.75rem;
	}
	.titre-historique {
		margin: 1.5rem 0 0.6rem;
		font-size: var(--fs-md);
	}
</style>
