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

/**
 * Périmètres — la table a disparu d'ici, et de partout ailleurs.
 *
 * `PERIMETRE_LABELS` vivait juste en dessous : sept clés écrites en dur, arrêtées
 * à `bat:4` quand l'API allait jusqu'à `bat:9`. Un cinquième bâtiment s'affichait
 * « Bât. 5 » côté serveur et **`bat:5` brut** à l'écran, et aucune description
 * n'existait nulle part.
 *
 * L'arborescence vit désormais en base et s'édite depuis l'administration
 * (`/admin/patrimoine`). Le rendu est dans `$lib/perimetres`, alimenté au
 * démarrage par `$lib/stores/perimetres`.
 *
 * Ces réexports existent pour que les cinq pages qui écrivent
 * `import { perimetreLabel } from '$lib/utils'` n'aient pas à changer : le chemin
 * d'import n'est pas la question que ce lot traite.
 */
export {
	perimetreLabel,
	perimetreLabelUn,
	estPerimetreParDefaut,
	perimetreParDefaut,
	perimetreDefautListe,
	perimetreDuBatiment,
	noeudPerimetre,
	tousLesPerimetres,
	concerneTous,
	batimentsCibles,
	type Perimetre,
} from '$lib/perimetres';

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

/**
 * Message d'une erreur d'API, ou un libellé de repli si elle n'en porte pas.
 *
 * `ApiError` expose `message`, mais un rejet réseau ou une exception de code n'en
 * portent pas toujours : lire `e.message` sans précaution affiche « undefined »
 * dans un toast — le seul endroit où l'utilisateur regarde quand ça a échoué.
 */
export function apiMessage(e: unknown, fallback = 'Erreur'): string {
	if (e && typeof e === 'object' && 'message' in e) return String((e as { message?: unknown }).message ?? fallback);
	return fallback;
}

/**
 * Une note sur 5 rendue en étoiles pleines et vides — `4` → `★★★★☆`.
 *
 * Écrite deux fois dans le dépôt (l'espace CS et la fiche prestataire) jusqu'au
 * 19/08/2026, sous le même nom et avec le même corps.
 */
export function starsDisplay(note: number): string {
	const pleines = Math.round(note);
	return '★'.repeat(pleines) + '☆'.repeat(5 - pleines);
}
