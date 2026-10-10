#!/usr/bin/env node
/**
 *  Garde-fou : une rangée de pastilles qui FILTRE une liste dit combien elle
 *  montre, sur sa pastille retenue (10/10/2026, maquette J arbitrée à l'écran).
 *
 *  ## Pourquoi il existe
 *
 *  Le standard est né sur Mes affaires et a été étendu le même jour à toutes
 *  les rangées de filtres du site (annuaire des prestataires, utilisateurs,
 *  idées, annonces, badges, carnet d'entretien, fil d'une affaire). Il tient
 *  dans UNE prop — `compte` de `ChoixPastilles` (ou de `FiltrePerimetre`) —, et
 *  une prop qu'on oublie ne fait échouer ni la compilation ni un test : la
 *  rangée s'affiche, simplement sans son nombre. La prochaine rangée de filtres
 *  partirait donc sans lui, en silence.
 *
 *  ## Ce qu'il reconnaît comme un FILTRE
 *
 *  - une `<ChoixPastilles>` sans `radio` (le mode radio est un choix de
 *    formulaire) qui offre l'entrée « sans filtre » — `tous` absent (défaut
 *    « Tous ») ou une chaîne —, ou dont le libellé commence par « Filtrer » ;
 *  - toute `<FiltrePerimetre>`.
 *
 *  Un choix de FORMULAIRE qui offre une entrée vide (« Aucune », « Inchangé »)
 *  ne filtre rien : il se déclare dans `EXCEPTIONS`, avec sa raison.
 *
 *  Lancer : node scripts/check-compte-filtres.mjs [--selftest]
 */
import { controler } from './lib-source-unique.mjs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';
import { balisesOuvrantes } from './lib-balises.mjs';

/**  Choix de formulaire qui offrent une entrée vide — ils ne filtrent aucune
 *   liste. Une entrée qui ne sert plus fait échouer. */
const EXCEPTIONS = {
	'src/lib/components/BlocUsageIA.svelte':
		'l’effort de raisonnement d’un usage IA — « Par défaut du modèle » est une valeur du réglage',
	'src/lib/components/ChampFrequence.svelte':
		'la fréquence d’un contrat — « Aucune » est une valeur du champ',
	'src/routes/(app)/profil/+page.svelte':
		'le profil demandé — « Inchangé » est une valeur de la demande',
};

const A_UN_COMPTE = /(?:\scompte=|\{compte\})/;

/** Les lignes des rangées de filtres qui ne passent pas `compte`. PURE. */
export function fautes(source) {
	const texte = neutraliserCommentaires(source);
	const ligne = (i) => texte.slice(0, i).split('\n').length;
	const trouvees = [];
	for (const { balise, index } of balisesOuvrantes(texte, 'ChoixPastilles')) {
		if (/\sradio[=\s>/]/.test(balise)) continue;
		const sansTous = /\stous=\{false\}/.test(balise);
		const filtre = !sansTous || /\slibelle="Filtrer/.test(balise);
		if (filtre && !A_UN_COMPTE.test(balise)) trouvees.push(ligne(index));
	}
	for (const { balise, index } of balisesOuvrantes(texte, 'FiltrePerimetre')) {
		if (!A_UN_COMPTE.test(balise)) trouvees.push(ligne(index));
	}
	return trouvees;
}

process.exit(
	controler({
		extensions: ['.svelte'],
		//  Le composant lui-même : il REÇOIT le compte, il ne filtre rien.
		sources: ['src/lib/components/ChoixPastilles.svelte'],
		exceptions: EXCEPTIONS,
		fautes,
		cas: [
			['<ChoixPastilles options={o} bind:valeur={v} tous="Tous" libelle="Type" />', 1],
			//  `tous` absent : l'entrée « Tous » est offerte par défaut.
			['<ChoixPastilles options={o} bind:valeur={v} libelle="Contrat" />', 1],
			['<ChoixPastilles options={o} bind:valeur={v} tous="Tous" compte={liste.length} />', 0],
			['<ChoixPastilles options={o} bind:valeur={v} {compte} />', 0],
			//  Un `>` dans une expression ne coupe pas la balise avant `compte`.
			['<ChoixPastilles options={o.filter((x) => x.n > 1)} compte={n} />', 0],
			//  Un choix de formulaire : radio, ou sans entrée vide.
			['<ChoixPastilles options={o} bind:valeur={v} tous={false} radio="r" />', 0],
			['<ChoixPastilles options={o} bind:valeur={v} tous={false} libelle="Lot" />', 0],
			//  …sauf s'il se dit filtre.
			['<ChoixPastilles bind:valeur tous={false} libelle="Filtrer le fil" />', 1],
			['<FiltrePerimetre bind:choisi on:changer={c} />', 1],
			['<FiltrePerimetre bind:choisi compte={n} />', 0],
			['<!-- <ChoixPastilles tous="Tous" /> -->', 0],
		],
		ok: 'Rangées de filtres : chacune dit son compte sur la pastille retenue',
		ko: 'rangée(s) de filtres sans `compte`',
		conseil:
			'Passer `compte={<la liste affichée>.length}` — le nombre que la liste montre, filtres appliqués (`ChoixPastilles.compte`). Un choix de formulaire se déclare dans EXCEPTIONS.',
	}),
);
