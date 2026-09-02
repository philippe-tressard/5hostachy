/**
 * Les écarts DÉCLARÉS de `check-charte-recomposee.mjs`.
 *
 * Clé : `chemin/relatif.svelte::classe`. Trois règles, et elles ne se négocient
 * pas — ce sont celles de `check-styles-nus.regles.mjs`, pour les mêmes raisons :
 *
 *   1. **Une raison, toujours.** Une liste sans raison devient un dépotoir.
 *   2. **Une tolérance qui ne sert plus fait ÉCHOUER le contrôle**, ce qui force à
 *      retirer la ligne plutôt qu'à la reconduire « au cas où ».
 *   3. **Jamais de seuil.** On ne tolère pas « quelques » redéfinitions : on nomme
 *      celles qu'on n'a pas encore tranchées, et elles se comptent.
 *
 * Elles jouent aussi le rôle de TÉMOIN : chacune décrit une prise que la détection
 * doit continuer de faire. Si elles se périmaient TOUTES d'un coup, ce serait le
 * motif de lecture qui est cassé, pas le dépôt qui est devenu conforme.
 *
 * ── D'où vient cette liste ────────────────────────────────────────────────────
 *
 * Le relevé de #607 comptait **54** règles. Trente-cinq ont été supprimées ou
 * réduites à leur seule différence le 28/08/2026 ; les dix-neuf ci-dessous sont
 * des variations RÉELLES, dont chacune dit pourquoi elle existe.
 *
 * ⚠️ La plupart ne sont pas des dettes : `composants.css` autorise explicitement
 * qu'un écran réparte sa grille autrement, à condition de ne garder QUE ce qui
 * diffère. C'est le cas de tous les `.form-grid` ci-dessous. Les inscrire ici
 * n'est donc pas un aveu — c'est la seule façon qu'a le contrôle de distinguer
 * une variation VOULUE d'une copie oubliée, puisque le CSS ne le dit pas.
 */
export const TOLERANCES = {
	//  ── `.checkbox-field` : l'alignement quand le libellé fait plusieurs lignes ─
	//  La charte centre la case sur son libellé, ce qui est juste tant qu'il tient
	//  sur une ligne. Les conditions d'utilisation en font trois : la case doit
	//  alors s'aligner sur la PREMIÈRE, sinon elle flotte au milieu du paragraphe.
	//  C'est la SEULE des quatre propriétés qui reste locale — les trois autres
	//  (gap, font-size, display) étaient trois valeurs différentes pour la même
	//  case, et sont remontées dans la charte le 02/09/2026.
	'routes/auth/inscription/+page.svelte::checkbox-field':
		'align-items: flex-start — le libellé des conditions tient sur plusieurs lignes',
	//  ── `.form-grid` : la répartition en colonnes ────────────────────────────
	//  `composants.css` le prévoit en toutes lettres : « les écrans qui
	//  répartissent autrement ne gardent QUE ce qui diffère — une colonne, un
	//  espacement — jamais la règle entière ». C'est exactement ce qu'ils font.
	'lib/components/FormulaireEvenement.svelte::form-grid':
		'colonnes de 200 px : ce formulaire a des champs courts (date, heure, fréquence)',
	'lib/components/OngletCopropriete.svelte::form-grid':
		'`auto-fill` et non `auto-fit` — les champs ne s’étirent pas quand il en manque',
	'routes/(app)/admin/+page.svelte::form-grid':
		'deux colonnes fixes : cet écran de configuration apparie des libellés et des valeurs',
	'routes/(app)/espace-cs/+page.svelte::form-grid':
		'colonnes de 150 px et gap resserré — la fiche d’un membre du CS tient des champs très courts',
	'routes/(app)/prestataires/+page.svelte::form-grid':
		'colonnes de 180 px et gap resserré, même raison',
	//  ⚠️ Celui-ci n'est PAS une répartition : c'est une pile. Le nom ment sur ce
	//  que fait la règle, et c'est la vraie dette de la liste.
	//  ⚠️ La clé a suivi le BALISAGE le 31/08/2026 : le formulaire de la FAQ est
	//  devenu `FormulaireFaq.svelte`, et sa règle est partie avec lui (#344 —
	//  une règle laissée dans la page que le balisage vient de quitter ne
	//  s'applique plus à rien). La dette, elle, n'a pas bougé d'un pouce : la
	//  retirer parce que le fichier a changé de nom l'aurait fait disparaître
	//  des relevés sans que rien ne soit corrigé.
	'lib/components/FormulaireFaq.svelte::form-grid':
		'⚠️ DETTE — `display: flex` en colonne : ce n’est plus une grille, c’est une pile. ' +
		'La classe ment sur ce qu’elle fait ; à renommer plutôt qu’à aligner',

	//  ── Écrans d'authentification ────────────────────────────────────────────
	'routes/auth/inscription/+page.svelte::auth-page':
		'formulaire LONG : aligné en haut au lieu d’être centré, et plus aéré',
	'routes/auth/inscription/+page.svelte::auth-card':
		'480 px au lieu de 400 — l’inscription porte deux fois plus de champs',
	'routes/auth/inscription/+page.svelte::auth-logo': 'logo réduit sur une page déjà longue',

	//  ── Descendants par balise (lus depuis le 30/08/2026) ───────────────────
	//  🔴 Cette forme de sélecteur — `.classe element` — échappait au contrôle, qui
	//  ne lisait que `.classe` seule. C'est elle qu'emploie tout composant qui
	//  habille ses enfants : onglets, tableaux, listes. Son ajout a trouvé une
	//  redéfinition COMPLÈTE de `.tabs button` qui faisait disparaître le liseré de
	//  l'onglet actif en production, et deux règles de tableau dont cinq
	//  propriétés sur sept étaient identiques à la charte.
	'routes/(app)/prestataires/+page.svelte::tabs button':
		'onglets à ICÔNE, plus nombreux : padding et police resserrés pour tenir sur une ligne',
	'routes/(app)/acces-securite/+page.svelte::table th':
		'tableaux DENSES (imports d’accès, listes de badges) : en-tête resserré',
	'routes/(app)/acces-securite/+page.svelte::table td':
		'même raison — la cellule suit l’en-tête, sinon la colonne se décale',

	//  ── Boutons ──────────────────────────────────────────────────────────────
	'routes/(app)/admin/+page.svelte::btn-sm':
		'boutons plus denses dans les tableaux de configuration',
	'routes/(app)/espace-cs/+page.svelte::btn-icon':
		'boutons-icônes CERCLÉS et carrés (2 rem) formant une barre d’actions, là où la ' +
		'charte habille une icône nue',
	'routes/(app)/espace-cs/+page.svelte::btn-icon-edit':
		'le crayon est en couleur primaire — il est l’action principale de la rangée',
	'lib/components/ChampSaisiPour.svelte::tab-btn':
		'onglets ENCADRÉS et non soulignés : boutons de bascule dans un champ, pas la ' +
		'barre d’onglets d’une page',

	//  ── Divers, chacun avec sa raison ────────────────────────────────────────
	'lib/components/ImageUpload.svelte::spinner':
		'attente posée SUR l’image : taille fixe et trait blanc, pour rester lisible sur ' +
		'une photo quelconque',
	'lib/components/TachesPlanifiees.svelte::chevron':
		'chevron plus petit et en couleur primaire : il annonce une action, pas un dépliage neutre',
	'routes/(app)/faq/+page.svelte::chevron':
		'`color: inherit` — le chevron suit la couleur de la question, qui change au survol',
	'routes/(app)/acces-securite/+page.svelte::table':
		'tableau plus lisible : ses cellules portent des codes et des dates',
	'routes/(app)/notifications/+page.svelte::section-title':
		'espacement resserré — les sections de cette page sont courtes et nombreuses',
	'routes/(app)/notifications/+page.svelte::back-link':
		'retour discret et proche du contenu, là où la charte en fait un lien primaire',
};
