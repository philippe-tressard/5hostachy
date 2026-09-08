/**
 * Supprime toutes les balises HTML d'une chaîne.
 * Utilisé pour générer des aperçus texte depuis un contenu HTML riche (TipTap).
 * Compatible SSR (pas de dépendance DOM).
 */
export function stripHtml(html: string): string {
	return html
		.replace(/<[^>]*>/g, '')
		.replace(/&nbsp;/g, ' ')
		.replace(/&amp;/g, '&')
		.replace(/&lt;/g, '<')
		.replace(/&gt;/g, '>')
		.replace(/&quot;/g, '"')
		.trim();
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
	if (e && typeof e === 'object' && 'message' in e)
		return String((e as { message?: unknown }).message ?? fallback);
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

/**
 * Relie un calcul SANS dépendance réactive à ce qui doit le déclencher.
 *
 * ```svelte
 * $: minuit = relire(contrats, minuitDuJour);
 * ```
 *
 * 🔴 **Le défaut qu'il corrige.** Un `$:` ne se réexécute que si l'une des
 * variables réactives qu'il cite change. `$: annee = anneeCourante()` n'en cite
 * aucune : Svelte l'exécute une fois et plus jamais. La ligne a **l'air**
 * réactive, elle vaut un `const`, et aucune relecture ne peut le voir — c'est
 * `svelte/no-immutable-reactive-statements` qui l'a trouvé (#549, 29/08/2026).
 *
 * Quatre écritures en souffraient, dont deux avec, juste au-dessus, le
 * commentaire décrivant le rafraîchissement qui n'avait pas lieu :
 *
 * | Écran | Ce qui était figé | Ce que ça donnait |
 * |---|---|---|
 * | Reporting (×3) | l'année de référence | un onglet ouvert la nuit du réveillon annonçait les échéances de l'année passée — le commentaire disait l'empêcher |
 * | Prestataires | minuit du jour | un onglet ouvert la veille classait « en retard » ce qui devenait dû le lendemain |
 * | Sélecteur de périmètre | le périmètre par défaut | `perimetreParDefaut()` lit un état de module posé au chargement de l'arbre : avant lui, `null`, et pour toujours |
 * | Tableau de bord | la salutation | « Bonjour » à 20 h |
 *
 * ⚠️ **`dependance` n'est pas lue, et c'est tout son objet** : elle dit à Svelte
 * de quoi le calcul dépend. La citer est le geste, pas un effet de bord.
 *
 * ⚠️ **Ce n'est pas une horloge.** Le rechargement des données est le seul
 * moment où la page apprend que le temps a passé ; un onglet ouvert et immobile
 * reste en retard. Poser un `setInterval` pour ces quatre cas coûterait plus
 * qu'il ne rapporte — ce qui change est qu'une navigation suffit à corriger.
 */
export function relire<T>(dependance: unknown, calcul: () => T): T {
	void dependance;
	return calcul();
}

/**
 * Les numéros de téléphone d'un champ libre — découpés, nettoyés, DÉDOUBLONNÉS.
 *
 * 🔴 Écrit deux fois avant le 03/09/2026 : `splitTels()` dans les prestataires,
 * et `m.telephone.split(',').filter((t) => t.trim())` recopié dans l'annuaire.
 * Deux écritures de la même notion, qui auraient divergé au premier changement
 * de séparateur.
 *
 * ⚠️ Le dédoublonnage est ce qui manquait aux deux, et il règle DEUX choses à la
 * fois :
 *
 * 1. **le rendu** — un numéro saisi deux fois dans le même champ s'affichait
 *    deux fois, sans que personne y voie autre chose qu'une saisie maladroite ;
 * 2. **la clé de liste** — sans unicité, `{#each … as tel (tel)}` fait lever
 *    `each_key_duplicate` à Svelte et **l'écran entier tombe**. C'est pourquoi
 *    ces cinq boucles étaient restées sans clé : la corriger par la forme aurait
 *    été plus dangereux que le défaut. Dédoublonner à la SOURCE rend la clé
 *    sûre, au lieu de choisir entre les deux.
 */
export function telephonesDe(champ: string | null | undefined): string[] {
	if (!champ) return [];
	const vus = new Set<string>();
	for (const brut of champ.split(',')) {
		const numero = brut.trim();
		if (numero) vus.add(numero);
	}
	return [...vus];
}

/**
 * Libellé français du type d'un lot — « Appartement », « Parking », « Cave ».
 *
 * 🔴 Écrit dans `mon-lot/+page.svelte`, où un commentaire signalait déjà le
 * piège : *« `lotLabel` s'appuie sur `lotTypeLabel`, qui sert encore à
 * l'affichage des accès plus bas. L'emporter dans le composant en aurait fait
 * une deuxième écriture. »* L'extraction de `ModaleAccesBail` (#779) est
 * exactement le geste que ce commentaire redoutait — d'où le passage ici,
 * plutôt qu'une copie de plus.
 *
 * ⚠️ Une valeur inconnue est rendue TELLE QUELLE, pas remplacée par « — » : un
 * type ajouté côté API doit s'afficher, fût-ce sans majuscule, plutôt que
 * disparaître derrière un tiret que personne ne saura interpréter.
 */
export function lotTypeLabel(t: string | null | undefined): string {
	if (!t) return '—';
	if (t === 'appartement') return 'Appartement';
	if (t === 'parking') return 'Parking';
	if (t === 'cave') return 'Cave';
	return t;
}

/**
 * Le libellé d'un étage — « RDC », « 1er », « 2ème », « SS 1 ».
 *
 * 🔴 Écrit **six fois** dans trois écrans, en **trois rendus différents** (#835,
 * 08/09/2026) :
 *
 * | Écran | Rendu d'un sous-sol | Rendu du 2ᵉ |
 * |---|---|---|
 * | `mon-lot` (4 fois) | `-1` | `2` |
 * | `profil` | `SS 1` | `2ème étage` |
 * | `tableau-de-bord` | `-1` | `2ème` |
 *
 * Le même lot s'affichait donc « -1 » sur un écran et « SS 1 » sur un autre. Ce
 * n'est pas une variante de présentation assumée : c'est ce que trois personnes
 * ont écrit séparément en croyant chacune être seule.
 *
 * ⚠️ Le **suffixe** est laissé à l'appelant (`suffixe: false` par défaut). Une
 * ligne de définition affiche « Étage : 2ème » — répéter le mot dans la valeur
 * donnerait « Étage : 2ème étage ». Un fil de texte, lui, en a besoin. C'est la
 * seule divergence légitime des six, et elle devient un paramètre plutôt qu'une
 * copie.
 *
 * ⚠️ `null` et `undefined` rendent une chaîne **vide**, pas « — » : l'appelant
 * décide de ce qu'il affiche à la place, et plusieurs entourent déjà la valeur
 * d'un `{#if}`.
 */
export function etageLabel(
	etage: number | null | undefined,
	{ suffixe = false }: { suffixe?: boolean } = {},
): string {
	if (etage === null || etage === undefined) return '';
	if (etage === 0) return 'RDC';
	if (etage < 0) return `SS ${Math.abs(etage)}`;
	const rang = etage === 1 ? '1er' : `${etage}ème`;
	return suffixe ? `${rang} étage` : rang;
}

/**
 * L'étage à PROPOSER dans un profil, d'après les lots du compte.
 *
 * Demandé le 08/09/2026 : *« Si mono lot, mettre l'étage de l'appartement par
 * défaut. »* Personne ne devrait ressaisir une information que le site détient
 * déjà — l'étage d'un lot vient du classeur de la copropriété.
 *
 * 🔴 **Trois conditions, et chacune retire un cas où la proposition serait
 * fausse :**
 *
 * 1. **le champ est vide** — une valeur saisie ne se remplace jamais par une
 *    déduction, même juste. C'est l'utilisateur qui a raison ;
 * 2. **un seul lot**, sinon on ne saurait pas lequel il habite. Choisir « le
 *    premier appartement » donnerait une réponse plausible et parfois fausse,
 *    ce qui est le pire des deux : personne ne la remettrait en cause ;
 * 3. **de type appartement** — un copropriétaire dont l'unique lot est un
 *    parking ou une cave **n'habite pas son lot**. Lui proposer « SS 1 » serait
 *    une réponse à côté de la question, et il la validerait sans y penser,
 *    parce qu'un champ prérempli se lit comme une information vérifiée.
 *
 * ⚠️ `0` est un étage — le rez-de-chaussée. D'où `=== null` et non `!etage` :
 * un test de vérité écraserait le RDC.
 *
 * ⚠️ Elle vit ici et non dans l'écran : c'est une règle du produit, et
 * `api/tests/test_etage_defaut_mono_lot.py` l'exerce depuis le dehors.
 */
export function etageParDefaut(
	etageSaisi: number | null | undefined,
	lots: { type?: string | null; etage?: number | null }[],
): number | null {
	if (etageSaisi !== null && etageSaisi !== undefined) return etageSaisi;
	if (lots.length !== 1 || lots[0].type !== 'appartement') return null;
	return lots[0].etage ?? null;
}
