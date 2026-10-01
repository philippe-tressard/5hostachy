<!--
  ChampsIdentiteCopropriete.svelte — les champs d'identité de la copropriété,
  écrits UNE fois (#779, 01/10/2026).

  Admin › Fiche copropriété et la fiche de la page Résidence les saisissaient
  chacune à sa façon, et la copie de Résidence ne savait pas EFFACER un nombre :
  un champ vidé n'était pas envoyé, l'ancienne valeur restait. La version de
  l'administration — libellés de la fiche ANAH, nom obligatoire, vide envoyé à
  `null` — fait foi (`standards/02` §4 bis : la plus juste, à égalité de
  déploiement). 🔒 `npm run lint:identite-copropriete` refuse une troisième copie.

  Le composant rend les champs, pas la grille : l'écran les pose dans sa
  `.form-grid`, à côté de ce qui lui est propre.
-->
<script context="module" lang="ts">
	import { nombreOuNull } from '$lib/utils';

	/** Ce que `CoproprieteUpdate` accepte de l'identité ; un nombre vide vaut `''`
	 *  ou `null` le temps de la saisie (cf. `chargeIdentite`). */
	export type IdentiteCopropriete = {
		nom: string;
		adresse: string;
		nb_lots_total: string | number | null;
		nb_lots_principaux: string | number | null;
		annee_construction: string | number | null;
		numero_immatriculation: string;
	};

	const NUMERIQUES = ['nb_lots_total', 'nb_lots_principaux', 'annee_construction'] as const;

	/** Le formulaire pré-rempli depuis la fiche lue (ou vide, sans fiche). */
	export function identiteDepuis(
		fiche: Partial<Record<keyof IdentiteCopropriete, unknown>> | null,
	) {
		const v = (k: keyof IdentiteCopropriete) => (fiche?.[k] ?? '') as string;
		return {
			nom: v('nom'),
			adresse: v('adresse'),
			nb_lots_total: v('nb_lots_total'),
			nb_lots_principaux: v('nb_lots_principaux'),
			annee_construction: v('annee_construction'),
			numero_immatriculation: v('numero_immatriculation'),
		} satisfies IdentiteCopropriete;
	}

	/** Le formulaire tel que le serveur l'attend. Un nombre vide part à `null`,
	 *  jamais à `''` — Pydantic refuse la chaîne vide sur un `Optional[int]` — ni
	 *  omis : omis, il ne s'effacerait pas. Les autres clés passent telles quelles.
	 *
	 *  La règle du vide est celle de `nombreOuNull` (#1516) : `''` ET `null`. */
	export function chargeIdentite<T extends IdentiteCopropriete>(valeurs: T) {
		const charge: Record<string, unknown> = { ...valeurs };
		for (const champ of NUMERIQUES) {
			charge[champ] = nombreOuNull(valeurs[champ]);
		}
		return charge;
	}
</script>

<script lang="ts">
	import EtoileRequis from '$lib/components/EtoileRequis.svelte';

	export let valeurs: IdentiteCopropriete;
</script>

<label class="field">
	<span>Nom de la résidence<EtoileRequis vide={!valeurs.nom} /></span>
	<input bind:value={valeurs.nom} required />
</label>
<label class="field">
	<span>Adresse</span>
	<input bind:value={valeurs.adresse} />
</label>
<!--  Les DEUX décomptes de la fiche du registre national (ANAH). Un seul champ
      obligeait à choisir lequel perdre, et le chiffre saisi ne disait pas lequel
      il était : 195 ou 63 pour la même résidence. Les libellés reprennent mot
      pour mot ceux de la fiche, pour qu'on recopie sans avoir à interpréter. -->
<label
	class="field"
	title="Le « Nombre de lots » de la fiche d'immatriculation : tous les lots, caves et parkings compris."
>
	<span>Nombre de lots — total, caves et parkings compris</span>
	<input type="number" min="1" bind:value={valeurs.nb_lots_total} />
</label>
<label
	class="field"
	title="Le décompte qui porte les seuils réglementaires, et qui dit combien de foyers vivent ici."
>
	<span>Dont lots d'habitation, commerces et bureaux</span>
	<input type="number" min="1" bind:value={valeurs.nb_lots_principaux} />
</label>
<label class="field">
	<span>Année de construction</span>
	<input type="number" min="1800" max="2100" bind:value={valeurs.annee_construction} />
</label>
<label class="field champ-large">
	<span>N° immatriculation (ANAH)</span>
	<input bind:value={valeurs.numero_immatriculation} placeholder="ex : D75010800001" />
</label>
