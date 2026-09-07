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
 * ## ✅ Le CALENDRIER n'appelle plus ce module (02/09/2026)
 *
 * Ce fichier annonçait sa propre sortie : *« la vraie sortie est que ces deux
 * écrans cessent de calculer l'archivage et lisent ce que l'API leur envoie »*.
 * C'est fait pour le calendrier — `evenementArchive()` a été **supprimée**, et
 * l'écran lit `e.archivee`, calculé par `app/utils/archivage.py`.
 *
 * Trois écarts sont tombés avec elle : l'annulation devient immédiate, l'épinglage
 * protège, et surtout **le réglage de l'administration gouverne enfin le
 * calendrier** — ce qu'il n'avait jamais fait, la clé n'étant pas publique.
 *
 * ⚠️ **Le tableau de bord, lui, appelle encore `delaiArchivageMs`** pour son seuil
 * « récent ». Il reste donc sur le défaut en dur, pour la même raison qu'avant : la
 * clé n'est pas publiée, et la publier serait exposer un réglage de plus sur un
 * endpoint anonyme pour un confort d'affichage. Sa sortie est la même que celle du
 * calendrier — lire ce que l'API envoie — et elle n'est pas encore faite.
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

//  Réexport de commodité pour les écrans qui n'ont pas besoin du store : évite
//  qu'ils réécrivent `30` en dur, ce qui est exactement le point de départ.
export type ConfigLisible = Readable<Record<string, string>>;
