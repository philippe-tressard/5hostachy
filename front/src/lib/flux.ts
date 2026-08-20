/**
 * Règles du fil d'activité — partagées par le tableau de bord et ses cartes.
 *
 * Tout ce qui décide de l'apparence ou du classement d'une ligne du fil vit ici,
 * et nulle part ailleurs. Les deux blocs de carte du fil (« récent » et
 * « ancien ») avaient dupliqué ces tables et ces helpers : chaque évolution
 * devait alors être écrite deux fois, et c'est ainsi qu'un bloc a fini par
 * afficher moins d'informations que l'autre.
 *
 * Le partage compte surtout pour les TROIS REGISTRES du fil (urgences /
 * épinglé / chronologie) : leurs filtres doivent rester mutuellement exclusifs.
 * Une seule fonction décide donc de chaque appartenance.
 */
import type { FluxItem } from '$lib/api';
import { estTicketClos } from '$lib/tickets';

// ── Apparence par type d'élément ──────────────────────────────────────────
//
// ⚠️ CES TROIS TABLES DOIVENT COUVRIR TOUS LES TYPES QUE L'API ÉMET.
//
// Elles n'en couvraient que dix pour quinze : `prestataire`, `document`,
// `diagnostic`, `faq` et `annuaire` — les cinq rubriques ajoutées au fil depuis —
// retombaient sur les valeurs par défaut, c'est-à-dire **gris de bordure sur fond
// gris**, illisible, avec le nom technique brut en guise de libellé
// (« PRESTATAIRE »). Signalé par l'utilisateur le 08/08/2026 ; personne ne
// l'avait vu parce qu'une pastille grise ressemble à une pastille.
// `api/tests/test_flux_apparence.py` échoue désormais si un type émis par le
// backend n'a pas ses trois entrées.
//
// CONTRASTE. Six des sept couleurs d'origine échouaient déjà au niveau AA
// (4.5:1) : l'ambre était à 2,07 et l'émeraude à 2,41 — le gris sur gris à 1,15
// n'était que le cas extrême. Les textes sont passés en teintes foncées (700/800)
// sur des fonds clairs (50) : les douze sont désormais entre 4,75 et 10,2.
//
// DIFFÉRENCIATION. Les douze teintes sont réparties sur la roue, écart minimal
// 17°, sauf `devis` ⇄ `prestataire` (12°) — volontaire : ce sont les deux
// rubriques de la page /prestataires, leur parenté se lit.
export const TYPE_LABELS: Record<string, string> = {
	ticket_resolu: 'Ticket résolu', ticket_ouvert: 'Ticket', ticket_mis_a_jour: 'Ticket mis à jour',
	publication: 'Actualité', evenement: 'Événement',
	devis: 'Devis', sondage_clos: 'Sondage clos', sondage_ouvert: 'Sondage',
	annonce: 'Petite annonce', idee: 'Boîte à idées',
	prestataire: 'Prestataire', document: 'Document', diagnostic: 'Diagnostic',
	faq: 'Question fréquente', annuaire: 'Annuaire',
};

export const TYPE_COLORS: Record<string, string> = {
	ticket_resolu: '#B91C1C',          //   0° rouge
	ticket_ouvert: '#B91C1C',
	ticket_mis_a_jour: '#B91C1C',
	annonce: '#C2410C',                //  17° orange
	evenement: '#A16207',              //  35° ambre
	diagnostic: '#4D7C0F',             //  86° olive
	annuaire: '#15803D',               // 142° vert
	devis: '#047857',                  // 163° émeraude ┐ page /prestataires
	prestataire: '#0F766E',            // 175° sarcelle ┘
	idee: '#0E7490',                   // 193° cyan
	publication: 'var(--color-primary)', // 214° bleu Seine, couleur de la charte
	document: '#4338CA',               // 245° indigo
	sondage_clos: '#6D28D9',           // 263° violet
	sondage_ouvert: '#6D28D9',
	faq: '#A21CAF',                    // 295° fuchsia
};

export const TYPE_BG: Record<string, string> = {
	ticket_resolu: '#FEF2F2',
	ticket_ouvert: '#FEF2F2',
	ticket_mis_a_jour: '#FEF2F2',
	annonce: '#FFF7ED',
	evenement: '#FFFBEB',
	diagnostic: '#F7FEE7',
	annuaire: '#F0FDF4',
	devis: '#ECFDF5',
	prestataire: '#F0FDFA',
	idee: '#ECFEFF',
	publication: '#EEF2F7',
	document: '#EEF2FF',
	sondage_clos: '#F5F3FF',
	sondage_ouvert: '#F5F3FF',
	faq: '#FDF4FF',
};

//  Les défauts restent des VALEURS DE REPLI, pas une apparence acceptable : un
//  type inconnu doit se voir comme tel plutôt que passer pour une rubrique
//  normale. Ils sont lisibles (contraste 7,6:1) — c'est le garde-fou de test,
//  pas le repli, qui empêche un type d'y rester.
const COULEUR_INCONNUE = '#475569';
const FOND_INCONNU = '#F1F5F9';

export function typeCouleur(type: string): string {
	return TYPE_COLORS[type] ?? COULEUR_INCONNUE;
}
export function typeFond(type: string): string {
	return TYPE_BG[type] ?? FOND_INCONNU;
}
export function typeLibelle(type: string): string {
	return TYPE_LABELS[type] ?? type;
}

export function badgeClass(type: string, badge: string): string {
	const b = badge.toLowerCase();
	if (b.includes('résolu') || b.includes('réalisé') || b.includes('accepté')) return 'badge-green';
	if (b.includes('urgent') || b.includes('refusé')) return 'badge-red';
	if (b.includes('en cours') || b.includes('en attente') || b === 'panne') return 'badge-orange';
	if (b.includes('clôturé')) return 'badge-gray';
	if (b.startsWith('#')) return 'badge-gray';
	if (type === 'sondage_ouvert') return 'badge-purple';
	return 'badge-blue';
}

// ── Liens ─────────────────────────────────────────────────────────────────
// `null` = cet élément n'est affiché sur aucune page : on n'affiche alors PAS de
// lien, plutôt qu'un `href="#"` ou une route inexistante. Un document de catégorie
// non exposée (fiche synthétique, attestation de lot…) est dans ce cas — le fil
// pointait auparavant vers `/documents`, qui renvoyait un 404 (26/07/2026).
export function typeLink(item: FluxItem): string | null {
	if (item.type === 'sondage_ouvert' || item.type === 'sondage_clos') return '/sondages';
	if (['ticket_ouvert', 'ticket_resolu', 'ticket_mis_a_jour'].includes(item.type)) {
		const numero = item.meta?.numero as string | undefined;
		return numero ? `/tickets?open=${numero}` : '/tickets';
	}
	return item.lien ?? null;
}

export function typeVoirLabel(item: FluxItem): string {
	if (['ticket_ouvert', 'ticket_resolu', 'ticket_mis_a_jour'].includes(item.type)) return 'Voir le ticket →';
	if (item.type === 'publication') return "Voir l'actualité →";
	if (item.type === 'evenement') return "Voir l'événement →";
	if (item.type === 'devis') return 'Voir le devis →';
	if (item.type === 'sondage_ouvert' || item.type === 'sondage_clos') return 'Voir le sondage →';
	if (item.type === 'annonce') return "Voir l'annonce →";
	if (item.type === 'idee') return "Voir l'idée →";
	return 'Voir →';
}

// ── Nouveauté ─────────────────────────────────────────────────────────────
// `date` est celle de l'ANNONCE (le backend ne la recalcule pas sur une simple
// modification de marqueur, cf. flux.py) : décocher « Épinglé » ne redonne donc
// pas la pastille NEW à une actualité de l'an dernier.
export function isNew(item: { cree_le?: string; date: string }): boolean {
	const dateTs = new Date(item.date).getTime();
	const creeTs = item.cree_le ? new Date(item.cree_le).getTime() : dateTs;
	const ref = Math.max(dateTs, creeTs);
	const diff = Date.now() - ref;
	return diff >= 0 && diff < 48 * 3600 * 1000;
}

// ── Les trois registres du fil ────────────────────────────────────────────
// Chaque ligne appartient à UN registre et un seul :
//   1. 🔴 Urgences en cours — « qu'est-ce qui brûle ? »
//   2. 📌 Épinglé          — « qu'est-ce qu'il ne faut pas perdre de vue ? »
//   3. Chronologie         — « quoi de neuf ? »
//
// Pourquoi épinglé n'est PAS fusionné dans les urgences : l'urgence s'auto-périme
// (les états clos sortent du filtre), pas l'épinglage. Un épinglé y resterait
// indéfiniment et le bandeau rouge mourrait d'habitude ; et le plafond de 3 des
// urgences ferait évincer une urgence réelle par un élément épinglé.

/** Le registre le plus grave l'emporte : un élément urgent ET épinglé n'apparaît
 *  qu'en urgence. Il retombera dans le bandeau épinglé en cessant d'être urgent. */
export function estUrgent(item: FluxItem): boolean {
	return (
		(item.type === 'evenement' && item.meta?.type === 'coupure') ||
		(item.type === 'ticket_ouvert' && (item.badges?.includes('urgence') ?? false)) ||
		(item.type === 'publication' && Boolean(item.meta?.urgente) && item.meta?.statut !== 'resolu')
	);
}

export function estEpingle(item: FluxItem): boolean {
	return Boolean(item.meta?.epingle) && !estUrgent(item);
}

/** Reste en tête de la chronologie malgré son âge : ce qui n'est pas terminé
 *  n'est pas de l'histoire ancienne. */
export function estNonResolu(item: FluxItem): boolean {
	if (item.type === 'ticket_ouvert') {
		//  La cinquième liste de statuts de tickets, et la seule qui oubliait
		//  `annulé` : un ticket annulé restait donc en tête de la chronologie
		//  indéfiniment, comme s'il attendait encore quelque chose. `$lib/tickets`
		//  porte la question une fois pour toutes (#415).
		return !estTicketClos((item.meta?.statut as string) ?? '');
	}
	if (item.type === 'evenement') {
		//  🔴 Un événement PASSÉ n'attend plus rien, quel que soit son kanban
		//  (20/08/2026, signalé à l'écran : « pourquoi des événements de plus de
		//  30 j sont visibles ? »). L'AG du 1er mars était encore en tête du fil
		//  cinq mois plus tard : personne ne l'avait passée en « terminé », et
		//  ce seul oubli la rendait éternelle.
		//
		//  La règle du site est « après la date de l'événement » (#515) : c'est
		//  la DATE qui décide, pas un clic dans le kanban. Un ticket ouvert, lui,
		//  attend vraiment quelque chose — d'où la différence de traitement juste
		//  au-dessus.
		const debut = item.meta?.debut ?? item.date ?? item.cree_le;
		if (debut && new Date(debut as string).getTime() < Date.now()) return false;
		const k = (item.meta?.statut_kanban as string) ?? '';
		return !['termine', 'annule'].includes(k);
	}
	return false;
}

/**
 * Date qui décide de l'ancienneté d'une ligne du fil.
 *
 * ## 🔴 Elle lisait la NAISSANCE de l'objet, pas la date de l'annonce (#529)
 *
 * Signalé à l'écran le 20/08/2026 : *« le dernier commentaire semble ne pas être
 * visible »*. Un commentaire ajouté aujourd'hui sur un ticket ouvert en mars
 * était classé **en mars** — donc rangé dans les Archives (au-delà de trente
 * jours), voire hors de la fenêtre de chargement.
 *
 * La cause : cette fonction rendait `item.cree_le`, la naissance de l'OBJET,
 * alors que `item.date` porte celle de l'ANNONCE — ce que le commentaire de
 * `isNew`, vingt lignes plus haut, disait déjà en toutes lettres.
 *
 * ⚠️ **Six producteurs sur dix calculent une `date` différente de `cree_le`**,
 * et chacun l'a fait exprès :
 *
 * | Carte | `date` | `cree_le` |
 * |---|---|---|
 * | ticket mis à jour | l'évolution | l'ouverture du ticket |
 * | évolution d'événement | l'évolution | la création de l'événement |
 * | sondage clos | la clôture | la création |
 * | petite annonce | la mise à jour | le dépôt |
 * | prestation | la date de prestation | la saisie du devis |
 * | actualité | la publication | la rédaction |
 *
 * Le serveur faisait donc le bon calcul, six fois, et l'écran le jetait.
 *
 * ⚠️ Ce qui n'est **pas** traité ici : un événement du calendrier reste classé
 * sur sa date d'annonce et non sur sa date de tenue. C'est une autre question —
 * elle demande de trancher, entité par entité, entre « quoi de neuf » et « quoi
 * ensuite » — et elle reste suivie en **#524**.
 */
export function dateDeReference(item: FluxItem): number {
	const cloture = (item.meta?.cloture_le || item.meta?.ferme_le) as string | undefined;
	if (cloture) return new Date(cloture).getTime();
	//  `date` d'abord : c'est la date de l'ANNONCE, celle que le serveur a
	//  calculée pour cette carte. `cree_le` n'est qu'un repli pour les cartes
	//  qui ne portent pas de date propre.
	return new Date(item.date || item.cree_le || 0).getTime();
}

/** Plafond SOUPLE : on avertit celui qui épingle, on ne masque jamais un
 *  élément épinglé — le cacher trahirait la promesse du marqueur. Au-delà,
 *  le bandeau devient une seconde chronologie et ne signale plus rien. */
export const PLAFOND_EPINGLES = 5;

/** `totalApresEpinglage` = ce que deviendrait le total si l'on validait la case
 *  cochée, toutes rubriques confondues. `null` = rien à signaler. */
export function avertissementEpinglage(totalApresEpinglage: number): string | null {
	if (totalApresEpinglage <= PLAFOND_EPINGLES) return null;
	return `Cela porterait à ${totalApresEpinglage} le nombre d'éléments épinglés. Au-delà de ${PLAFOND_EPINGLES}, le bandeau « Épinglé » cesse d'attirer l'œil : épingler dix éléments revient à n'en épingler aucun.`;
}
