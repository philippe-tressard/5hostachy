<!--
  **La section 9 — Diffusion** : qui verra cette entrée, et par quels canaux.

  Message interne · groupe WhatsApp / syndic / conseil syndical · adresse externe.

  ## Pourquoi ce composant (#498, 19/08/2026)

  Arbitré à l'écran : *« C'est une évolution sur l'objet Diffusion, qu'il soit
  positionné sur n'importe quel formulaire. »*

  La Diffusion est un **objet du site**, pas un bloc de formulaire : elle se rend
  partout pareil (R3 du cadre #430), et tout ce qu'on lui ajoute doit atteindre
  les neuf écrans qui la portent. Elle était écrite dans `EvolForm` d'un côté et
  dans `ChampsCommuns` de l'autre — deux écritures d'une même notion, donc deux
  valeurs libres de diverger, ce qui est exactement arrivé aux canaux avant que
  `CanauxNotification` ne les réunisse (08/08/2026).

  ⚠️ **`CanauxNotification` ne suffisait pas** : il porte les trois cases, pas la
  section qui les entoure — son titre, le message interne, l'adresse externe, et
  l'avertissement sur les fichiers WhatsApp. C'est ce reste-là qui divergeait.

  ## Ce que ce composant ne fait PAS

  Il ne décide pas de l'envoi et ne compose aucun message : il rend des cases.
  L'aperçu de ce qui partira vit dans `ApercuDiffusion.svelte`, et la composition
  côté serveur — un aperçu reconstruit ici mentirait à la première évolution d'un
  gabarit (`standards/04` §14).
-->
<script lang="ts">
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import CanauxNotification from '$lib/components/CanauxNotification.svelte';

	/** Préfixe des `id` : plusieurs formulaires coexistent souvent à l'écran. */
	export let idPrefixe = 'diffusion';
	/** Les trois canaux — liés par l'appelant, qui seul sait ce qu'ils déclenchent. */
	export let whatsapp = false;
	export let syndic = false;
	export let cs = false;
	/** Afficher les trois cases de canal. */
	export let avecCanaux = false;
	/** Afficher le champ d'adresse externe (CS/admin). */
	export let avecEmailExterne = false;
	export let emailExterne = '';
	/**  Proposer « Message interne ». C'est une décision de DIFFUSION — qui voit
	     cette entrée —, donc elle est rendue ici, avec les canaux, et non au
	     milieu du commentaire comme le faisait le formulaire de réponse écrit à
	     la main de la fiche d'un ticket (#431). */
	export let avecInterne = false;
	export let interne = false;
	/**  Pièces jointes de l'entrée : sert uniquement à savoir s'il faut avertir
	     que WhatsApp ne les emporte pas. */
	export let fichiers: string[] = [];
	/** Infobulle propre au contexte, passée telle quelle à `CanauxNotification`. */
	export let aideWhatsapp = '';
	/** Rendu en version dense (fil d'évolution, devis). */
	export let compact = false;

	$: visible = avecCanaux || avecEmailExterne || avecInterne;
</script>

{#if visible}
	<!-- ── 9. Diffusion — EN DERNIER, après les pièces jointes ──────────────
	     L'avertissement sur les fichiers est rendu au CONTACT de la case WhatsApp
	     qu'il commente : sous le sélecteur de fichiers, il en était séparé par
	     toute la rubrique (#416). -->
	<SectionFormulaire titre="Diffusion">
		{#if avecInterne}
			<label class="case-interne">
				<input type="checkbox" bind:checked={interne} />
				<span>Message interne (visible par le conseil syndical uniquement)</span>
			</label>
		{/if}

		{#if avecCanaux}
			<CanauxNotification bind:whatsapp bind:syndic bind:cs {compact} {aideWhatsapp} />
			{#if whatsapp && fichiers.length > 0}
				<p class="aide-case">
					⚠️ Les fichiers ne sont pas envoyés via WhatsApp, uniquement le texte.
				</p>
			{/if}
		{/if}

		{#if avecEmailExterne}
			<div class="field champ-large">
				<label for="{idPrefixe}-email-ext">&#x1F4E7; Notifier une adresse email externe</label>
				<input id="{idPrefixe}-email-ext" type="email" bind:value={emailExterne}
					placeholder="contact@exemple.fr" />
			</div>
		{/if}
	</SectionFormulaire>
{/if}

<style>
	/*  Définie ICI, avec le balisage qu'elle habille : `.checkbox-field` n'est pas
	    une classe d'`app.css` — chaque composant qui l'emploie la style lui-même,
	    et une classe seulement utilisée arrive nue à l'écran (v2.67.11). */
	.case-interne {
		display: flex;
		align-items: center;
		gap: .4rem;
		cursor: pointer;
		font-size: .85rem;
		margin: 0 0 .6rem;
	}
	.case-interne input[type='checkbox'] { width: auto; margin: 0; flex-shrink: 0; }
	/*  Sous 480 px, la cible tactile d'une case ne faisait que 16 à 18 px de haut
	    (socle 11 §10). */
	@media (max-width: 480px) {
		.case-interne { min-height: 44px; }
	}
</style>
