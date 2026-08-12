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

/**
 * Montant en euros — format français unique de l'application.
 *
 * `1234` → `1 234 €` · `1234.5` → `1 234,50 €` · `null` → `—`
 *
 * Avant ce helper, le même champ `montant_estime` était formaté de trois façons
 * différentes selon l'écran — parfois sur la même page : `{style:'currency'}`
 * (« 1 234,00 € »), `toLocaleString('fr-FR')` suivi d'un `€` littéral
 * (« 1 234 € »), et un `Intl.NumberFormat` local avec `maximumFractionDigits: 0`
 * (qui arrondissait « 1 234,50 » en « 1 235 € »).
 *
 * `minimumFractionDigits: 0` + `maximumFractionDigits: 2` : les centimes sont
 * affichés quand ils existent — donc aucun arrondi trompeur sur un montant de
 * devis — et masqués sur un montant entier. Le `—` pour une valeur absente suit la
 * convention de `lib/date.ts`.
 */
export function fmtMontant(v: number | null | undefined): string {
	if (v == null) return '—';
	return new Intl.NumberFormat('fr-FR', {
		style: 'currency',
		currency: 'EUR',
		minimumFractionDigits: 0,
		maximumFractionDigits: 2,
	}).format(v);
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
 *
 * Accepte les DEUX formes que porte réellement le produit : le tableau
 * `perimetre_cible` (publications, tickets) et la chaîne `perimetre` des
 * événements, que le modèle déclare `str` mais que le front recevait parfois
 * séparée par des virgules. Le calendrier réimplémentait la fonction pour cette
 * seule raison, avec une table de correspondance recopiée à l'identique — une
 * correction faite ici ne l'atteignait pas (#316).
 *
 * Le `trim()` n'est pas cosmétique : sur `'bat:1, parking'`, une clé avec espace
 * de tête ne correspond à rien et ressortirait brute à l'écran.
 */
export function perimetreLabel(items: string[] | string | null | undefined): string {
	const liste = typeof items === 'string' ? items.split(',') : (items ?? []);
	return liste
		.map((i) => (i ?? '').trim())
		.filter(Boolean)
		.map((i) => PERIMETRE_LABELS[i] ?? i)
		.join(' · ');
}

/**
 * État de la touche Verr. Maj., ou `null` si l'événement ne permet pas de le savoir.
 *
 * `getModifierState()` n'existe que sur les événements clavier et souris : un
 * `FocusEvent` ne l'a pas. Or les trois pages d'authentification câblaient le
 * même handler sur `on:focus` en plus de `on:keydown`/`on:keyup`, et il levait
 * donc une `TypeError` à chaque fois que l'utilisateur cliquait dans le champ
 * mot de passe — sur la connexion, l'inscription et la réinitialisation.
 *
 * Rendre `null` plutôt que lever : au focus, l'état des touches n'est tout
 * simplement pas connaissable, ce n'est pas une erreur. L'appelant conserve
 * alors la valeur qu'il avait.
 */
export function capsLockActif(e: KeyboardEvent | FocusEvent): boolean | null {
	const getModifierState = (e as KeyboardEvent).getModifierState;
	if (typeof getModifierState !== 'function') return null;
	return getModifierState.call(e, 'CapsLock');
}
