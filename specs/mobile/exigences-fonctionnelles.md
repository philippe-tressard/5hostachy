# Exigences fonctionnelles — Application mobile (PWA)

> La PWA partage la même API et les mêmes règles métier que le site web.
> Ce fichier liste les exigences **spécifiques à l’usage mobile** ainsi que les exigences communes les plus critiques.
> Priorités : **Haute** (MVP), **Moyenne** (phase 1), **Basse** (phase 2).

---

## Installation & accès

### EF-MOB-001 — Installable sur écran d’accueil (A2HS)
- **Priorité :** Haute
- **Description :** La PWA est installable sur écran d’accueil sur iOS 16.4+ (Safari) et Android 10+ (Chrome) sans passer par un App Store.
- **Critères d’acceptance :**
  - Le manifeste PWA est valide (icônes 192 px et 512 px, `display: standalone`, `theme_color`).
  - L’invité d’installation s’affiche après une première visite sur Android.

### EF-MOB-002 — Fonctionnement hors-ligne partiel
- **Priorité :** Haute
- **Description :** Les pages consultées récemment (tableau de bord, mon lot, actualités) restent accessibles sans connexion via le cache Workbox.
- **Critères d’acceptance :**
  - Page d’accueil et informations essentielles disponibles hors-ligne.
  - Les actions nécessitant le serveur (ticket, commande vigik) affichent un message clair « connexion requise ».

---

## Navigation mobile

### EF-MOB-010 — Barre de navigation inférieure
- **Priorité :** Haute
- **Description :** Navigation principale via une bottom tab bar à 5 onglets : Accueil, Mon lot, Demandes, Résidence, Profil.
- **Critères d’acceptance :**
  - L’onglet actif est visuellement distinct.
  - Un badge de notification s’affiche sur les onglets concernés.

### EF-MOB-011 — Gestes natifs
- **Priorité :** Haute
- **Description :** Swipe retour pour la navigation arrière, pull-to-refresh sur les listes, ouverture des formulaires en modale.

---

## Fonctionnalités métier (reprises du web)

### EF-MOB-020 — Connexion & inscription
- **Priorité :** Haute
- **Description :** Même règles que EF-WEB-001/002. Sur mobile, l’authentification OAuth doit ouvrir l’app native (Apple/Google) si disponible.

### EF-MOB-021 — Création d’un ticket depuis mobile
- **Priorité :** Haute
- **Description :** Un résident peut créer un ticket et prendre une photo directement depuis l’appareil photo du téléphone.
- **Critères d’acceptance :**
  - Accès à l’appareil photo via `input[type=file] accept="image/*" capture="environment"`.
  - Taille du fichier limitée à 5 Mo par photo, compression ctôté client si dépassé.  - Si l'auteur est un **locataire**, tous les copropriétaires bailleurs du lot concerné **et** le mandataire (s'il en a un) reçoivent une notification à la création et à chaque changement de statut.
### EF-MOB-022 — Ticket urgence
- **Priorité :** Haute
- **Description :** Un bouton d’urgence (inondation, panne majeure) accessible en 2 taps maximum depuis l’accueil.
- **Critères d’acceptance :**
  - L’envoi d’un ticket urgence déclenche une notification prioritaire immédiate pour le conseil syndical.

### EF-MOB-023 — Consultation et commande de vigiks/télécommandes
- **Priorité :** Haute
- **Description :** Idem EF-WEB-011, adapté à la navigation mobile.

### EF-MOB-024 — Consultation des documents
- **Priorité :** Moyenne
- **Description :** Les documents PDF sont affichables directement dans l’app (visionneuse intégrée ou ouverture dans le lecteur système).

---

## Notifications

### EF-MOB-030 — Notifications push (Web Push API)
- **Priorité :** Basse *(phase 2)*
- **Description :** Envoi de notifications push sur Android (Chrome) via Web Push API / Service Worker. Sur iOS 16.4+, les notifications push PWA sont supportées depuis Safari.
- **Critères d’acceptance :**
  - L’utilisateur peut activer/désactiver les notifications par catégorie (urgences, actualités, tickets, sondages).
  - Les urgences (ticket catégorie `urgence`) ne peuvent pas être désactivées par les membres du conseil syndical.

### EF-MOB-031 — Badge sur l’icône applicative
- **Priorité :** Basse *(phase 2)*
- **Description :** Affichage d’un badge numéroté sur l’icône PWA (API Badging) indiquant les notifications non lues.

---

## Accessibilité & performance mobile

### EF-MOB-040 — Touch targets
- **Priorité :** Haute
- **Description :** Toutes les zones interactives ont une taille minimale de 44 × 44 px (recommandation WCAG 2.2 et Apple HIG).

### EF-MOB-041 — Temps de chargement
- **Priorité :** Haute
- **Description :** First Contentful Paint (FCP) < 2 s sur réseau 4G. Taille du bundle JS < 150 Ko gzippé.

---

## Conformité RGPD

### EF-MOB-060 — Information et consentement à l'inscription
- **Priorité :** Haute
- **Description :** Même exigences que EF-WEB-001 (cases non pré-cochées, lien politique de confidentialité, encadré résumé Art. 13, blocage < 15 ans). Le formulaire mobile adapte l'affichage aux contraintes de l'écran.
- **Critères d'acceptance :**
  - Mentions RGPD et cases à cocher lisibles sans zoom sur 320 px de largeur (contraste ≥ 4,5:1, WCAG 2.2 AA).
  - La politique de confidentialité s'ouvre dans une modale ou un écran dédié (pas un lien quittant l'app).

### EF-MOB-061 — Exercice des droits RGPD depuis le menu Profil
- **Priorité :** Haute
- **Description :** Même périmètre que EF-WEB-091 (accès, rectification, effacement, limitation, portabilité, opposition, directives post-mortem), accessible depuis le menu Profil.
- **Critères d'acceptance :**
  - L'export de données (droit à la portabilité, Art. 20) est partageable via le Share Sheet natif iOS/Android.
  - Le bouton « Supprimer mon compte » demande une confirmation en deux étapes.

### EF-MOB-062 — Double consentement pour les notifications push
- **Priorité :** Haute
- **Description :** Les notifications push PWA requièrent le consentement RGPD (finalité des données) ET la permission système (navigateur/OS). Ces deux consentements sont indépendants et révocables séparément.
- **Critères d'acceptance :**
  - La demande de permission OS (navigateur) n'est déclenchée qu'après obtention du consentement RGPD explicite.
  - La révocation du consentement RGPD désactive immédiatement l'envoi de notifications côté serveur, indépendamment de la permission OS encore active.

---

## Conformité juridique

### EF-MOB-050 — Page « À propos / Licences open source »
- **Priorité :** Moyenne
- **Description :** Une page accessible depuis le menu Profil liste l'ensemble des bibliothèques open source utilisées par l'application, avec pour chacune : nom, version, auteur/organisation, licence (type + texte complet), lien vers le dépôt source.
- **Critères d'acceptance :**
  - La page est accessible sans connexion (incluse dans le cache Workbox).
  - Le contenu est généré automatiquement depuis l'inventaire produit au build (`license-checker`, `pip-licenses`).
  - Les mentions de copyright obligatoires (Apache 2.0 `NOTICE`, MIT header) y figurent intégralement.
  - Les dépendances sous licence GPL/AGPL déclenchent une alerte dans la pipeline CI.

---

## Fonctionnalités UX supplémentaires (mobile)

### EF-MOB-063 — Onboarding progressif à la première connexion
- **Priorité :** Moyenne
- **Description :** Même expérience que EF-WEB-004, adaptée aux contraintes de l'écran mobile.
- **Critères d'acceptance :**
  - Formulaires en plein écran, une étape par écran, navigation avant/arrière par boutons et swipe horizontal.
  - La barre de complétion de profil est affichée dans l'encart Accueil jusqu'à 100 %.
  - Les CTA contextuel (empty states) sont accessibles en 1 tap depuis l'onglet concerné.

### EF-MOB-064 — Calendrier de la résidence (mobile)
- **Priorité :** Moyenne
- **Description :** Même périmètre que EF-WEB-033. Vue semaine par défaut sur mobile, avec swipe horizontal pour naviguer.
- **Critères d'acceptance :**
  - Vue semaine et vue agenda disponibles ; vue mensuelle accessible via un bouton de bascule.
  - Les événements `coupure` et `urgence travaux` sont signalés par une couleur rouge dans toutes les vues.
  - Un événement à venir dans les 24 h déclenche un rappel push configurable.
  - Section accessible depuis l'onglet [Résidence].

### EF-MOB-065 — Recherche globale (mobile)
- **Priorité :** Moyenne
- **Description :** Même périmètre que EF-WEB-111. Sur mobile, la recherche est accessible via une icône loupe dans la barre de navigation supérieure.
- **Critères d'acceptance :**
  - L'écran de recherche s'affiche en modale plein écran avec clavier ouvert d'emblée.
  - Les résultats sont groupés par type et présentés dans une liste scrollable.
  - La recherche respecte le périmètre de l'utilisateur (mandataire : son lot uniquement).
  - Fermeture par swipe bas ou bouton Annuler.

### EF-MOB-066 — Export par lot (mobile)
- **Priorité :** Basse *(phase 2)*
- **Description :** Même périmètre que EF-WEB-112. L'archive ZIP peut être partagée via le Share Sheet natif iOS/Android.
- **Critères d'acceptance :**
  - Le déclenchement de l'export génère une notification push à la disponibilité du fichier.
  - Le lien de téléchargement est valable 72 h.
  - Le fichier peut être enregistré sur l'appareil ou partagé directement.

### EF-MOB-067 — Tableau de bord CS et validation en masse (mobile)
- **Priorité :** Moyenne
- **Description :** Les membres du conseil syndical accèdent depuis l'onglet [Résidence] à un espace CS dédié.
- **Critères d'acceptance :**
  - KPIs visibles sur une carte en haut du tableau de bord : tickets > 7 j, vigiks en attente, comptes à valider.
  - La validation en masse sur mobile utilise des cases à cocher et un bouton flottant « Valider la sélection (N) ».
  - Le tableau de bord CS n'est visible que par les rôles `conseil_syndical` et `admin`.
  - Les notifications d'urgence pour le synthèse sont toujours reçues, même sans ouverture de l'espace CS.

### EF-MOB-068 — Préférences digest de notifications (mobile)
- **Priorité :** Basse *(phase 2)*
- **Description :** Même périmètre que EF-WEB-070. La configuration du digest est accessible depuis Profil > Notifications.
- **Critères d'acceptance :**
  - Options : temps réel / digest quotidien / digest hebdomadaire.
  - Les notifications de catégorie `urgence` ne sont jamais incluses dans un digest.
  - Les préférences sont synchronisées entre le web et le mobile (stockage côté serveur).
