# Multi-copropriétés — architecture cible

> 🧭 **Spécification de CIBLE, en conception — la phase 1 en découle (v2.113.0
> à v2.117.0), la phase 2 est découpée en lots (§8 bis).** Contrairement aux autres fichiers de `specs/`, qui décrivent le produit
> tel qu'il a été conçu à l'origine, celui-ci décrit **où le produit va**. Il est
> rédigé le 07/10/2026, à partir des arbitrages de l'auteur pris le même jour.
>
> Le **travail** vit dans les tickets : phase 1 à partir de #1718, phase 2 de #1743
> à #1751. Ce document en
> porte les **décisions** et leurs raisons. Il se met à jour **à chaque arbitrage**,
> daté. Toute décision qui n'y figure pas n'est pas prise.

## 1. L'objectif et l'exigence

Rendre le site capable de servir **plusieurs dizaines de copropriétés**, hébergées
dans le cloud, chacune dans un **caisson étanche**.

**Caisson étanche** = aucune donnée, aucun fichier, aucun courriel, aucune session,
aucun coût d'IA d'une copropriété ne peut être lu, modifié ou déduit depuis une
autre — **ni par un bug applicatif oublié**. C'est une exigence de **sécurité, de
rang 1** : en cas de conflit avec la factorisation ou la simplicité d'exploitation,
l'étanchéité tranche.

Le critère qui départage les architectures : **combien de lignes de code faut-il
oublier pour qu'une fuite se produise ?** Une architecture où un seul `WHERE`
oublié suffit n'est pas étanche, elle n'est que *disciplinée*.

## 2. Les décisions prises (07/10/2026)

| # | Sujet | Décision | Conséquence directe |
|---|---|---|---|
| D1 | Échelle | **plusieurs dizaines** de copropriétés | une installation par copro (option A) devient inexploitable comme modèle général |
| D2 | Hébergement | **cloud** | la plateforme quitte les Raspberry Pi ; la haute disponibilité maison (bascule, verrou, réplication de `app.db`) ne se transpose pas : elle se **remplace** par celle de l'hébergeur |
| D3 | Architecture | **option B** : une application, **une base par copropriété** | §3 et §4 |
| D4 | Moteur de base | **PostgreSQL**, une base **et un rôle** par copropriété | §4.3 ; SQLite est abandonné pour la plateforme |
| D5 | Opérateur de plateforme | **aucun accès aux données** d'une copropriété, même pour l'assistance | §4.7 ; l'assistance passe par l'administrateur de la copro |
| D6 | Canaux et services | **par copropriété**, et **chaque service se désactive** | §4.8 ; premier lot : #1718 |
| D7 | Licence | **GNU AGPLv3 pure**, sans clause commerciale — appliquée en v2.116.0 | §7 |
| D8 | Une personne dans deux copros | le cas existe, **rare** : **deux comptes indépendants**, un par caisson — confirmé le 08/10/2026 | §4.7 |
| D9 | Nom de la plateforme (07/10/2026) | **CoproConnect** ; la résidence garde le sien, « 5Hostachy » | §8, phase 1 : le nom de la **plateforme** (attribution, lien vers le source) et celui de la **résidence** (administrable) sont deux réglages distincts |
| D10 | Variante de la licence (07/10/2026) | **`AGPL-3.0-or-later`** | §7 |

## 3. Les trois architectures comparées

| | **A — une instance par copro** | **B — une application, une base par copro** | **C — une base partagée, colonne `copropriete_id`** |
|---|---|---|---|
| Étanchéité | 🟢 totale (processus, base, fichiers, secrets séparés) | 🟢 données ; 🟠 **mémoire du processus** partagée (§4.5) | 🔴 un filtre oublié sur 82 tables = une fuite |
| Changement du code | faible | moyen : un **contexte de copropriété** résolu à l'entrée de chaque requête | massif : toutes les tables, toutes les requêtes |
| Exploitation | 🔴 N piles à déployer, migrer, superviser | 🟠 N bases à migrer et sauvegarder, une seule pile | 🟢 une base |
| Restaurer ou rendre **une** copro | 🟢 | 🟢 une base + un préfixe de fichiers | 🔴 extraction ligne à ligne |
| Échelle | quelques copros | quelques dizaines à quelques centaines | des milliers |

**B est retenue** (D1, D3). Elle est la seule à combiner l'étanchéité des données et
une exploitation tenable à plusieurs dizaines. Son point faible, la mémoire du
processus partagée, se ferme par les règles du §4.5.

**A reste la solution de repli** pour une copropriété qui exigerait un hébergement
dédié : un code propre pour B l'est aussi pour A. **C est écartée** : elle repose sur
la discipline, pas sur la structure.

## 4. L'architecture cible

### 4.1 Le contexte de copropriété

Chaque requête est rattachée à **une seule** copropriété, résolue **à l'entrée**, et
toute ressource s'obtient de ce contexte :

```
requête ── nom d'hôte (residence.domaine) ──► registre de la plateforme
                                                   │
                     ┌─────────────────────────────┼──────────────────────────────┐
                     ▼                             ▼                              ▼
          base PostgreSQL + rôle        préfixe de stockage objet       secret de signature,
          de CETTE copro                de CETTE copro                  expéditeur, services
```

Règles :
1. **Résolution par nom d'hôte**, jamais par un paramètre, un en-tête libre ou un
   champ de formulaire. Une copro = un sous-domaine : cookies, stockage du
   navigateur et CSP sont alors cloisonnés **par le navigateur**, sans code.
2. **Un hôte inconnu ne résout rien** : réponse d'erreur, jamais de copropriété
   « par défaut ».
3. **Aucune ressource ne se construit depuis la configuration globale** : base,
   fichiers, secret, expéditeur, clé d'IA viennent tous du contexte.

### 4.2 Le registre de la plateforme

La seule donnée **commune** : la liste des copropriétés et de quoi résoudre leur
contexte (identifiant, sous-domaine, état actif ou suspendu, références vers les
secrets). Il ne contient **aucune donnée personnelle** de résident ; les secrets
eux-mêmes vivent dans le coffre de l'hébergeur, pas dans le registre.

### 4.3 Les données — PostgreSQL, une base et un rôle par copropriété (D4)

- **Un rôle PostgreSQL par base**, qui n'a de droits que sur sa base : un contexte
  mal résolu **échoue à la connexion** au lieu de lire la mauvaise copro.
  L'étanchéité descend jusque dans le moteur.
- **Connexions** : plusieurs dizaines de bases avec un pool chacune → un regroupeur
  de connexions (type PgBouncer), ou des pools paresseux et bornés.
- **Migrations** : la même migration s'applique à toutes les bases, avec la version
  **suivie par base**, un **arrêt au premier échec**, et une copro en échec isolée
  sans bloquer les autres en lecture.
- **Bascule depuis SQLite** : repartir d'une **migration initiale PostgreSQL** qui
  pose le schéma actuel, plutôt que de rejouer l'historique écrit pour SQLite.
  Les données de la résidence actuelle se reprennent par un export / import
  **vérifié** (comptes de lignes par table, sommes de contrôle).
- **Tests** : la CI tourne **sur PostgreSQL**. Des tests sous SQLite masqueraient
  les écarts de typage, de casse et de transactions.

### 4.4 Les fichiers

Stockage objet, **un préfixe ou un compartiment par copropriété**, avec des droits
d'accès qui l'imposent. Un chemin de fichier ne se construit **jamais** à partir
d'une donnée de la requête.

### 4.5 La mémoire du processus — le point faible de B

Avec une seule application pour toutes les copros, tout état gardé **en mémoire**
et indexé par un simple identifiant fuit d'une copro à l'autre : l'utilisateur
n° 12 de la copro A lirait le cache de l'utilisateur n° 12 de la copro B.

- **Règle** : tout état mutable de module est **indexé par la copropriété**, ou
  n'existe pas.
- **Garde-fou** : un contrôle statique refuse tout nouvel état de module qui ne
  l'est pas — `api/tests/test_etat_module_par_copropriete.py` (#1743, 08/10/2026).
  Il précède tout le reste, puisqu'il ne coûte rien tant qu'il n'y a qu'une
  copropriété.
- **Recensés le 08/10/2026 par ce contrôle — neuf, et non quatre** comme l'écrivait
  le relevé de la veille, fait à la main. La liste fait foi **dans le test**, et
  ne se recopie pas ici. Deux familles :
  - **à indexer par copropriété** (lot P2-2) — dont le cache de l'**arbre des
    périmètres** et le quota horaire de l'IA par personne, que le relevé à la main
    n'avait pas vus ;
  - **du processus**, sans donnée de copropriété (configuration de la plateforme,
    catalogue d'icônes, repli d'un caractère pour la recherche, diagnostic du
    dernier rendu PDF). Le `lru_cache` de `config.py` y est rangé : ce qui est
    propre à une copropriété sort de `settings` au lot P2-2, et le cache qui reste
    est celui de la plateforme.

### 4.6 Les tâches planifiées

Sauvegarde, maintenance, relances, rattrapages : chaque tâche s'exécute **par
copropriété**, dans le contexte de celle-ci, et **l'échec d'une copro ne bloque
pas les autres**. Chaque exécution est journalisée par copro.

### 4.7 Les identités, les rôles et l'opérateur

- **Un compte appartient à une copropriété.** Le même courriel peut exister dans
  deux copros sous la forme de **deux comptes indépendants** (D8, confirmée le 08/10/2026).
  Aucun pont, aucun sélecteur entre caissons.
- **Deux niveaux d'administration** : l'**administrateur de copro**, qui gère sa
  résidence, et l'**opérateur de plateforme**, qui crée, suspend et supervise les
  copropriétés. Le rôle `admin` actuel mêle les deux : il se scinde.
- **L'opérateur ne lit aucune donnée d'une copro** (D5). Sa supervision (santé,
  volumes, erreurs) ne contient **aucune donnée personnelle** : ni nom, ni
  courriel, ni contenu d'affaire dans les journaux qu'il lit.

### 4.8 Les canaux et les services (D6)

- **Un registre unique des services**, chacun activable par copropriété : IA,
  diffusion WhatsApp, réception des réponses par courriel… C'est le **premier
  lot** (#1718), utile dès aujourd'hui avec une seule copro. Un réglage rangé en
  base y est cloisonné **gratuitement** par B.
- 🔴 **Les courriels de sécurité ne sont pas un service** : mot de passe oublié,
  vérification d'adresse, alertes d'administration. Aucun interrupteur ne les
  coupe. Le registre sépare le **service**, qui se coupe, de l'**infrastructure**
  (SMTP), qui ne se coupe pas.
- **Courriel** : un sous-domaine d'envoi par copro (SPF et DKIM propres), et une
  adresse de réception (`affaire@`) qui identifie la copro **sans ambiguïté**.
- **WhatsApp** : un compte par copro. La passerelle repose sur une bibliothèque non
  officielle, avec un risque de blocage du compte : c'est un service désactivable.
- **IA** : clé, plafonds et coûts **par copro**. Le registre des usages de l'IA
  (`utils/llm_usages.py`) en est déjà la forme.

### 4.9 Les sauvegardes et la réversibilité

- Une sauvegarde **par base**, chiffrée, **restaurable seule**, sans toucher aux
  autres copros.
- Avec D5, la clé de chiffrement ne doit pas permettre à l'opérateur de lire les
  données **en routine**. Le mécanisme reste à concevoir.
- **Départ d'une copropriété** : elle repart avec sa base et ses fichiers, puis
  ceux-ci sont supprimés de la plateforme.

## 5. Les garde-fous

1. **Test d'étanchéité permanent** : deux copropriétés aux **identifiants
   identiques** (même `user.id`, même `ticket.id`). Chaque route est appelée avec
   la session de A sur les objets de B → refus partout. Il comporte un **cas zéro**
   et un **témoin** qui doit servir. Un test qui ne peut pas s'exécuter rend
   **INCONNU**, jamais OK.
2. **Contrôle statique de la mémoire du processus** (§4.5).
3. **Jeton de A présenté à B** : refusé, puisque le secret de signature diffère.
4. **Hôte inconnu** : aucune copropriété résolue (§4.1, règle 2).
5. **Journaux de l'opérateur** : un contrôle refuse l'apparition d'une donnée
   personnelle (§4.7).

## 6. Ce que le code suppose aujourd'hui (relevé le 07/10/2026)

Le produit a été pensé **réutilisable par une autre copropriété, une installation
chacune** : le patrimoine et l'arbre des périmètres sont administrables, *« une
autre copropriété n'a ni AFUL, ni quatre bâtiments »* (`models/perimetre.py`). Il
n'a **jamais** été pensé pour plusieurs copropriétés dans une même installation.
Le relevé ci-dessous **vieillit avec le code** : le revérifier avant de s'en servir.

| Hypothèse mono-copropriété | Où | Ce qu'il faudra en faire |
|---|---|---|
| `Copropriete` est un singleton | `select(Copropriete).first()` dans `seed/__init__.py`, `routers/flux/sante.py`, `routers/uploads.py`, `utils/syndic.py`, `utils/synthese_affaire/rassemblement.py` | rester un singleton **dans sa base** : B n'y change rien |
| 2 tables sur 82 portent `copropriete_id` | `Batiment`, `ContratEntretien` | sans objet avec B (c'est C qui l'exigerait) |
| `Lot.batiment_id` est nullable (parkings) | `models/copropriete.py` | sans objet avec B ; un piège direct pour C |
| `Utilisateur.email` unique globalement, rôles globaux | `models/core.py`, `models/roles.py` | unique **dans sa base** (D8) ; scission de `admin` (§4.7) |
| Une base, un dossier de fichiers, un secret de signature | `config.py` : `database_url`, `uploads_dir`, `secret_key` | passent au contexte de copropriété (§4.1) |
| Domaine, adresses et nom en dur | `5hostachy.fr` 14 fois dans `api/` et `front/`, `contact@`, `noreply@`, « Hostachy » dans 14 fichiers du front | configuration de la copropriété (phase 1) |
| État en mémoire du processus | voir §4.5 | indexé par copro ou supprimé |
| Tâches planifiées globales | `add_job` dans `main.py`, `utils/maintenance.py`, `utils/backup.py`, `utils/taches.py`, `utils/rattrapage.py` | par copro (§4.6) |
| Adhérence à SQLite | 39 fichiers d'`api/app` citent `sqlite` ou `PRAGMA` (`database.py` lit `sqlite_master`), migrations en mode `batch`, scripts d'exploitation | réécrits pour PostgreSQL (§4.3) |
| Un compte WhatsApp, une boîte de réception, une configuration d'IA | `whatsapp-bridge/`, `utils/courriel_ingestion.py`, `config_llm` | par copro (§4.8) |

## 7. La licence — GNU AGPLv3 (D7)

**Fait le 08/10/2026 en v2.116.0 (#1726).** La clause d'usage commercial de
l'ancienne licence a disparu : le projet est sous la **GNU AGPLv3**, une licence
libre reconnue par l'OSI et la FSF. ⚠️ Ce qui suit n'est pas un avis juridique.

- **Assumé** : n'importe qui peut héberger le logiciel et le proposer comme service,
  y compris contre paiement, **à condition de publier ses modifications**. La
  seule protection qui reste est la **marque** : la clause « nom et logo » sort de
  la licence et devient une politique de marque séparée.
- **Obligation pour la plateforme** (AGPLv3 §13) : chaque utilisateur qui se sert
  du site par le réseau se voit **proposer le code source** de la version qui
  tourne. Un lien vers le source figure donc dans l'interface de chaque copro.
- **Aucune condition additionnelle** (AGPLv3 §7) — arbitré le 08/10/2026 :
  « AGPLv3 pure ». L'attribution se limite aux mentions de copyright.
- **Les versions déjà publiées** restent sous l'ancienne licence.
- **Tranché le 07/10/2026 (D10)** : **`AGPL-3.0-or-later`**. Les versions ultérieures
  de l'AGPL publiées par la FSF s'appliqueront au choix de qui reçoit le code ;
  c'est l'identifiant SPDX à écrire dans `LICENSE`, `REUSE.toml` et les en-têtes.
- **La marque** porte le nom de la **plateforme**, **CoproConnect** (D9), pas celui
  de la résidence. Une recherche web du 07/10/2026 n'a trouvé aucun produit de ce
  nom ; elle **ne remplace pas** une recherche d'antériorité (INPI, EUIPO) avant de
  s'en servir publiquement.
- **Vérifié avant le changement** (08/10/2026) : un seul auteur humain dans tout
  l'historique, aucun contributeur extérieur ; les cinq exceptions « à valider »
  de `docs/licences-tierces.md` analysées compatibles, analyse validée par
  l'auteur (motifs : `scripts/ci/licences_politique.py`).
- **La politique de marque** reste à écrire : #1736.

## 8. Le phasage

Chaque phase apporte de la valeur **seule**, même si le chantier s'arrête après
elle.

| Phase | Contenu | Prérequis |
|---|---|---|
| 0 | Décisions restantes (§9) | — |
| 1 | **Mono-copro propre** : services activables (#1718, v2.113.0) ; identité de la copropriété en configuration et nom de la plateforme, CoproConnect, avec le lien vers le source (#1725, v2.114.0) ; consignes de la fiche arrivant administrables (#1727, v2.115.0) ; licence AGPL (#1726, v2.116.0) ; logo de la résidence téléversable (#1728, v2.117.0). Reste : la politique de marque (#1736) | aucun |
| 2 | **Contexte de copropriété** dans le processus (§4.1, §4.5, §4.6), en production avec **une seule** copro, le test d'étanchéité déjà actif sur deux copros factices. Neuf lots, §8 bis (#1743 à #1751) | phase 1 |
| 3 | **Plateforme cloud** : hébergeur, PostgreSQL (§4.3), stockage objet (§4.4), outillage de flotte (créer, migrer, sauvegarder et restaurer **une** copro), supervision sans donnée personnelle | hébergeur choisi |
| 4 | **Copropriété pilote** : une seconde résidence réelle et volontaire | phase 3 |
| 5 | Accueil autonome des copropriétés ; facturation selon le modèle économique | modèle économique |

## 8 bis. La phase 2 en lots (proposition du 08/10/2026)

**Le chemin retenu : transformer 5Hostachy en CoproConnect, pas migrer.** Le même
dépôt devient le code de la plateforme ; la résidence en serait la première
copropriété (question 7, §9). C'est la suite logique de B (§3) : un code propre
pour B l'est aussi pour A, et la licence (§7) est déjà celle de la plateforme.

La phase 2 se mène **entièrement sur les Raspberry Pi, avec SQLite et une seule
copropriété**. Chaque lot a une valeur seul, et diminue le coût de la phase 3
quel que soit l'hébergeur. Proposée et validée le 08/10/2026 (« consigne la
proposition dans la spec et ouvre les tickets ») ; le code de chaque lot reste
soumis à accord, lot par lot.

| Lot | Contenu | Taille | Prérequis | Ticket |
|---|---|---|---|---|
| P2-1 | **Contrôle de la mémoire du processus** : tout nouvel état mutable de module est refusé ; les existants sont déclarés, à indexer ou du processus (§4.5) | S | — | #1743 |
| P2-2 | **Un seul accès aux ressources** d'une copropriété — base, fichiers, secret, expéditeur, services — par un module `contexte` qui lit `settings` tant qu'il n'y a qu'une copro ; garde-fou contre l'accès direct (§4.1, règle 3). Les états « à indexer » de P2-1 s'y soldent | L | P2-1 | #1744 |
| P2-3 | **Tâches planifiées par copropriété** : une enveloppe, un journal par copro, l'échec de l'une ne bloque pas les autres (§4.6) | M | P2-2 | #1745 |
| P2-4 | **Test d'étanchéité** sur deux copros factices aux identifiants identiques, avec cas zéro et témoin (§5.1, §5.3) | M | P2-2 | #1746 |
| P2-5 | **CI sur PostgreSQL** (informative, puis requise) ; adhérence à SQLite regroupée dans un module de dialecte ; migration initiale PostgreSQL préparée (§4.3) | M | — | #1747 |
| P2-6 | **Stockage des fichiers** derrière une interface, disque local puis stockage objet, préfixe par copro (§4.4). Décision à y prendre : `/uploads/*` n'est plus servi en statique par Caddy | M | P2-2 | #1748 |
| P2-7 | **Export / import vérifié** d'une copro (comptes et sommes de contrôle par table) : sauvegarde vérifiée aujourd'hui, passage à PostgreSQL demain, réversibilité ensuite (§4.3, §4.9) | M | — | #1749 |
| P2-8 | **Scission du rôle `admin`** : administrateur de copro et opérateur de plateforme, sans donnée personnelle (§4.7, §5.5) | M | — (D8 confirmée le 08/10/2026) | #1750 |
| P2-9 | **Résolution par nom d'hôte** (§4.1, règles 1 et 2). ⚠️ Le standby est servi par son IP locale (`ORIGIN`) : le registre rattache **plusieurs hôtes** à une même copro. En dernier | S | P2-2 | #1751 |

**Ce que la phase 2 ne fait pas, exprès :**

- **aucune colonne `copropriete_id`** : ce serait l'option C, écartée (§3) ;
- **pas de PostgreSQL en production sur les Raspberry Pi** : la phase 3 le
  ferait deux fois, et la base actuelle courrait un risque pour rien ;
- **pas d'outillage de flotte** (créer, migrer, sauvegarder N copros) avant le
  choix de l'hébergeur : il en dépend.

## 9. Les questions encore ouvertes

1. **RGPD** : vis-à-vis de chaque syndicat des copropriétaires (responsable de
   traitement), l'opérateur devient **sous-traitant**. Il faudra un contrat de
   sous-traitance, un registre, des mentions légales et une politique de
   confidentialité **par copro**, et un hébergeur conforme. À faire valider.
2. **Hébergeur** : PostgreSQL géré, stockage objet, coffre à secrets, localisation
   des données.
3. ~~**Nom du produit**~~ — tranché le 07/10/2026 : **CoproConnect** (D9). Reste la
   recherche d'antériorité de la marque (§7).
4. ~~**D8**~~ — confirmée le 08/10/2026 : **deux comptes indépendants**.
5. **Licence** : la variante est tranchée (`-or-later`, D10) ; restent la politique
   de marque et les vérifications d'avant changement (§7).
6. **Modèle économique** : gratuit ou facturé. L'AGPLv3 permet de facturer
   l'hébergement ; elle interdit seulement d'en fermer le code.
7. **La résidence actuelle** : devient-elle une copropriété de la plateforme, ou
   reste-t-elle sur les Raspberry Pi ? *Recommandation du 08/10/2026, non
   tranchée* : la première copropriété de la plateforme, qui sert de copro de
   non-régression ; la haute disponibilité des Raspberry Pi s'éteint alors en
   phase 3.
