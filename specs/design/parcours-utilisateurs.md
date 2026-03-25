# Parcours utilisateurs

> Les parcours utilisateurs (user journeys) décrivent de bout en bout l'expérience vécue par un utilisateur pour accomplir un objectif clé. Ils complètent les [cas d'utilisation](../commun/cas-utilisation.md) en se concentrant sur la fluidité et les points de friction potentiels.

---

## PU-001 — Inscription d'un nouveau résident

**Persona concerné :** Copropriétaire ou locataire venant d'emménager.
**Objectif :** Créer son compte et accéder à son espace personnel.

| Étape | Action utilisateur | Réponse système | Émotion |
|-------|--------------------|-----------------|---------|
| 1 | Reçoit le lien d'invitation ou découvre l'appli | Page d'accueil claire, CTA « Créer mon compte » | Curieux |
| 2 | Saisit ses informations (nom, email, bâtiment, statut) | Formulaire guidé, champs obligatoires signalés | Confiant |
| 3 | Choisit son mode d'auth (mot de passe / Apple / Google) | Retour immédiat, confirmation par email | Rassuré |
| 4 | Renseigne son lot (facultatif à cette étape) | Sauvegarde automatique, peut compléter plus tard | Soulagé |
| 5 | Son nom est reconnu dans la liste des copropriétaires | Compte activé instantanément | Satisfait |
| 5bis | Son nom n'est pas reconnu | Message « Validation en attente » + délai estimé | Légèrement frustré → rassuré |
| 6 | Accède à son tableau de bord | Contenu personnalisé selon son bâtiment et son statut | Bien accueilli |

**Points de friction à éviter :**
- Formulaire trop long en une seule page → décomposer en étapes.
- Manque de feedback après soumission → indiquer le délai et le responsable de validation.

---

## PU-002 — Résident signale une panne ou un problème

**Persona concerné :** Résident occupant (copropriétaire ou locataire).
**Objectif :** Signaler un problème et suivre sa résolution.

| Étape | Action utilisateur | Réponse système | Émotion |
|-------|--------------------|-----------------|---------|
| 1 | Constate une panne (ex. ascenseur en panne) | — | Inquiet |
| 2 | Ouvre l'appli → « Mes demandes » → « Nouveau ticket » | Catégories claires (panne, nuisance, urgence, question) | Guidé |
| 3 | Choisit la catégorie, décrit le problème, ajoute une photo | Formulaire simple, prise de photo directe | Efficace |
| 4 | Valide l'envoi | Confirmation visuelle + numéro de ticket | Soulagé |
| 5 | Reçoit une notification à chaque changement de statut | Push notification ou email selon préférence | Informé |
| 6 | Le problème est résolu, ticket clos | Récapitulatif et invitation à confirmer la résolution | Satisfait |

**Points de friction à éviter :**
- Pas de retour après envoi → confirmation immédiate et numérotation du ticket.
- Pas de visibilité sur l'avancement → statut toujours visible et mis à jour.

---

## PU-003 — Résident commande un vigik ou une télécommande

**Persona concerné :** Copropriétaire ou locataire ayant besoin d'un accès supplémentaire.
**Objectif :** Commander un vigik ou une télécommande de parking.

| Étape | Action utilisateur | Réponse système | Émotion |
|-------|--------------------|-----------------|---------|
| 1 | Accède à « Mon lot → Mes vigiks » | Liste de ses badges actuels avec statut | Orienté |
| 2 | Consulte les règles en vigueur (quota autorisé) | Information claire sur les limites | Informé |
| 3 | Clique sur « Commander un vigik » | Formulaire simple (motif, quantité) | Confiant |
| 4 | Confirme la demande | Confirmation + transmission au conseil syndical | Rassuré |
| 5 | Reçoit une notification de traitement | Statut mis à jour (accepté / refusé + motif) | Satisfait ou compréhensif |

---

## PU-004 — Membre du conseil syndical publie une actualité

**Persona concerné :** Membre du conseil syndical.
**Objectif :** Informer tous les résidents d'un événement ou d'une décision.

| Étape | Action utilisateur | Réponse système | Émotion |
|-------|--------------------|-----------------|---------|
| 1 | Se connecte avec son compte conseil syndical | Interface enrichie avec outils de publication | Efficace |
| 2 | Va dans « Communication → Actualités → Nouvelle publication » | Éditeur simple (titre, texte, pièces jointes, urgence ?) | Concentré |
| 3 | Choisit le périmètre (toute la résidence / un bâtiment) | Sélecteur de cible | Précis |
| 4 | Publie l'actualité | Notification push envoyée aux résidents concernés | Satisfait |
| 5 | Les résidents voient l'actualité sur leur tableau de bord | Mise à jour en temps réel | — |

---

## PU-005 — Nouveau résident découvre le kit de bienvenue

**Persona concerné :** Résident venant d'emménager.
**Objectif :** S'approprier les règles et informations pratiques de la résidence.

| Étape | Action utilisateur | Réponse système | Émotion |
|-------|--------------------|-----------------|---------|
| 1 | Termine son inscription | Suggestion automatique « Découvrez votre résidence » | Curieux |
| 2 | Accède au kit de bienvenue | Contenu structuré : contacts, règles, FAQ, plan | Bien accueilli |
| 3 | Télécharge le règlement de copropriété | Document à jour, téléchargeable en PDF | Confiant |
| 4 | Consulte le plan de la résidence | Plan interactif avec repères clés (poubelles, vélos, parkings) | Orienté |
| 5 | Découvre les contacts utiles (syndic, conseil de son bâtiment) | Fiches contact avec coordonnées | Rassuré |

---

## PU-006 — Bailleur crée un bail et transfère ses accès au locataire

**Persona concerné :** Copropriétaire bailleur louant son lot.
**Objectif :** Enregistrer un nouveau locataire, lui confier virtuellement ses badges Vigik et télécommandes, puis récupérer les accès en fin de bail.

### Cas A — Le bailleur s'inscrit avant le locataire

| Étape | Action utilisateur | Réponse système | Émotion |
|-------|--------------------|-----------------|---------|
| 1 | Va dans « Mon lot → Location » | Liste de ses baux actifs et historique | Orienté |
| 2 | Clique sur « Nouveau bail », saisit l'email du locataire | Recherche instantanée : si l'email est déjà inscrit, la fiche s'affiche ; sinon les champs libres restent modifiables | Guidé |
| 3 | Renseigne les dates d'entrée et de sortie prévue, valide | Bail créé, `locataire_email` enregistré. Si compte trouvé : `locataire_id` lié immédiatement | Satisfait |
| 4 | Clique sur 🔑 « Accès » du bail | Liste de tous ses Vigik et TC rattachés au lot (statut : Chez bailleur / Chez locataire) | Précis |
| 5 | Coche les accès à confier, clique « Transférer (N) » | `chez_locataire=True` + `bail_id` enregistrés. Accès signalés « Chez locataire » | Rassuré |
| 6 | Le locataire s'inscrit ultérieurement avec le même email | Liaison `locataire_id` effectuée automatiquement à l'activation | — (transparent) |

### Cas B — Le locataire s'inscrit avant le bailleur (ou bailleur absent)

| Étape | Action utilisateur | Réponse système | Émotion |
|-------|--------------------|-----------------|---------|
| 1 | Locataire s'inscrit | Compte créé, en attente de validation | Neutre |
| 2 | Admin valide le compte | Auto-match : si un bail actif existe avec cet email → `locataire_id` lié automatiquement | — (transparent) |
| 3 | Aucun bail trouvé → admin va dans Espace CS → Baux en attente | Liste des baux sans `locataire_id` | Réactif |
| 4 | Admin sélectionne le bon utilisateur, clique « Lier » | `locataire_id` renseigné manuellement via `POST /admin/baux/{id}/lier-locataire/{user_id}` | Satisfait |

### Fin de location

| Étape | Action utilisateur | Réponse système | Émotion |
|-------|--------------------|-----------------|---------|
| 1 | Bailleur clique « Terminer le bail » | Confirmation demandée (date de sortie réelle) | Précis |
| 2 | Confirme | Tous les Vigik/TC avec `bail_id=X` passent automatiquement à `chez_locataire=False` | Soulagé |
| 3 | Consulte la vue « Mes accès » | Tous ses accès apparaissent à nouveau « Chez bailleur » | Confiant |

**Points de friction à éviter :**
- Oublier de récupérer les accès en fin de bail → récupération automatique à la clôture.
- Bailleur incertain si le locataire est inscrit → recherche email temps réel dans le formulaire de bail.
- Locataire qui ne voit pas les accès confiés → section dédiée dans « Accès & badges ».

---

## PU-007 — Mandataire consulte un lot pour un copropriétaire absent

**Persona concerné :** Mandataire (proche, notaire, gestionnaire) d'un copropriétaire.
**Objectif :** Consulter les documents et tickets d'un lot au nom du copropriétaire, sans pouvoir agir à sa place sur les actions sensibles.

| Étape | Action utilisateur | Réponse système | Émotion |
|-------|--------------------|-----------------|---------|
| 1 | Se connecte | Interface réduite : seul le lot mandaté est visible | Orienté |
| 2 | Reçoit une notification urgente (ex. dégât des eaux) | Notification accessible malgré les droits limités | Informé |
| 3 | Consulte le ticket associé à l'urgence | Détail du ticket en lecture, statut en temps réel | Rassuré |
| 4 | Essaie de modifier un paramètre hors périmètre | Message explicatif « Action réservée au copropriétaire titulaire » + contact CS | Compréhensif (pas frustré) |
| 5 | Télécharge les derniers relevés de charges | PDF disponible en lecture | Efficace |

**Points de friction à éviter :**
- Boutons d'action silencieusement masqués → expliquer pourquoi l'action est indisponible.
- Toutes les sections de la résidence visibles → restreindre aux données du lot mandaté.

---

## PU-008 — Syndic surveille la résidence et exporte un rapport

**Persona concerné :** Gestionnaire de syndic (accès lecture seule + notifications urgentes).
**Objectif :** Avoir une vision de l'état de la résidence et produire des rapports périodiques.

| Étape | Action utilisateur | Réponse système | Émotion |
|-------|--------------------|-----------------|---------|
| 1 | Se connecte | Interface dédiée syndic : statistiques, tickets, lots | Concentré |
| 2 | Reçoit une alarme urgente (ex. ascenseur bloqué depuis 2 h) | Notification push dédiée « Urgence résidence » même hors connexion | Alert |
| 3 | Accède au ticket depuis la notification | Détail complet en lecture seule, historique et photos | Informé |
| 4 | Essaie de répondre au ticket | Message « Réponse réservée au conseil syndical » + lien pour contacter le CS | Compréhensif |
| 5 | Génère un rapport mensuel (tickets, lots, incidents) | Sélecteur de période, formats PDF/XLSX, export immédiat | Satisfait |
| 6 | Télécharge le rapport et le joint à son compte rendu | Fichier au format structuré, prêt à l'envoi | Efficace |

**Points de friction à éviter :**
- Syndic ne reçoit pas les urgences car il est lecture seule → les notifications d'urgence ne dépendent pas des droits d'écriture.
- Export demande plusieurs navigations → accessible en un clic depuis le tableau de bord syndic.

---

## PU-009 — Locataire découvre les accès confiés par son bailleur

**Persona concerné :** Locataire venant d'emménager, son bailleur lui a transféré un badge Vigik et une télécommande.
**Objectif :** Savoir quels accès sont à sa disposition et à qui les rendre en partant.

| Étape | Action utilisateur | Réponse système | Émotion |
|-------|--------------------|-----------------|----------|
| 1 | Se connecte après activation de son compte | Tableau de bord personnalisé | Bien accueilli |
| 2 | Va dans « Accès & badges » | Ses propres accès + section **« Accès confiés par votre bailleur »** visible si des accès ont été transférés | Informé |
| 3 | Consulte la liste : 1 Vigik, 1 télécommande | Code de chaque accès, statut, type | Rassuré |
| 4 | Tente de supprimer ou modifier un accès reçu | Action non disponible — les accès du bailleur sont en lecture seule pour le locataire | Compréhensif |
| 5 | En fin de bail, les accès disparaissent automatiquement de la liste | Le bailleur a clôturé le bail → `chez_locataire=False` | Informé |

**Points de friction à éviter :**
- Section absente si aucun accès transféré → la section n'apparaît que si `accesRecus.length > 0` (pas d'encart vide).
- Locataire pense que les accès lui appartiennent → libellé explicite « Confiés par votre bailleur ».

---

> **Note :** Les détails fonctionnels (champs, règles métier, validations) sont dans [cas-utilisation.md](../commun/cas-utilisation.md).
> L'arborescence des écrans est définie dans [web/navigation.md](../web/navigation.md) et [mobile/navigation.md](../mobile/navigation.md).
