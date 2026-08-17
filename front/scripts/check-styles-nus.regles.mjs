/**
 * La RÈGLE de `check-styles-nus.mjs` : ce qui est refusé, et les écarts déjà connus.
 *
 * Séparé du script pour que la DÉTECTION (lui) et ce qu’elle cherche (ici) ne
 * grossissent pas dans le même fichier — cette table-ci bouge à chaque écran repris.
 */
/**
 * Volet A — les éléments dont une règle CSS nue casse silencieusement un autre
 * usage : elle atteint TOUS les éléments de ce type, cases à cocher comprises.
 */
export const ELEMENTS = ['input', 'textarea', 'select', 'button', 'label'];

/** Les éléments qui portent la peau définie par `.field input, .field select, …`. */
const CONTROLES = ['input', 'select', 'textarea'];

/**
 * Volet B — ce qu'une signature refuse, et par quelle classe on la remplace.
 * `regle` : le sélecteur d'`app.css` dont les valeurs sont LUES (jamais recopiées),
 * dont `proprietes` doit être déclaré — vérifié au cas zéro. `mode: valeurs` exige
 * TOUTES les propriétés AVEC la valeur d'app.css, ce qui rend la signature étroite
 * et sûre ; `mode: proprietes` se contente d'UNE propriété, mais seulement sur les
 * `elements` visés.
 */
export const SIGNATURES = [
	{
		nom: 'libelle-champ',
		regle: '.field label',
		proprietes: ['font-size', 'font-weight'],
		mode: 'valeurs',
		quoi: 'la typographie du libellé de champ',
		remede:
			'écrire un vrai `<label for="…">` dans un `.field` — `.field label` (app.css) porte ' +
			'déjà cette taille et cette graisse ; quand la section ne contient qu’un champ, ' +
			'c’est le titre de `SectionFormulaire` qui EST le libellé (ux-patterns §9 septies)',
	},
	{
		nom: 'form-actions',
		regle: '.form-actions',
		proprietes: ['display', 'justify-content'],
		mode: 'valeurs',
		quoi: 'l’alignement à droite d’une rangée d’actions',
		remede:
			'utiliser `class="form-actions"` (app.css), qui porte display, alignement, gap et ' +
			'marge — ou `class="modal-footer"` quand la rangée est le pied d’une modale',
	},
	{
		nom: 'controle-saisie',
		regle: '.field input',
		proprietes: ['border', 'border-radius', 'padding', 'background'],
		mode: 'proprietes',
		elements: CONTROLES,
		quoi: 'la peau d’un contrôle de saisie (bordure, rayon, remplissage, fond)',
		remede:
			'placer le contrôle dans un `<div class="field">` — `.field input, .field select, ' +
			'.field textarea` (app.css) porte déjà bordure, rayon, remplissage, fond ET le style ' +
			'de focus, que le style en ligne fait perdre en silence',
	},
	{
		nom: 'largeur-saisie',
		regle: '.largeur-saisie',
		proprietes: ['max-width'],
		mode: 'valeurs',
		quoi: 'la largeur normée d’un bloc de saisie',
		remede: 'utiliser `class="largeur-saisie"` (app.css) — la norme UX §9, écrite une fois',
	},
];

/**
 * Volet B bis — les classes de STRUCTURE dont une redéclaration en ligne est
 * toujours une redite. Limité à celles-ci exprès : `font-size` sur un `.badge` ou
 * `padding` sur une `.card` sont des variations légitimes, et les refuser noierait
 * le vrai signal (53 `.badge` et 14 `.card` dans l'arborescence).
 */
export const CLASSES_STRUCTURE = ['field', 'form-actions', 'largeur-saisie'];

/**
 * Tolérances, chacune avec sa raison.
 *
 * Clé : `chemin/relatif.svelte::signature`, où la signature est le `nom` d'une
 * entrée de `SIGNATURES` (ou `redite-classe`). Une clé qui nomme une signature
 * inexistante fait ÉCHOUER le contrôle : une tolérance qui ne protège rien, en
 * silence, est pire qu'absente.
 *
 * Trois règles, et elles ne se négocient pas :
 *
 *   1. **Une raison, toujours.** Une liste sans raison devient un dépotoir.
 *   2. **Une tolérance qui ne sert plus fait échouer le contrôle**, ce qui force à
 *      retirer la ligne plutôt qu'à la reconduire « au cas où ».
 *   3. **Jamais de seuil.** On ne tolère pas « quelques » recompositions : on
 *      nomme celles qu'on n'a pas encore corrigées, et elles se comptent.
 *
 * Ces tolérances jouent aussi le rôle de TÉMOIN : chacune décrit une prise que la
 * détection doit continuer de faire. Si elles se périment TOUTES d'un coup, c'est
 * le motif de lecture qui est cassé, pas le dépôt qui est devenu conforme.
 *
 * ⚠️ La clé est le FICHIER, pas la ligne : une ligne bouge à chaque édition, et une
 * exception qui pointe à côté ne protège plus rien. La contrepartie est assumée —
 * une seconde violation de la même signature dans un fichier déjà toléré ne sera
 * pas vue. C'est le même arbitrage que `check-libelles-soumission.mjs`.
 * Les numéros de ligne cités dans les raisons sont donc indicatifs (`l. ~N`).
 *
 * ── RESTE À TRAITER — révélé par l'élargissement au balisage (#425) ────────────
 *
 * Ces écarts sont réels et connus. Ils ne sont PAS corrigés dans #425, dont le
 * périmètre est le formulaire d'édition de ticket : les corriger au passage aurait
 * mélangé une dizaine d'écrans dans le même diff. Chaque ligne dit ce qu'on lit
 * dans le fichier ; l'entrée disparaît d'elle-même quand l'écran est repris.
 */
export const TOLERANCES = {
	//  ── Volet A : sélecteurs d'élément nus dans un `<style>` ────────────────
	//  (aucune — clé de la forme `chemin.svelte:input`)

	//  ── libelle-champ : la typographie de `.field label` réécrite à la main ──
	'lib/components/FormulaireTicket.svelte::libelle-champ':
		'la typographie du libellé est recopiée sur un `<legend>` de fieldset (l. ~210) — ' +
		'un `<legend>` n’est pas un `.field label` : il manque une classe pour lui, à décider',
	'routes/(app)/prestataires/+page.svelte::libelle-champ':
		'deux libellés écrits à la main (l. ~1857 et ~1861) — écran de 2 182 lignes déjà ' +
		'déclaré en exception de `lint:formulaires` et de `lint:soumission`, à découper avant',

	//  ── form-actions : la rangée d'actions alignée à droite, à la main ───────
	'lib/components/OngletWhatsApp.svelte::form-actions':
		'trois rangées d’actions alignées à la main (l. ~175, ~260, ~286)',
	'routes/(app)/admin/+page.svelte::form-actions':
		'neuf rangées d’actions alignées à la main (l. ~1082 à ~1639), dont plusieurs pieds ' +
		'de modale qui relèvent de `.modal-footer`',
	'routes/(app)/admin/templates-email/+page.svelte::form-actions':
		'pied de modale aligné à la main (l. ~192)',
	'routes/(app)/annuaire/+page.svelte::form-actions':
		'rangée d’actions alignée à la main (l. ~198)',
	'routes/(app)/espace-cs/+page.svelte::form-actions':
		'deux rangées alignées à la main (l. ~2276 et ~2495)',
	'routes/(app)/faq/+page.svelte::form-actions': 'pied de modale aligné à la main (l. ~543)',
	'routes/(app)/mon-lot/+page.svelte::form-actions':
		'rangée d’actions alignée à la main, avec `flex-wrap` (l. ~889)',
	'routes/(app)/residence/+page.svelte::form-actions':
		'pied de modale aligné à la main (l. ~584)',
	'routes/(app)/sondages/[id]/+page.svelte::form-actions':
		'rangée d’actions alignée à la main (l. ~326)',

	//  ── controle-saisie : la peau de `.field input` repeinte à la main ───────
	'routes/(app)/admin/+page.svelte::controle-saisie':
		'champ de saisie de seuil re-peint à la main (l. ~1212)',
	'routes/(app)/espace-cs/+page.svelte::controle-saisie':
		'champ de filtre re-peint à la main (l. ~2266)',
	'routes/(app)/prestataires/+page.svelte::controle-saisie':
		'un `<select>` et un `<input>` re-peints à la main (l. ~1815 et ~1840) — même écran de ' +
		'2 182 lignes que ci-dessus',
	'routes/(app)/sondages/[id]/+page.svelte::controle-saisie':
		'deux `<textarea>` de réponse re-peints à la main (l. ~220 et ~234) ; celui de la l. ~220 ' +
		'porte en plus une bordure `--color-primary` volontaire, à traduire en classe d’état',
	//  ⚠️ Les deux tolérances de `tickets/[id]` sont tombées le 17/08/2026 (#431) :
	//  le champ e-mail re-peint à la main est parti avec le formulaire de réponse
	//  écrit à la main (remplacé par `EvolForm`), et les 720 px de quatre blocs
	//  sont devenus une seule règle `.ticket-header, .messages, …`. Le contrôle
	//  les a REFUSÉES dès qu'elles sont devenues inutiles.

	//  ── largeur-saisie : les 720 px de `.largeur-saisie` écrits en dur ───────
	'routes/(app)/espace-cs/+page.svelte::largeur-saisie':
		'720 px écrits en dur sur deux `<section>` (l. ~1342 et ~1371)',

	//  ── redite-classe : la classe est là, et le style en ligne la redit ──────
	'routes/(app)/admin/lots-import/+page.svelte::redite-classe':
		'`.field` avec `margin-bottom:.75rem` en ligne (l. ~346) — exactement la valeur que la ' +
		'classe porte déjà : le style ne change rien, il fait seulement croire qu’il pourrait',
};
