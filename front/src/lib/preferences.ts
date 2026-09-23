/**
 * Les deux clés des préférences de notification par e-mail.
 *
 * Elles doivent rester identiques à celles de `api/app/utils/preferences_mail.py`,
 * qui fait autorité : c'est lui qui décide d'envoyer ou non. Une clé recopiée de
 * travers ici ne produirait aucune erreur — l'écran cocherait une case que le
 * serveur ne lirait jamais, et le résident croirait avoir réglé quelque chose.
 *
 * `api/tests/test_preferences_mail.py` vérifie que les deux côtés emploient les
 * mêmes noms et les mêmes valeurs par défaut.
 */
export const MON_BATIMENT = 'mon_batiment_mail';
export const AUTRES_BATIMENTS = 'autres_batiments_mail';
/** 🔔 La cloche, réglable comme le courriel depuis #1187 (23/09/2026). */
export const MON_BATIMENT_APP = 'mon_batiment_app';
export const AUTRES_BATIMENTS_APP = 'autres_batiments_app';

/** Coché pour son propre bâtiment, décoché pour les autres : personne n'a
 *  jamais consenti à recevoir les e-mails d'ailleurs. */
export const DEFAUTS_NOTIFS: Record<string, boolean> = {
	[MON_BATIMENT]: true,
	[AUTRES_BATIMENTS]: false,
	//  La cloche sonnait pour tout : ses défauts le reproduisent — rien ne
	//  disparaît sans un geste du résident.
	[MON_BATIMENT_APP]: true,
	[AUTRES_BATIMENTS_APP]: true,
};

/** Les deux canaux du profil, et leurs deux cases — une table, rendue une fois. */
export const CANAUX_NOTIFS = [
	{ titre: 'Notifications par e-mail', mon: MON_BATIMENT, autres: AUTRES_BATIMENTS },
	{
		titre: "Notifications dans l'application",
		mon: MON_BATIMENT_APP,
		autres: AUTRES_BATIMENTS_APP,
	},
] as const;

/**
 * Les clés que l'utilisateur n'a **jamais réglées** — leur valeur est héritée.
 *
 * 🔴 Pourquoi cette fonction existe (#1147, 22/09/2026)
 *
 * `mon_batiment_mail` vaut `true` par défaut. Un conseiller qui n'a jamais
 * ouvert son profil reçoit donc les courriels de son bâtiment **sans avoir rien
 * choisi** — et l'écran lui montre une case cochée, qui laisse croire qu'il l'a
 * cochée. Signalé à l'écran : *« c'est le membre du CS nominativement qui a
 * choisi cette option dans son profil »*, ce qui ne décrivait personne.
 *
 * Arbitré : le défaut reste activé — c'est lui qui garantit qu'un signalement
 * atteint quelqu'un — mais l'écran le **dit**.
 *
 * ⚠️ Elle lit le JSON BRUT, pas les valeurs résolues : `lire()` côté serveur
 * applique les défauts et **perd** cette information. C'est la seule raison pour
 * laquelle le brut traverse jusqu'à l'écran, et il ne sert qu'à ça.
 *
 * PURE : une chaîne en entrée, un ensemble de clés en sortie. Un JSON illisible
 * rend TOUTES les clés héritées — c'est exactement ce qu'il est alors.
 */
export function clesHeritees(brut: string | null | undefined): Set<string> {
	let lues: Record<string, unknown> = {};
	try {
		const parse = JSON.parse(brut || '{}');
		if (parse && typeof parse === 'object' && !Array.isArray(parse)) lues = parse;
	} catch {
		lues = {};
	}
	return new Set(Object.keys(DEFAUTS_NOTIFS).filter((cle) => typeof lues[cle] !== 'boolean'));
}
