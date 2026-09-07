/**
 *  Les EXCEPTIONS de `check-libelles-soumission.mjs` — chacune avec sa raison.
 *
 *  🔴 Séparées du script le 07/09/2026 : la détection (lui) et ce qu'elle
 *  tolère (ici) ne doivent pas grossir dans le même fichier. C'est ce qui l'a
 *  fait passer au-dessus de son propre plafond de modularité.
 *
 *  ⚠️ Cette table BOUGE à chaque écran repris ; la détection, presque jamais.
 *  Deux rythmes différents, deux fichiers — le pattern de
 *  `check-styles-nus.regles.mjs`, pour la même raison exactement.
 */
/**
 * Fichiers dispensés, avec leur raison.
 *
 * Une tolérance sans raison devient un dépotoir : chacune est nommée, et le
 * contrôle échoue si l'une cesse de servir — c'est-à-dire dès que le fichier
 * qu'elle protège devient conforme (règle posée en #374, reprise de
 * `check-pages.mjs`). Une exception qui dort laisserait repasser une vraie
 * divergence dans ce fichier sans que personne l'ait décidé.
 */
export const EXCEPTIONS = {
	//  🔴 `PiedFormulaire` rend `{enCours ? libelleEnCours : libelle}` — des
	//  VARIABLES, pas des chaînes. Le contrôle B lit le balisage : il ne peut rien
	//  y voir, et il l'a dit honnêtement (« aucun libellé lisible — contrôle
	//  impossible »).
	//
	//  ⚠️ Ce n'est PAS une dérogation à la règle, c'est un DÉPLACEMENT de
	//  l'endroit où elle se vérifie : `check-pied-formulaire.mjs` lit les valeurs
	//  par défaut de ces props et refuse qu'un appelant en passe d'autres. Le
	//  verbe générique est donc mieux tenu qu'avant — il l'était par dix-neuf
	//  copies d'accord entre elles, il l'est maintenant par une déclaration.
	'lib/components/PiedFormulaire.svelte':
		'le libellé y est une PROP : la règle se vérifie sur ses défauts, dans ' +
		'check-pied-formulaire.mjs, pas sur son balisage',
	//  🔴 Une CONFIRMATION n'est pas une soumission de formulaire, et son verbe
	//  ne doit surtout pas être générique : « Enregistrer » sur une boîte qui
	//  supprime définitivement serait un piège. Le libellé y nomme le GESTE —
	//  « Supprimer », « Archiver » — et c'est ce qui rend la boîte sûre.
	//
	//  ⚠️ L'exception porte sur le VERBE (contrôle B), pas sur l'ordre des
	//  boutons : « Annuler » y vient bien avant l'action, comme partout ailleurs
	//  (contrôle C), et c'est délibérément la même main.
	'lib/components/Confirmation.svelte':
		'boîte de confirmation : le verbe nomme le geste (« Supprimer »), il ne peut pas être générique',
	//  ── Hors périmètre par la RÈGLE elle-même (§9 quinquies bis) ────────────
	//  Ce ne sont pas des créations d'objet, et leur verbe métier est le bon.
	'lib/components/FormulaireCreation.svelte':
		"c'est le cadre (titre + boîte), pas un formulaire — chaque écran écrit son " +
		'propre bouton dans son <form>',
	'lib/components/ChangementMotDePasse.svelte':
		'changement de mot de passe — hors périmètre explicite de la règle',
	'routes/auth/connexion/+page.svelte': "écran d'authentification — « Se connecter »",
	'routes/auth/inscription/+page.svelte': "écran d'authentification — « Créer mon compte »",
	'routes/auth/mot-de-passe-oublie/+page.svelte':
		"écran d'authentification — « Envoyer le lien » ne crée aucun objet",
	'routes/auth/verifier-email/+page.svelte':
		"écran d'authentification — « Renvoyer » relance un e-mail déjà parti",
	//  🔴 Arbitré à l'écran le 18/08/2026 : « Créer et envoyer au CS me semble
	//  bizarre : ça doit être plutôt Générer une affiche ». Cet écran ne crée pas un
	//  objet qu'on retrouvera dans une liste — il FABRIQUE un document à imprimer,
	//  et depuis le même jour il n'envoie plus rien. Même famille que les imports,
	//  déjà hors périmètre de la règle.
	'lib/components/FormulaireAnnonceHall.svelte':
		'affiche de hall — « Générer une affiche » : on produit un document, on ne ' +
		"crée pas un objet (et l'écran n'envoie plus d'e-mail depuis le 18/08/2026)",
	//  Relance syndic : ce n'est pas un formulaire de création mais une ACTION de
	//  masse sur une sélection, et son libellé porte le compte — « Envoyer la
	//  relance (3 tickets) ». Le remplacer par « Enregistrer » ferait disparaître
	//  ce que le bouton va réellement faire, et à combien de tickets.
	//  Repéré par ce contrôle en extrayant le reporting (#453) : la rangée est
	//  passée à `.form-actions`, ce qui l'a rendue visible ici.
	'lib/components/reporting/VueRelanceSyndic.svelte':
		'envoi groupé de relances — « Envoyer la relance (N tickets) » agit sur une ' +
		'sélection existante, il ne crée aucun objet',

	//  ── RESTE À TRAITER — révélé par l'élargissement de portée (#416) ───────
	//  Ces écarts sont réels et connus. Ils ne sont PAS corrigés dans #416, dont
	//  le périmètre est `EvolForm` : les corriger au passage aurait mélangé deux
	//  lots dans le même diff. Chaque ligne dit ce qu'on lit à l'écran ; l'entrée
	//  disparaît d'elle-même quand l'écran est repris, sinon ce contrôle échoue
	//  en réclamant sa suppression.
	'routes/(app)/profil/+page.svelte':
		'« Envoyer la demande » / « Envoi… » (l. ~451) et « Je suis un nouvel arrivant » ' +
		'/ « Envoi… » (l. ~526)',
	'routes/(app)/sondages/[id]/+page.svelte': 'attente « Sauvegarde… » (l. ~328)',
	//  ⚠️ L'exception de `tickets/[id]` disait « c'est une seconde écriture
	//  d'`EvolForm`, à fusionner avant d'aligner le verbe ». La fusion a eu lieu le
	//  17/08/2026 (#431) : le formulaire de réponse écrit à la main a disparu, le
	//  geste n'a plus qu'un libellé, et le contrôle a REFUSÉ la tolérance dès
	//  qu'elle est devenue inutile.
};
