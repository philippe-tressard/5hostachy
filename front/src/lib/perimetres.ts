/**
 * Périmètres — le rendu, sans table.
 *
 * ## Ce que ce module remplace
 *
 * `lib/utils.ts` portait `PERIMETRE_LABELS`, une table de libellés écrite en dur
 * et arrêtée à `bat:4`, quand l'API allait jusqu'à `bat:9` : un cinquième bâtiment
 * s'affichait « Bât. 5 » côté serveur et **`bat:5` brut** à l'écran. Trois copies
 * s'étaient installées autour (#316), toutes correctes, toutes divergentes à terme.
 *
 * L'arborescence vit désormais en base et s'édite depuis l'administration. Ce
 * module n'en garde qu'un **cache d'affichage**, rempli par
 * `stores/perimetres.ts` au démarrage.
 *
 * ## Pourquoi un module à part, sans aucun import
 *
 * `perimetreLabel()` est appelée dans une quinzaine de gabarits, en plein milieu
 * du rendu : elle doit rester **synchrone**. La rendre asynchrone aurait imposé de
 * réécrire chacun de ces appels. Elle lit donc une carte de module, et le store
 * s'occupe de la remplir — c'est le store qui connaît l'API, pas l'inverse.
 *
 * N'importer rien ici est délibéré : `lib/utils.ts` réexporte `perimetreLabel`, et
 * une dépendance vers `$lib/api` créerait un cycle avec les modules qui importent
 * `utils`.
 */

/** Un nœud de l'arborescence, tel que `GET /perimetres` le rend. */
export interface Perimetre {
	id: number;
	code: string;
	parent: string | null;
	libelle: string;
	libelle_court: string;
	description: string;
	icone: string | null;
	batiment_id: number | null;
	profondeur: number;
	ordre: number;
	actif: boolean;
	portee_globale: boolean;
	concerne_tous: boolean;
	selectionnable: boolean;
	/**  Cet espace est-il PRIVATIF — un logement, une cave, une place attribuée —
	 *   par opposition aux parties communes ? Administré depuis Admin →
	 *   Patrimoine, jamais deviné d'après le libellé : chaque copropriété nomme
	 *   ses espaces comme elle veut (31/08/2026).
	 *
	 *   ⚠️ **Purement visuel pour l'instant.** La pastille se distingue, rien
	 *   d'autre ne change — ni qui voit, ni qui est notifié. */
	privatif: boolean;
	utilise: boolean;
}

const PREFIXE_BATIMENT = 'bat:';

let carte: Record<string, Perimetre> = {};
let ordreCodes: string[] = [];
let codeDefaut: string | null = null;

const cle = (code: string) => (code ?? '').trim().toLowerCase();

/**
 * Remplit le cache d'affichage. Appelé par `stores/perimetres.ts`, nulle part ailleurs.
 */
export function definirPerimetres(liste: Perimetre[]): void {
	carte = Object.fromEntries(liste.map((n) => [cle(n.code), n]));
	ordreCodes = liste.map((n) => n.code);
	//  Le périmètre « tout le monde » est une DONNÉE, pas la chaîne « résidence »
	//  écrite dans le code : une autre copropriété peut l'avoir renommé ou supprimé.
	//  C'est la racine à portée globale la plus prioritaire, comme côté serveur
	//  (`api/app/utils/perimetres.py`, `code_par_defaut`).
	const racines = liste.filter((n) => n.parent === null && n.portee_globale && n.actif);
	codeDefaut = racines.length ? racines[0].code : null;
}

/** L'arborescence connue, dans l'ordre d'affichage rendu par l'API. */
export function tousLesPerimetres(): Perimetre[] {
	return ordreCodes.map((c) => carte[cle(c)]).filter(Boolean);
}

export function noeudPerimetre(code: string): Perimetre | undefined {
	return carte[cle(code)];
}

/**
 * Le code du périmètre qui représente un bâtiment donné.
 *
 * Six endroits du front construisaient `` `bat:${batiment_id}` `` à la main —
 * la convention de nommage du seed recopiée en dur, alors que l'administration
 * peut créer un bâtiment sous n'importe quel code. On interroge l'arbre.
 *
 * Retombe sur la convention si l'arborescence n'est pas encore chargée : c'est un
 * affichage, et le libellé se corrigera au chargement.
 */
export function perimetreDuBatiment(batimentId: number | null | undefined): string {
	if (batimentId === null || batimentId === undefined) return perimetreParDefaut() ?? '';
	const trouve = tousLesPerimetres().find((n) => n.batiment_id === batimentId && n.actif);
	return trouve ? trouve.code : `${PREFIXE_BATIMENT}${batimentId}`;
}

/** Le code qui désigne « toute la copropriété », ou `null` sur un arbre vide. */
export function perimetreParDefaut(): string | null {
	return codeDefaut;
}

/**
 * La sélection initiale d'un formulaire — « toute la copropriété ».
 *
 * Les pages écrivaient `['résidence']` en dur, une trentaine de fois. Sur une
 * copropriété qui renomme ou supprime ce nœud, chacune de ces occurrences aurait
 * produit un périmètre inexistant, sans erreur visible : le formulaire se serait
 * ouvert sur une pastille morte. Liste vide sur un arbre vide, ce que le serveur
 * traite déjà comme « concerne tout le monde ».
 */
export function perimetreDefautListe(): string[] {
	return codeDefaut ? [codeDefaut] : [];
}

/**
 * Cette sélection désigne-t-elle toute la copropriété ?
 *
 * Remplace les comparaisons `=== 'résidence'` semées dans les pages, qui
 * cesseraient d'être vraies dès qu'une copropriété renomme ou supprime ce nœud.
 * Une liste vide vaut « tout le monde », comme côté serveur.
 */
export function estPerimetreParDefaut(items: string[] | string | null | undefined): boolean {
	const liste = normaliser(items);
	if (liste.length === 0) return true;
	return liste.length === 1 && codeDefaut !== null && cle(liste[0]) === cle(codeDefaut);
}

function normaliser(items: string[] | string | null | undefined): string[] {
	const liste = typeof items === 'string' ? items.split(',') : (items ?? []);
	return liste.map((i) => (i ?? '').trim()).filter(Boolean);
}

/** Sépare deux éléments de même niveau : « Bât. 1 · Parking ». */
export const SEPARATEUR_ELEMENT = ' · ';

/**
 * Borne un GROUPE de plusieurs espaces partageant le même parent :
 * « Bât. 4 › Logement · Jardin Bâtiment — AFUL › Voie d'accès » (27/08/2026,
 * signalé à l'écran).
 *
 * Sans lui, le « · » qui sépare les deux espaces du bâtiment 4 se lit comme celui
 * qui introduit AFUL, et « AFUL › Voie d'accès » paraît être un troisième espace
 * du bâtiment. Il n'apparaît QUE là où le « · » deviendrait ambigu — c'est-à-dire
 * dès qu'un des deux groupes voisins compte plusieurs éléments. Deux groupes d'un
 * seul élément portent chacun leur chemin complet et se lisent sans lui :
 * « Bât. 3 › Toit · Bât. 4 › Toit » ne change pas.
 */
export const SEPARATEUR_GROUPE = ' — ';

/**
 * Un nœud d'ORGANISATION : une racine qui ne se cible pas (« Bâtiments »).
 *
 * Il ne qualifie pas ses enfants — « Bâtiments › Bât. 4 » n'apprend rien et allonge
 * tout. Même définition que dans `PerimetrePicker.svelte` (`estGroupeRacine`), et
 * les deux doivent le rester : ce qui fait une pastille de premier niveau à la
 * saisie est exactement ce qui ne se préfixe pas à la lecture.
 */
function estGroupeRacine(n: Perimetre | undefined): boolean {
	return !!n && n.parent === null && !n.selectionnable;
}

/**
 * Le parent qui doit précéder ce nœud dans son libellé, ou `undefined`.
 *
 * 🔴 **La qualification ne s'arrête PLUS aux bâtiments** (27/08/2026, signalé à
 * l'écran). La version précédente exigeait `parent.batiment_id != null`, en
 * s'appuyant sur ceci, qui était écrit juste au-dessus d'elle : *« les enfants du
 * parking, des espaces verts ou des locaux techniques portent déjà des libellés
 * distincts (Places, Chaufferie…) : les préfixer allongerait sans lever
 * d'ambiguïté »*.
 *
 * C'était vrai **du seed, et de lui seul**. Rien n'impose la même discipline aux
 * nœuds créés depuis `/admin/patrimoine` : une « Voie d'accès » ajoutée sous AFUL
 * s'affichait nue sur le fil, sur la carte de ticket et dans la relance syndic —
 * alors que le sélecteur, lui, écrivait bien « AFUL › Voie d'accès ». Le même objet
 * avait donc deux écritures contradictoires selon l'écran, ce que le cadre
 * d'interface interdit ; et devant cet écart c'est la LECTURE qui avait tort, elle
 * perdait une information que la saisie affichait déjà.
 *
 * La condition porte donc sur ce que le parent EST — une cible, ou un simple
 * regroupement — et non sur ce qu'il contient.
 */
function parentQualifiant(n: Perimetre): Perimetre | undefined {
	const parent = n.parent ? carte[cle(n.parent)] : undefined;
	return parent && !estGroupeRacine(parent) ? parent : undefined;
}

/**
 * Le libellé ABRÉGÉ (« Bât. 3 »), employé en position de préfixe : le long
 * (« Bâtiment 3 ») allongerait un badge déjà à deux niveaux.
 */
function court(n: Perimetre): string {
	return n.libelle_court || n.libelle;
}

/**
 * Le chemin d'`ordre` de la racine jusqu'au nœud — sa position dans l'arbre.
 *
 * ⚠️ `ordre` n'est unique qu'entre FRÈRES : le seed donne 0 à « Copropriété
 * entière » comme au premier bâtiment. Trier sur ce seul entier mélangerait les
 * niveaux. Le chemin, lui, se compare terme à terme comme un numéro de chapitre :
 * `[10]` < `[10,0]` < `[20]`. Un parent précède ses enfants, et deux enfants d'un
 * même parent restent **contigus** — ce dont le regroupement de `perimetreLabel`
 * dépend entièrement.
 *
 * La remontée est bornée par `vus` : une boucle dans l'arbre ne doit pas figer
 * l'interface (même garde-fou que `batimentsCibles`).
 */
function cheminOrdre(n: Perimetre): number[] {
	const chemin: number[] = [];
	const vus = new Set<string>();
	let courant: Perimetre | undefined = n;
	while (courant && !vus.has(cle(courant.code))) {
		chemin.unshift(courant.ordre ?? 0);
		vus.add(cle(courant.code));
		courant = courant.parent ? carte[cle(courant.parent)] : undefined;
	}
	return chemin;
}

/** `-1` pour la position absente : un parent passe avant ses enfants. */
function comparerChemins(a: number[], b: number[]): number {
	for (let i = 0; i < Math.max(a.length, b.length); i++) {
		const x = a[i] ?? -1;
		const y = b[i] ?? -1;
		if (x !== y) return x - y;
	}
	return 0;
}

/**
 * Libellé d'un périmètre isolé. Ne rend jamais un code brut à l'écran.
 *
 * 🔴 **Un espace est QUALIFIÉ par son parent** — « Bât. 3 › Toit », « AFUL › Voie
 * d'accès », « Parking › Portail d'accès ». Le gabarit pose les mêmes neuf espaces
 * sous chaque bâtiment, si bien qu'un ticket ciblant les toits de deux bâtiments
 * affichait « Toit · Toit · Bâtiment 3 » (18/08/2026) ; et un espace créé sous un
 * nœud transverse s'affichait nu (27/08/2026). Le détail de la règle et de son
 * élargissement est dans `parentQualifiant`.
 *
 * C'est la même écriture que le résumé des pastilles du sélecteur — un objet se lit
 * partout de la même façon (R3).
 */
export function perimetreLabelUn(code: string): string {
	const n = carte[cle(code)];
	if (n) {
		const parent = parentQualifiant(n);
		return parent ? `${court(parent)} › ${n.libelle}` : n.libelle;
	}
	//  Repli d'affichage, identique à celui du serveur : un contenu peut citer un
	//  nœud supprimé depuis, et l'arborescence peut n'être pas encore chargée.
	//  Ce n'est PAS une source de vérité — la convention `bat:N` est posée par le
	//  seed, l'arbre reste seul juge.
	if (code && cle(code).startsWith(PREFIXE_BATIMENT)) {
		return `Bât. ${code.slice(PREFIXE_BATIMENT.length)}`;
	}
	return code;
}

/**
 * Périmètres → libellé affichable, **trié puis regroupé par parent**.
 * Ex : ['bat:1','parking'] → 'Bât. 1 · Parking'
 *
 * Accepte les DEUX formes que porte réellement le produit : le tableau
 * `perimetre_cible` (publications, tickets) et la chaîne `perimetre` des
 * événements. Le calendrier réimplémentait la fonction pour cette seule raison,
 * avec une table recopiée à l'identique — une correction faite ici ne l'atteignait
 * pas (#316).
 *
 * 🔴 **L'ordre affiché ne suit plus l'ordre des clics** (27/08/2026, signalé à
 * l'écran). Les codes sont stockés dans l'ordre où l'utilisateur a touché les
 * pastilles (`PerimetrePicker`, `value = [...s]`), et personne ne les triait
 * ensuite : deux espaces d'un même bâtiment se retrouvaient séparés par un
 * périmètre étranger, et le bâtiment répété —
 *
 *     Bât. 4 › Logement · Voie d'accès · Bât. 4 › Jardin Bâtiment
 *
 * On trie par la position dans l'arbre, on fusionne les éléments contigus qui
 * partagent un parent qualifiant, et on rend :
 *
 *     Bât. 4 › Logement · Jardin Bâtiment — AFUL › Voie d'accès
 *
 * Les codes INCONNUS de l'arbre (nœud supprimé depuis, arborescence pas encore
 * chargée) sont conservés — un contenu ne perd pas son badge — mais rangés à la
 * fin, dans leur ordre d'origine : ils n'ont pas de position dans un arbre où ils
 * ne figurent plus.
 *
 * Le `trim()` de `normaliser` n'est pas cosmétique : sur `'bat:1, parking'`, une
 * clé avec espace de tête ne correspond à rien et ressortirait brute à l'écran.
 */
export function perimetreLabel(items: string[] | string | null | undefined): string {
	const codes = normaliser(items);
	const connus = codes.map((c) => carte[cle(c)]).filter(Boolean);
	const inconnus = codes.filter((c) => !carte[cle(c)]);
	connus.sort((a, b) => comparerChemins(cheminOrdre(a), cheminOrdre(b)));

	//  Un « groupe » = des éléments CONTIGUS partageant le même parent qualifiant.
	//  Contigus suffit : le tri par chemin garantit qu'aucun nœud étranger ne peut
	//  s'intercaler entre deux enfants d'un même parent.
	const groupes: { parent?: Perimetre; libelles: string[] }[] = [];
	for (const n of connus) {
		const parent = parentQualifiant(n);
		const dernier = groupes[groupes.length - 1];
		if (dernier && parent && dernier.parent === parent) dernier.libelles.push(n.libelle);
		else groupes.push({ parent, libelles: [n.libelle] });
	}
	for (const c of inconnus) groupes.push({ parent: undefined, libelles: [perimetreLabelUn(c)] });

	return groupes
		.map((g, i) => {
			const corps = g.libelles.join(SEPARATEUR_ELEMENT);
			const rendu = g.parent ? `${court(g.parent)} › ${corps}` : corps;
			if (i === 0) return rendu;
			//  Le séparateur fort UNIQUEMENT là où le « · » deviendrait ambigu :
			//  dès que l'un des deux groupes voisins en contient déjà un.
			const ambigu = groupes[i - 1].libelles.length > 1 || g.libelles.length > 1;
			return (ambigu ? SEPARATEUR_GROUPE : SEPARATEUR_ELEMENT) + rendu;
		})
		.join('');
}

/**
 * L'un de ces périmètres concerne-t-il tous les résidents ?
 *
 * Miroir de `a_portee_globale` côté serveur. L'héritage est déjà résolu par l'API,
 * qui rend `concerne_tous` pour chaque nœud — inutile de remonter l'arbre ici.
 *
 * Remplace la liste `['résidence','parking','cave','aful']` que le tableau de bord
 * portait en dur, troisième copie d'une même énumération.
 */
export function concerneTous(items: string[] | string | null | undefined): boolean {
	return normaliser(items).some((c) => carte[cle(c)]?.concerne_tous === true);
}

/**
 * Les bâtiments réellement visés — celui du nœud, ou du plus proche ancêtre qui en
 * porte un. C'est ce qui fait que « Bât. 2 › Hall d'entrée » concerne le bâtiment 2
 * sans que le hall ait à le répéter.
 *
 * Miroir de `batiments_cibles` côté serveur. La remontée est bornée par `vus` : une
 * boucle dans l'arbre ne doit pas figer l'interface.
 */
export function batimentsCibles(items: string[] | string | null | undefined): number[] {
	const cibles = new Set<number>();
	for (const code of normaliser(items)) {
		let courant = carte[cle(code)];
		const vus = new Set<string>();
		while (courant && !vus.has(cle(courant.code))) {
			if (courant.batiment_id !== null) {
				cibles.add(courant.batiment_id);
				break;
			}
			vus.add(cle(courant.code));
			courant = courant.parent ? carte[cle(courant.parent)] : undefined!;
		}
	}
	return [...cibles];
}

/**
 * Icônes proposées pour un périmètre, dans l'écran d'administration.
 *
 * Volontairement **courte et thématique** : un choix de cinquante icônes ne se
 * parcourt pas, il se subit. Chacune doit dire quelque chose d'un lieu de
 * copropriété — et toutes existent dans `Icon.svelte`, sans quoi la pastille
 * s'afficherait avec le point d'interrogation du repli.
 */
export const ICONES_PERIMETRE: { nom: string; libelle: string }[] = [
	{ nom: 'building-2', libelle: 'Bâtiment' },
	{ nom: 'home', libelle: 'Copropriété' },
	{ nom: 'door-closed', libelle: 'Hall, porte' },
	{ nom: 'stairs', libelle: 'Escalier' },
	{ nom: 'layers', libelle: 'Paliers, étages' },
	{ nom: 'arrow-up-down', libelle: 'Ascenseur' },
	{ nom: 'box', libelle: 'Cave, stockage' },
	{ nom: 'car', libelle: 'Parking' },
	{ nom: 'square-parking', libelle: 'Parking public' },
	{ nom: 'trees', libelle: 'Espaces verts' },
	{ nom: 'sprout', libelle: 'Jardin' },
	{ nom: 'footprints', libelle: 'Cheminement' },
	{ nom: 'lightbulb', libelle: 'Éclairage' },
	{ nom: 'zap', libelle: 'Électricité' },
	{ nom: 'droplet', libelle: 'Eau' },
	{ nom: 'flame', libelle: 'Chauffage' },
	{ nom: 'warehouse', libelle: 'Local technique' },
	{ nom: 'wrench', libelle: 'Entretien' },
	{ nom: 'settings', libelle: 'Divers technique' },
];

/**
 * Le périmètre dont HÉRITE une nouvelle entrée d'historique.
 *
 * 🔴 Signalé à l'écran le 31/08/2026 :
 *
 * > *« quand on fait un commentaire sur un Ticket, par défaut le périmètre du
 * > dernier commentaire (ou du ticket original si 1er commentaire) n'est pas
 * > conservé »*
 *
 * Le formulaire proposait « Copropriété entière » sur un ticket situé « Bât. 1 ›
 * Escaliers ». Il ne mentait pas sur ce qui allait s'écrire — le serveur ne
 * touche à rien quand le champ est vide — mais il **montrait un choix par défaut
 * qui n'était pas celui qui s'appliquerait**, ce qui revient au même pour qui
 * lit l'écran.
 *
 * ⚠️ L'héritage remonte les entrées, il ne prend pas seulement le ticket : une
 * entrée a pu resserrer le périmètre — « on a trouvé d'où vient la fuite » — et
 * c'est ce resserrement, le plus récent, qui vaut ensuite. Prendre le ticket
 * ferait revenir en arrière à chaque commentaire.
 *
 * ⚠️ Une entrée qui ne dit RIEN du périmètre ne compte pas : elle n'a rien
 * précisé, donc elle n'a rien changé. C'est le sens de la valeur vide, et c'est
 * ce qui permet à un courriel d'afficher « 🔹 … » sur une entrée pour dire
 * qu'elle a précisé quelque chose.
 *
 * @param perimetreObjet le périmètre de l'objet porteur (ticket, événement…)
 * @param entrees        l'historique, dans l'ordre CHRONOLOGIQUE
 */
export function perimetreHerite(
	perimetreObjet: string[] | null | undefined,
	entrees: { perimetre_cible?: string[] | null }[] = [],
): string[] {
	for (let i = entrees.length - 1; i >= 0; i--) {
		const precise = entrees[i]?.perimetre_cible;
		if (precise && precise.length) return [...precise];
	}
	return [...(perimetreObjet ?? [])];
}

/**
 * Deux périmètres désignent-ils la même chose ? **L'ORDRE ne compte pas.**
 *
 * Le sélecteur mémorise l'ordre des clics ; deux mêmes zones cochées dans un
 * autre ordre sont le même périmètre. C'est déjà la règle de `perimetreLabel`,
 * qui trie avant de rendre — la comparer autrement ferait diverger l'affichage
 * et la décision.
 *
 * ⚠️ Employé pour n'envoyer `perimetre_cible` que s'il DIFFÈRE de l'hérité : une
 * comparaison sensible à l'ordre ferait déclarer un resserrement à chaque
 * commentaire où l'on aurait décoché puis recoché la même zone.
 */
export function memePerimetre(a: string[], b: string[]): boolean {
	return a.length === b.length && [...a].sort().join('|') === [...b].sort().join('|');
}
