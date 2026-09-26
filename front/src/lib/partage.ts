/**
 * Ce qu'un 🔗 peut TRANSMETTRE par courriel (#1357) — et comment le reconnaître
 * dans son lien.
 *
 * Miroir de `OBJETS_TRANSMISSIBLES` (`api/app/utils/liens.py`), plus l'affaire
 * (`ticket`), qui a sa propre route de lecture. `test_partage_vocabulaire.py`
 * compare les deux listes : un type ajouté d'un seul côté proposerait un envoi
 * que le serveur refuse, ou priverait un 🔗 de l'envoi.
 */
export const OBJETS_TRANSMISSIBLES = [
	'annonce',
	'idee',
	'faq',
	'sondage',
	'doc',
	'diag',
	'contrat',
	'presta',
] as const;

export type CiblePartage = { objet: string; id: number };

/**  Ce que désigne le lien d'un 🔗 — l'affaire de `/tickets/12`, le sondage de
 *   `/sondages/3`, l'annonce de `#annonce-42` —, ou `null` s'il ne se transmet pas. */
export function cibleDuLien(chemin: string | null, ancre: string | null): CiblePartage | null {
	const page = chemin?.match(/^\/(tickets|sondages)\/(\d+)$/);
	if (page) return { objet: page[1] === 'tickets' ? 'ticket' : 'sondage', id: Number(page[2]) };
	const m = ancre?.match(/^([a-z]+)-(\d+)$/);
	if (m && (OBJETS_TRANSMISSIBLES as readonly string[]).includes(m[1]))
		return { objet: m[1], id: Number(m[2]) };
	return null;
}
