/**
 * Supprime toutes les balises HTML d'une chaîne.
 * Utilisé pour générer des aperçus texte depuis un contenu HTML riche (TipTap).
 * Compatible SSR (pas de dépendance DOM).
 */
export function stripHtml(html: string): string {
	return html.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').trim();
}

/**
 * Génère un aperçu texte tronqué depuis un contenu HTML.
 */
export function htmlPreview(html: string, maxLength = 150): string {
	const text = stripHtml(html);
	return text.length > maxLength ? text.slice(0, maxLength) + '…' : text;
}

/** Libellés canoniques des périmètres (cf. specs/design — pattern UX « Périmètre »). */
export const PERIMETRE_LABELS: Record<string, string> = {
	'résidence': 'Copropriété entière',
	'bat:1': 'Bât. 1', 'bat:2': 'Bât. 2', 'bat:3': 'Bât. 3', 'bat:4': 'Bât. 4',
	parking: 'Parking', cave: 'Cave', aful: 'AFUL',
};

/**
 * Périmètres → libellé affichable. Séparateur ` · ` (espace point-médian espace).
 * Ex : ['bat:1','parking'] → 'Bât. 1 · Parking'
 */
export function perimetreLabel(items: string[]): string {
	return (items ?? []).map((i) => PERIMETRE_LABELS[i] ?? i).join(' · ');
}
