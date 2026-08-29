/**
 * Le délai d'archivage, côté écran — **une seule lecture** (#515 point 2).
 *
 * ## Pourquoi ce fichier
 *
 * Deux écrans calculaient l'archivage dans le navigateur, chacun avec sa propre
 * clé de configuration et son propre défaut :
 *
 *   - `calendrier/+page.svelte` — `archivage_delai_heures`, défaut 48 **heures** ;
 *   - `tableau-de-bord/+page.svelte` — `publie_visibilite_jours`, défaut 30 **jours**.
 *
 * Deux valeurs, deux unités, deux défauts, pour la même question : « à partir de
 * quand un contenu quitte les listes actives ? »
 *
 * ## 🔴 Et aucune des deux n'était lue
 *
 * `configStore` est alimenté par `GET /config`, qui filtre par **liste blanche**
 * (`_PUBLIC_KEYS`, durcie le 26/07/2026 après une fuite de 31 clés). Ni
 * `archivage_delai_heures` ni `publie_visibilite_jours` n'y figurent — les deux
 * lectures rendaient `undefined` depuis toujours, et les deux écrans tournaient
 * sur leur valeur en dur.
 *
 * Le réglage de l'administration n'a donc **jamais** gouverné le calendrier ni le
 * tableau de bord. Personne ne s'en est aperçu : un défaut qui vaut la même chose
 * que le réglage courant est indiscernable d'un réglage qui fonctionne.
 *
 * ## Ce que ce module fait, et ce qu'il ne fait pas
 *
 * Il donne **un** défaut et **une** lecture. Il ne rend pas la clé publique — ce
 * serait exposer un réglage de plus sur un endpoint indexable pour un confort
 * d'affichage. La vraie sortie est que ces deux écrans cessent de calculer
 * l'archivage et lisent ce que l'API leur envoie, comme les annonces le font
 * déjà (`"archivee": est_archivee(...)`). C'est le reste de #515 ; en attendant,
 * l'écart est ici, écrit, à un seul endroit.
 *
 * ⚠️ `DELAI_ARCHIVAGE_JOURS` est une **copie** de `ARCHIVAGE_DELAI_JOURS`
 * (`api/app/utils/archivage.py`). Les contextes de build sont `./api` et
 * `./front` : rien de la racine n'entre dans les images, le partage d'un fichier
 * est impossible, seule la copie l'est.
 */
import type { Readable } from 'svelte/store';

/** Le défaut du site, en jours. Copie assumée de la valeur serveur. */
export const DELAI_ARCHIVAGE_JOURS = 30;

/**
 * Le délai en vigueur, en jours.
 *
 * Lit `archivage_delai_jours` s'il est disponible, puis l'ancien
 * `publie_visibilite_jours` — et jamais `archivage_delai_heures`, qui vaut 48 h
 * et ferait basculer les écrans à deux jours (même arbitrage que
 * `seuil_archivage_jours` côté API).
 */
export function delaiArchivageJours(config: Record<string, string> | null | undefined): number {
	const unique = parseInt(config?.['archivage_delai_jours'] ?? '');
	if (Number.isFinite(unique) && unique > 0) return unique;
	const ancien = parseInt(config?.['publie_visibilite_jours'] ?? '');
	if (Number.isFinite(ancien) && ancien > 0) return ancien;
	return DELAI_ARCHIVAGE_JOURS;
}

/** Le même délai en millisecondes — ce que manipulent les comparaisons de dates. */
export function delaiArchivageMs(config: Record<string, string> | null | undefined): number {
	return delaiArchivageJours(config) * 86_400_000;
}

/**
 * Un événement du calendrier est-il passé aux Archives ?
 *
 * ⚠️ Vivait dans `calendrier/+page.svelte` sous le nom `isExpired`, avec un
 * **défaut de 48 h en dur** — le dernier des quatre nombres qui répondaient à
 * la même question. Le déclencheur est la **fin** de l'événement (ou son début
 * s'il n'a pas de fin), conformément à l'arbitrage du 19/08/2026 : *« Calendrier
 * = après la date de l'événement »*.
 *
 * ⚠️ Ne connaît ni `archivee` (archivage manuel) ni `statut_kanban` : l'écran
 * les teste séparément. Le pendant serveur, `REGLES["evenement"]`, les intègre —
 * et c'est lui qui fera foi le jour où le calendrier lira l'état que l'API lui
 * envoie plutôt que de le recalculer (le reste de #515).
 */
export function evenementArchive(
	ev: { debut?: string | Date; fin?: string | Date | null },
	delaiMs: number,
): boolean {
	const fin = new Date((ev.fin ?? ev.debut) as string | Date);
	return fin.getTime() + delaiMs < Date.now();
}

//  Réexport de commodité pour les écrans qui n'ont pas besoin du store : évite
//  qu'ils réécrivent `30` en dur, ce qui est exactement le point de départ.
export type ConfigLisible = Readable<Record<string, string>>;
