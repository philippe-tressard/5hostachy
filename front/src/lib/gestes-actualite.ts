/**
 * **Les gestes qu'on fait à une actualité** — depuis le fil, côté écran.
 *
 * Trois à ce jour : la promouvoir en affaire (#1094), la supprimer, et
 * enregistrer ses options de mise en avant. Ils vivent
 * ensemble parce qu'ils partagent leur forme — une confirmation dite avec les
 * mots du lecteur, un appel, puis le retrait de la carte — et parce que l'écran
 * qui les portait est au-dessus du plafond de modularité.
 *
 * ## La promotion : une actualité devient une affaire (#1094)
 *
 * ## Le gain, et il est pour l'utilisateur
 *
 * Une actualité qui dérape — « attention, fuite au 3e » — obligeait à rouvrir
 * une affaire et **tout retaper**. Ici, titre, description, pièces jointes et
 * périmètre suivent ; on ajoute un statut.
 *
 * ## Pourquoi un module et pas trente lignes dans l'écran
 *
 * `actualites/+page.svelte` est au-dessus du plafond de modularité, et le
 * contrôle a refusé qu'il grossisse — « on découpe QUAND on y touche ».
 *
 * Mais ce n'est pas la seule raison, ni la meilleure : la promotion a **deux
 * moitiés qui doivent rester ensemble**. Celle qui convertit, et celle qui
 * rattrape l'ancienne adresse. Séparées, la seconde se perd — et c'est elle
 * qui empêche un courriel déjà envoyé de finir sur un lien mort.
 *
 * ## L'arbitrage du 21/09/2026 : la publication DISPARAÎT
 *
 * Trois voies étaient possibles — convertir, coexister, archiver. La conversion
 * a été retenue : *un seul objet à la fois, jamais de doublon*.
 *
 * Verrouillé côté serveur par `api/tests/test_promotion_actualite.py`.
 */
import { goto } from '$app/navigation';

import { publications as pubsApi } from '$lib/api';
import type { Publication, Ticket } from '$lib/api/types';
import { confirmerPuis } from '$lib/confirmation';
import { tenter } from '$lib/erreurs';
import { PUBLICATION } from '$lib/entites/publication';
import { TICKET } from '$lib/entites/ticket';

/** L'adresse d'une affaire — écrite ici, et une seule fois pour ce module. */
const versAffaire = (id: number) => `/tickets/${id}`;

/**
 * Promouvoir une actualité, après confirmation, et suivre l'affaire née d'elle.
 *
 * ⚠️ La confirmation n'est pas une politesse : l'actualité **quitte le fil** et
 * le geste ne se défait pas. Le texte le dit avec les mots du lecteur — « quittera
 * le fil », « rien n'est à ressaisir » — et jamais ceux du modèle.
 *
 * @param retirerDeLaListe ce que l'écran fait de sa liste une fois la
 *   conversion faite. Il reste chez lui : chaque écran range la sienne à sa
 *   façon, et un paramètre de plus aurait obligé les appelants à se ressembler
 *   là où ils n'ont aucune raison de le faire (même choix que `confirmerPuis`).
 * @returns `true` si la promotion a eu lieu.
 */
export async function promouvoirActualite(
	pub: Pick<Publication, 'id' | 'titre'>,
	retirerDeLaListe: (id: number) => void,
): Promise<boolean> {
	let affaire: Ticket | undefined;
	const fait = await confirmerPuis(
		{
			titre: `En faire une ${TICKET.libelle.toLowerCase()}`,
			message:
				`« ${pub.titre} » quittera le fil des actualités et deviendra une ` +
				`${TICKET.libelle.toLowerCase()} à suivre. Le titre, la description et les ` +
				'pièces jointes suivent — rien n’est à ressaisir.',
			libelleConfirmer: `En faire une ${TICKET.libelle.toLowerCase()}`,
		},
		`${TICKET.libelle} ouverte — le suivi peut commencer.`,
		async () => {
			affaire = await pubsApi.promouvoir(pub.id);
			retirerDeLaListe(pub.id);
		},
		'Impossible de promouvoir cette actualité',
	);
	//  Le lecteur suit l'objet : il vient de demander un suivi, c'est sur
	//  l'affaire qu'il veut être. Le laisser sur le fil l'obligerait à la
	//  retrouver — et la carte qu'il regardait n'y est plus.
	if (fait && affaire) goto(versAffaire(affaire.id));
	return fait;
}

/**
 * **L'ancienne adresse mène à l'affaire** — la moitié qui rattrape.
 *
 * 🔴 Une actualité publiée a déjà été envoyée par courriel, avec son adresse
 * `/actualites#pub-42`. La promotion la supprime : sans ce rattrapage, chacun
 * de ces courriels devient un lien mort. Le chantier refuse de renommer les
 * identifiants `TK-xxxx` pour exactement cette raison.
 *
 * Le serveur répond **410** avec l'affaire née d'elle — et **404** pour un
 * identifiant réellement inconnu, qu'on laisse alors tranquille plutôt que
 * d'annoncer une affaire qui n'existe pas.
 *
 * @returns `true` si l'on a redirigé — l'appelant n'a alors plus rien à faire.
 */
export async function suivrePublicationPromue(pubId: number): Promise<boolean> {
	try {
		await pubsApi.get(pubId);
		//  Elle existe : ce n'est pas une promotion, l'écran continue son travail
		//  (elle est peut-être simplement hors de la page chargée).
		return false;
	} catch (e: unknown) {
		const detail = (e as { data?: { detail?: { promu_en_affaire?: number } } })?.data?.detail;
		const id = detail?.promu_en_affaire;
		//  ⚠️ Tout autre échec — 404, 403, réseau — ne redirige RIEN. Se tromper
		//  ici enverrait le lecteur sur l'affaire de quelqu'un d'autre.
		if (typeof id !== 'number') return false;
		goto(versAffaire(id));
		return true;
	}
}

/**
 * Supprimer une actualité, définitivement.
 *
 * ⚠️ Passe par `confirmerPuis` et non par le `confirm()` du navigateur, qui est
 * ce que cet écran employait : la fenêtre native ne se met pas à la charte, ne
 * se traduit pas, et sa formulation n'est pas maîtrisée. Le déplacement du
 * geste a été l'occasion de l'aligner — c'est la moitié « au fil de l'eau » de
 * la règle de modularité.
 */
export async function supprimerActualite(
	pub: Pick<Publication, 'id' | 'titre'>,
	retirerDeLaListe: (id: number) => void,
): Promise<boolean> {
	return confirmerPuis(
		{
			titre: `Supprimer cette ${PUBLICATION.libelle.toLowerCase()}`,
			message: `« ${pub.titre} » sera supprimée définitivement. Ce geste ne se défait pas.`,
			libelleConfirmer: 'Supprimer',
			danger: true,
		},
		`${PUBLICATION.libelle} supprimée`,
		async () => {
			await pubsApi.delete(pub.id);
			retirerDeLaListe(pub.id);
		},
		'Impossible de supprimer',
	);
}

/** Les options de mise en avant d'une actualité — ce que l'écran en édite. */
export interface OptionsActualite {
	epingle: boolean;
	urgente: boolean;
	brouillon: boolean;
	confidentiel: boolean;
}

/**
 * Enregistrer les options de mise en avant.
 *
 * 🔴 **Le serveur a le dernier mot**, et c'est pourquoi l'appelant reçoit ce
 * qu'il REND, jamais ce qu'on lui a demandé : il peut refuser « confidentiel »
 * sur un périmètre à portée globale (`appliquer_confidentialite`). Ranger le
 * brouillon local afficherait alors une option que la base n'a pas.
 */
export async function enregistrerOptionsActualite(
	pub: Pick<Publication, 'id'>,
	options: OptionsActualite,
	remplacer: (maj: Publication) => void,
): Promise<boolean> {
	return tenter(
		async () => {
			const maj = await pubsApi.update(pub.id, { ...options });
			remplacer(maj);
		},
		'Options mises à jour',
		"Erreur d'enregistrement",
	);
}
