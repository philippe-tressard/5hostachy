/**
 * Le vocabulaire des petites annonces — types, catégories, statuts et leurs rendus.
 *
 * Extrait de `routes/(app)/sondages/+page.svelte` le 14/08/2026 : cette page porte
 * TROIS rubriques (sondages, boîte à idées, petites annonces) et dépassait les
 * 1 000 lignes, deux fois le plafond de modularité (rang 1 §4). La règle est « au
 * fil de l'eau » — on découpe le fichier quand on y touche, et le contrôle de CI
 * refuse qu'il grossisse encore.
 *
 * Ces tables vivent ici plutôt que dans `AnnonceCard.svelte` parce qu'elles sont
 * lues des deux côtés : la carte les rend, la page en fait ses filtres et son
 * formulaire de dépôt. Les laisser dans le composant aurait obligé la page à les
 * recopier — la duplication que tout le reste du projet passe son temps à défaire.
 *
 * ⚠️ Emojis en `\u{…}` : hors du plan multilingue de base, ils survivent mal aux
 * allers-retours d'encodage sous Windows (cf. skill `svelte-patterns`).
 */

export const MAX_PHOTOS_ANNONCE = 5;

export const TYPES_ANNONCE = [
	{ val: 'vente', label: '\u{1F3F7}️ Vente' },
	{ val: 'don', label: '\u{1F381} Don' },
	{ val: 'recherche', label: '\u{1F50D} Recherche' },
];

export const CATEGORIES_ANNONCE = [
	{ val: 'appartement', label: '\u{1F3E0} Appartement' },
	{ val: 'parking_cave', label: '\u{1F17F}️ Parking / Cave' },
	{ val: 'mobilier', label: '\u{1F6CB}️ Mobilier' },
	{ val: 'electromenager', label: '\u{1FAD9} Électroménager' },
	{ val: 'high_tech', label: '\u{1F4BB} High-tech' },
	{ val: 'vehicule', label: '\u{1F697} Véhicule' },
	{ val: 'vetements', label: '\u{1F457} Vêtements' },
	{ val: 'services', label: '\u{1F6E0}️ Services' },
	{ val: 'divers', label: '\u{1F4E6} Divers' },
];

export const STATUTS_ANNONCE = [
	{ val: 'disponible', label: 'Disponible' },
	{ val: 'reserve', label: 'Réservé' },
	{ val: 'vendu', label: 'Vendu / Donné' },
	{ val: 'archive', label: 'Archiver' },
];

export function typeAnnonceLabel(val: string) {
	return TYPES_ANNONCE.find((t) => t.val === val)?.label ?? val;
}

export function categorieAnnonceLabel(val: string) {
	return CATEGORIES_ANNONCE.find((c) => c.val === val)?.label ?? val;
}

export function typeAnnonceClass(val: string) {
	return (
		({ vente: 'badge-blue', don: 'badge-green', recherche: 'badge-orange' } as Record<string, string>)[val] ??
		'badge-gray'
	);
}

export function statutAnnonceClass(val: string) {
	return (
		({
			disponible: 'badge-green',
			reserve: 'badge-orange',
			vendu: 'badge-gray',
			archive: 'badge-gray',
		} as Record<string, string>)[val] ?? 'badge-gray'
	);
}
