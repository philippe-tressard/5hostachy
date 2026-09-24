# CLAUDE.md — 5Hostachy

Règles de développement à appliquer dans toutes les sessions sur ce projet.

## Principe fondamental

Avant toute implémentation : **grep le pattern existant**. Si le pattern existe ≥ 2 fois → l'appliquer à l'identique. Si une demande contredit un pattern établi → signaler le conflit et demander confirmation.

Les références canoniques sont dans `.claude/skills/` (voir le tableau ci-dessous).

---

## Stack

- **Backend** : FastAPI + SQLModel + SQLite WAL + Alembic (`api/`)
- **Documents imprimables** : HTML/CSS → PDF via WeasyPrint (libs système dans `api/Dockerfile`)
- **Frontend** : SvelteKit v2 + TypeScript strict + Vite + PWA (`front/`)
- **Infra** : Docker Compose + Caddy + Raspberry Pi 5
- **Langue** : français exclusif (interface + nommage des champs)

---

## Consignes chargées à la demande

Ce fichier ne porte que ce qui doit être vrai **en permanence**. Le détail vit dans
`.claude/skills/`, découvert automatiquement par Claude Code et chargé **seulement
quand la tâche le demande** — ouvrir la skill *avant* d'agir, jamais après.

| Tâche | Skill à charger |
|---|---|
| MEP, déploiement, pré-check, post-check, rollback | `.claude/skills/mep-precheck` |
| Infra, bascule, RPi, base, WhatsApp, monitoring, incident | `.claude/skills/infra-rpi` |
| Écran, composant, libellé, pattern d'interface | `.claude/skills/ux-patterns` |
| Page ou composant SvelteKit, store, appel API côté front | `.claude/skills/svelte-patterns` |
| Nouveau modèle, schéma, router, migration | `.claude/skills/api-scaffold` |
| Auth, droits, secrets, exposition publique | `.claude/skills/security-audit` |
| Documentation utilisateur — manuel **et** `README.md` | `.claude/skills/user-manual` |

Les bonnes pratiques **génériques** — valables pour un autre projet — sont dans le
socle `~/.claude/standards/`. Ce fichier-ci ne contient que leur **instanciation
5Hostachy** : chemins, seuils, commandes.

> 📖 **Routage du socle : `~/.claude/CLAUDE.md` §1** (source unique, déjà en contexte
> — quel standard charger avant quelle tâche). Mode d'emploi, règle de placement et
> entretien : `standards/INDEX.md`. Une règle générique ne se recopie **jamais** ici :
> elle s'écrit dans le socle et bénéficie alors aux quatre projets.

---

## 🚨 Règle d'or anti-corruption DB — ne dépend d'aucun chargement à la demande

**Ne JAMAIS ouvrir `app.db` depuis un process tiers tant que l'API tourne — même en
lecture seule.** `docker exec … PRAGMA` et `sqlite3` hôte sont **interdits** : le
process tiers se croit dernière connexion, `unlink` le WAL sous le pool SQLAlchemy,
et l'API écrit ensuite dans des inodes orphelins → `disk I/O error`, 503, puis
**perte des données** au prochain arrêt. À chaud, passer par les endpoints
in-process : `POST /admin/db/checkpoint`, `GET /admin/db/integrite`. VACUUM, copie ou
swap de fichier → **stopper l'API d'abord** (0 writer).

Signature de diagnostic, conduite à tenir et historique des trois incidents :
`.claude/skills/infra-rpi`.

> 📖 `standards/06-donnees-et-integrite.md` §1 — le principe généralisé à **tout état
> multi-fichiers qu'un processus tient ouvert**, pas seulement une base : il s'est
> reproduit à l'identique sur l'état d'authentification WhatsApp (24/07/2026).

---

## Front — les quatre règles qui ne se négocient pas

Le détail des patterns est dans `.claude/skills/ux-patterns` et
`.claude/skills/svelte-patterns` — les charger avant d'écrire un écran.

> 📖 `standards/11-interface-et-ux.md` (un pattern par notion, accessibilité,
> formulaires, archiver ≠ supprimer) · `standards/03-securite.md` §4 (assainissement)
> · `standards/02-factorisation.md` §2 (pourquoi dates et montants sont les deux
> récidivistes de la duplication).

1. **XSS** : jamais `{@html contenu}`, toujours `{@html <assainisseur>(contenu)}`.
   Ils sont **trois**, tous exportés par `$lib/sanitize.ts` et tous adossés à
   DOMPurify : `safeHtml` (HTML riche), `safeRichContent` (riche ou texte, **sans**
   enveloppe — appelé à l'intérieur d'un `<p>`), `safeDescription` (idem, **avec**
   enveloppe `<p>`). Cette règle ne nommait que le premier alors que les trois
   étaient en service : c'est ce qui a fait croire à 19 écarts qui n'en étaient pas
   (#429).

   🔒 **Garde-fou : `npm run lint:html`** (`front/scripts/check-html.mjs`), en CI
   depuis le 18/08/2026. Il lit la liste des assainisseurs **dans `sanitize.ts`** —
   une liste recopiée diverge au premier ajout — et exige que le nom vienne de
   l'**import**, pas de la portée du fichier : une fonction locale homonyme qui ne
   ferait rien passerait sinon. C'est ainsi qu'a été trouvée `renderContent`
   (`tickets/[id]`), copie littérale de `safeDescription`, correcte par chance.

   **Deux** exceptions, et deux seulement — relevées par l'audit du 18/08/2026,
   qui en a trouvé une non déclarée ; elles sont **déclarées dans le contrôle**
   (`EXCEPTIONS`), qui échoue si l'une d'elles cesse de servir :
   - `Icon.svelte` — SVG codé en dur côté serveur ;
   - `QRCode.svelte` — SVG produit **localement** par `qrcode-generator` à partir
     d'une donnée encodée en modules, jamais interpolée dans le balisage.

   ⚠️ Une exception non écrite n'est pas une exception, c'est un oubli qui
   ressemble à une décision. Toute nouvelle exception s'ajoute **ici** avec sa
   raison, sinon la règle devient « sauf quand on a jugé que ça allait ».
2. **Dates et montants** : ne jamais réimplémenter un format dans une page.
   `$lib/date.ts` (`fmtDate`, `fmtDatetime`, `fmtMonthYear`…), `$lib/utils.ts`
   (`fmtMontant`, `perimetreLabel`), et côté API `app/utils/dates_fr.py`. Deux
   garde-fous échouent en CI : `api/tests/test_dates_fr.py` et `npm run lint:dates`.
3. **Accessibilité** : tout élément cliquable non-`<button>` porte `role="button"`,
   `tabindex="0"` et `on:keydown` (Enter/Space) ; `aria-label` sur les boutons
   icône-seule ; `role="dialog"` + `aria-modal="true"` sur les modales
   (`standards/11-interface-et-ux.md` §2, seule source générique ; les skills y renvoient).
4. **Icônes de contexte** : 📍 = lieu physique, 🔹 = périmètre logique — **jamais
   mélangés**, et le périmètre par défaut ne s'affiche pas — la question se pose à
   `estPerimetreParDefaut` (`$lib/perimetres`), jamais par un `=== 'résidence'` :
   le code n'en contient plus un seul, et le nom du périmètre racine est
   **administrable**.

---

## Conventions Backend (Python / FastAPI)

> 📖 `standards/06-donnees-et-integrite.md` §3 (migrations : chaîne linéaire, jamais
> de f-string SQL, le code et le schéma voyagent ensemble) et §4–5 (suppression
> logique, montants en entiers) · `standards/03-securite.md` §1–5 (autorisation
> centralisée, liste blanche, entrées/sorties, session et transport).

### Modèle SQLModel
- Un modèle vit dans le module de **son domaine** sous `app/models/` (`acces`,
  `communaute`, `prestataires`, `gouvernance`…) — **jamais dans `core.py`**, qui
  dépasse 500 lignes et que le garde-fou de modularité refuse de voir grossir.
  Un module neuf s'**importe dans `models/__init__.py`** : c'est ce qui enregistre
  la table auprès de SQLModel — oublié, elle manque à `create_all` sans un mot.
- `core.py` **ré-exporte** les modèles extraits (imports `# noqa: E402` en milieu
  de fichier). Ils laissent `from app.models.core import X` valable après chaque
  extraction — **et ils enregistrent** : `alembic/env.py` n'importe que `core`, et
  c'est par eux qu'Alembic voit la moitié des tables. Pas un doublon à nettoyer
  en passant (#1157). 🔒 `test_modeles_enregistres.py` : chaque module de
  `app/models/` doit être chargé par `import app.models.core`.
- `__tablename__` = snake_case français
- Champs en français snake_case : `statut_validation`, `date_debut`
- Timestamps : suffixe `_le` → `cree_le`, `mis_a_jour_le`
- FK : `{modele}_id = Field(default=None, foreign_key="table.id")`
- Enums : `class MonEnum(str, Enum)` → slugs français lowercase
- **Archiver, pas une colonne `actif` par réflexe.** Les objets qui quittent les
  listes se déclarent dans `utils/archivage.REGLES` — la règle unique, avec son
  test de concordance. La plupart des tables n'ont ni `actif` ni `archivee`, et
  c'est voulu : un booléen ajouté à côté ferait une seconde façon de disparaître.
- Lire un objet ou rendre 404 : `utils/recuperer.ou_404(session, Modele, id,
  "libellé")` — jamais `session.get` suivi d'un `raise HTTPException(404)`, que
  #1047 résorbe.
- La valeur d'une énumération (`categorie`, `statut`…) : `utils/valeurs.valeur(x)`,
  jamais `str(x)` — qui rend « CategorieTicket.etude_travaux » — ni un
  `getattr(x, "value", x)` recopié (il l'était neuf fois ; 🔒 `test_valeur_source_unique`).
- Lire un objet pour le RENDRE : `Schema.model_validate(objet)` puis les seuls
  champs dérivés — jamais une recopie colonne par colonne, où tout oubli part à
  sa valeur par défaut sans un mot (🔒 `test_ticket_read_rend_le_modele`, #1092).

> 🔴 Cette section décrivait jusqu'au 23/09/2026 un backend disparu : « modèle
> dans `models/core.py` », « trois schémas dans `schemas.py` », « soft delete par
> `actif` ». Suivre la consigne violait la modularité (rang 1), et ce fichier est
> relu à chaque session (#1046).

- **Nommage : français, tables, routes et tags compris.** Les noms anglais
  existants (9 tables, 46 routes) sont **figés** dans `api/tests/test_nommage_francais.py`,
  qui refuse le suivant : ils se renomment **au fil de l'eau**, quand un lot touche
  déjà la table ou la route — jamais en bloc (migration + client front) —, et on retire
  alors l'entrée, la liste ne fait que décroître. Un **tag** OpenAPI s'écrit en
  minuscules à tirets (`carnet-entretien`), un **préfixe** de routeur au pluriel (#1056).

### Schémas Pydantic
- Trois formes par entité exposée : `EntiteCreate` (entrée, sans id ni
  horodatage), `EntiteRead` (sortie, `class Config: from_attributes = True` —
  la forme de tout le dépôt), `EntiteUpdate` (tout `Optional`, PATCH partiel).
- Ils vivent dans le `schemas_<domaine>.py` de l'entité (`schemas_tickets`
  — actualités comprises —, `schemas_evenement`…), que `schemas.py` ré-exporte.
- Un schéma **propre à un seul routeur** — le corps d'un geste, la réponse d'un
  écran — vit à côté de lui (dans le routeur ou son `_schemas.py`). Le mettre
  dans un fichier partagé créerait un couplage que personne n'a demandé.
- `schemas_communs.py` n'importe RIEN du projet : c'est ce qui évite le cycle
  `schemas` ⇄ `schemas_tickets`. Ne pas lui en ajouter.

### Migrations Alembic
- ID séquentiel 4 chiffres : `0087`, `0088`…
- **Jamais** modifier une migration existante — créer une nouvelle
- **Jamais** de f-string dans `op.execute()` pour une **valeur** →
  `text(...).bindparams(...)`. Un **identifiant** (nom de table ou de colonne)
  ne peut pas se lier en SQLite : il s'interpole depuis une constante du fichier,
  et on l'écrit en commentaire. Cette nuance manquait, et la règle en « jamais »
  était donc fausse treize fois sur quarante — une consigne qu'on ne peut pas
  suivre à la lettre est une consigne qu'on cesse de lire.
  🔒 `test_migrations.py` refuse la **28ᵉ** f-string non liée ; les 27 existantes
  sont **figées** dans le test — une migration appliquée ne se modifie jamais,
  donc c'est de l'historique et non un retard à résorber. Ruff `S608` couvre le
  code vivant (`api/app/`), pas `alembic/`, pour la même raison.
- SQLite : pas de `ALTER TYPE`, pas de `CREATE TYPE`, et **pas de `ForeignKey`
  dans un `add_column`** — SQLite refuse d'altérer les contraintes d'une table
  existante, la migration crashe *après* avoir ajouté la colonne, et `start.sh`
  (`set -e`) arrête le conteneur. C'est arrivé **deux fois** (0117 le 25/07/2026,
  0165 le 01/09) sans que personne le voie : le redémarrage suivant passe grâce à
  la garde d'idempotence. Poser une colonne simple, et ne pas déclarer
  `foreign_key` dans le modèle non plus — sinon base neuve et base migrée
  divergent. `api/tests/test_migrations.py` le refuse.
- `start.sh` a `set -e` : une migration qui crash = conteneur bloqué

### Dépendances d'auth
| Dependency | Usage |
|-----------|-------|
| `get_current_user` | Tout utilisateur connecté |
| `require_cs_or_admin` | Création/modification de contenu |
| `require_admin` | Suppression définitive, config système |
| `require_proprietaire` | Fonctions propriétaires |
| `get_acting_user` | Délégation (header `X-Acting-As`) |

Ces cinq-là **refusent** (elles lèvent un 403). À côté vivent les **prédicats**,
qui *disent* sans refuser — et qui s'appellent, jamais ne se redérivent :

| Prédicat | La question |
|---|---|
| `est_moderateur(user)` | conseil syndical **ou** admin — « qui modère » |
| `est_rattache_au_lot(session, user, lot_id)` | « ce lot est le mien » (lien **actif** exigé) |
| `peut_commenter` / `peut_editer` | l'auteur, le « saisi pour », l'admin (+ le CS pour commenter) ; une **actualité** : le CS et son auteur — l'arrivant corrige son annonce, sans décider qui la lit (#1091) |

Et les règles d'**appartenance** — « cet objet est-il le mien ? » — vivent dans
`auth/appartenance.py`, **jamais chez un routeur** : elles ne sont pas des
`Depends`, donc `test_autorisation.py` ne les voyait pas (#1028).

⚠️ Elles ne sont **pas** fondues en une fonction, et c'est mesuré : le bail d'un
bailleur refuse en **403** et admet le CS ; l'accès d'un porteur refuse en **404**
et ne l'admet pas ; l'aidant d'une délégation refuse en 403 sans l'admettre non
plus. Trois combinaisons pour trois règles — les réunir demanderait quatre
paramètres de variation. Ce qu'elles gagnent est un **lieu** : côte à côte, on
voit ce qui diverge et pourquoi. 🔒 `test_appartenance_source_unique.py`.

🔒 Écrire `has_role(conseil_syndical, admin)` en ligne est refusé par
`api/tests/test_moderateur_source_unique.py`. Il l'était **vingt-six fois** avant le
20/09/2026 — dont trois dans `deps.py` lui-même —, parce que le prédicat existait
sous le nom `peut_commander` : un nom qui décrivait **un geste** (fixer les champs de
commandement d'un ticket) n'est appelé que par ce geste, et les vingt-cinq autres
points d'usage n'ont jamais vu qu'ils posaient la même question (#1028).

### Documents imprimables (PDF)
- Thème commun : `app/utils/pdf_theme.py` — logo, palette de la charte, data-URI (image/QR), `html_to_pdf()`.
  **Ne jamais** redéfinir une palette, un logo ou un moteur PDF ailleurs.
- Le HTML doit être **autonome** : CSS dans `<style>`, images en data-URI (rendu hors requête HTTP).
- Format de page via `@page { size: A4|A5 }`. Pas d'emoji dans les affiches — logo SVG et aplats de couleur.
- Documents existants : fiche arrivant (`fiche_arrivant.py`), annonce de hall (`annonce_hall.py`),
  manuel utilisateur (`manuel_pdf.py`).
- 🔴 **Le rendu s'exécute hors du process de l'API** (`app/utils/pdf_rendu.py`, 16/09/2026),
  dans un enfant `spawn` — **jamais `fork`**, qui hériterait des descripteurs de `app.db`
  et ramènerait la règle d'or ci-dessus. Un WeasyPrint qui plante ou épuise la mémoire
  du RPi n'emporte donc plus l'API. Coût assumé : +1,5 à 2 s par document.
  `api/tests/test_weasyprint_appel_unique.py` refuse tout appel au moteur ailleurs que
  dans ce module — c'est ce qui empêche le rendu de retomber dans le process, en silence.
  Il gardait déjà cette porte pour une **autre** raison (la dérogation de sécurité
  GHSA-jf6q-chmf-3h3v) : ne pas en écrire un second, c'est la même porte.
  `api/tests/test_pdf_hors_process.py` vérifie, lui, que l'enfant est bien `spawn`.

### Destinataires CS

`app/utils/destinataires.py` est la source unique, et elle porte **deux règles
distinctes** — les confondre envoie le bon message aux mauvaises personnes :

| Ce qu'on vise | Fonction | Employée par |
|---|---|---|
| le CS **concerné par un périmètre** | `membres_cs_notifiables(session, batiment_ids)` (+ `batiments_du_perimetre()`) | nouvel arrivant, annonces de hall |
| le CS **par le rôle**, sans périmètre | `membres_cs_avec_email(session)` | publications, sondages, calendrier, tickets |
| le **syndic principal** | `syndic_principal(session)` | ci-dessous, fiche copropriété, arrivants |
| **syndic puis CS, dédoublonnés** — qui reçoit un e-mail interne | `destinataires_syndic_cs(session, syndic=…, cs=…)` | les quatre entités qui cochent « envoyer au syndic / au CS » |

🔴 La dernière ligne a existé en **quatre exemplaires identiques** (tickets,
calendrier, publications, sondages) jusqu'au 31/08/2026 — et celui des tickets
affirmait, en toutes lettres, être *« le seul endroit où cette règle s'écrit »*.
Les trois autres n'avaient aucun commentaire : le seul fichier qui parlait du
sujet disait que le problème n'existait pas.

🔒 `api/tests/test_destinataires_source_unique.py` refuse une cinquième copie. Il
laisse passer les notifications **in-app**, qui visent « CS **ou** admin » et
rendent des `Utilisateur` — autre décision, autre destinataire.

### Sécurité
- JWT HS256 en cookies `httponly=True`, `secure=settings.cookie_secure`, `samesite="strict"`
- CORS : allowlist explicite, jamais `["*"]` avec `credentials=True`
- Rate limiting slowapi sur `/auth/*`
- **Journal de sécurité : une seule porte.** Un geste sensible — connexion
  refusée, mot de passe changé ou réinitialisé, rôle ajouté ou retiré,
  bannissement — appelle `utils/journal_securite.journaliser_securite`, et
  **aucun** n'écrit dans un `logger` local. Rien n'était journalisé avant le
  20/09/2026 : un compte compromis ou une élévation de rôle ne laissait aucune
  trace exploitable (#1040).
  🔴 **Jamais de donnée personnelle dans une ligne de journal** — un identifiant,
  jamais une adresse, un mot de passe ou un jeton, même tronqué. Le défaut
  inverse existe dans ce dépôt (#777, adresses journalisées en clair), et
  `test_journal_securite.py` le refuse **chez la fonction et chez ses appelants**.
  ⚠️ `WARNING`, jamais `ERROR` : le point 6 du pré-check compte les
  `ERROR`/`CRITICAL` (motif `MOTIF_ERREURS_API`), et une faute de frappe sur un
  mot de passe bloquerait alors la MEP. Cette ligne nommait aussi
  `check-reliability.sh`, qui ne compte rien de tel (23/09/2026).
- **Téléversement : une seule porte.** Un fichier reçu s'écrit sur disque par
  `utils/fichiers.enregistrer_fichier_recu` **et nulle part ailleurs** ; les
  règles — liste blanche de types, plafond de taille, cohérence de la signature —
  vivent dans `FAMILLES` (image · document · document_prive · tableur). Un
  routeur **nomme une famille**, il ne redéfinit pas ce qu'il accepte.
  🔒 `test_televersement_source_unique.py` refuse une écriture ailleurs (le PDF
  d'affiche, qui est **produit** et non reçu, y est déclaré), une liste MIME ou
  un plafond redéclaré dans un routeur, et une famille qui oublierait l'une des
  trois règles. `test_signature_fichiers.py` vérifie que **chaque** point de
  réception appelle la règle — les trois imports de tableur y ont été ajoutés,
  ils n'avaient aucun contrôle.
  Le nom stocké passe par `nom_stocke` : préfixe UUID, radical assaini, et
  **extension dérivée du type**, jamais du nom fourni — `/uploads/*` est servi
  en statique et Caddy pose le `Content-Type` d'après l'extension sur disque.
- La **racine du volume** se lit dans `Settings.uploads_dir`, seule lecture de
  la variable d'environnement. Elle était écrite six fois : un fichier posé hors
  du volume n'est ni répliqué par `bascule.sh`, ni sauvegardé par `backup.py`.

---

## Checklist avant commit

### Frontend
- [ ] Pattern existant réutilisé (pas de variante ad hoc)
- [ ] Méta toujours visible en mode collapsé
- [ ] Corps déplié d'une carte : `class="carte-corps …"` — c'est ce qui le fait
      entrer (fondu 200 ms) ; sans elle il apparaît sec, sans un mot. Un survol
      qui ne sert qu'à la souris vit sous `@media (hover: hover) and (pointer:
      fine)` — au doigt, `:hover` reste collé (`ux-patterns` §17)
- [ ] `.clamp-3` sur l'aperçu d'une carte (`.clamp-5` seulement hors carte)
- [ ] un assainisseur de `$lib/sanitize` sur tout `{@html}` — jamais un helper
      local, même correct (`npm run lint:html` le refuse)
- [ ] Accessibilité : `role`, `tabindex`, `aria-label`, `on:keydown`
- [ ] Droits : jamais recomposés dans un écran — `$isCS` (il **inclut** admin),
      `$isProprioOuCS`, `aRole(u, …)`, `peutEditer`/`peutCommenter`. Ils l'étaient
      **22 fois** avant #1041 (`npm run lint:droits` le refuse)
- [ ] Onglet réservé à un rôle : `reserve:` **sur l'onglet** dans `pages.ts`, jamais
      un masquage écrit dans la page — `BarreOnglets` masque ET refuse la route
      directe (`npm run lint:onglets-reserves`)
- [ ] Nom affiché d'un objet « Saisi pour » : `nomProprietaire` (`$lib/saisi-pour`),
      **jamais** `objet.auteur_nom` — c'est le rédacteur, et le « Saisi pour » s'y
      substitue (12/09). La case de copie, elle, dit `nomCopie` : deux questions.
      Il y en avait **13** avant #1104 (`npm run lint:nom-proprietaire` le refuse)
- [ ] Section d'un formulaire : elle est déclarée dans `$lib/entites/<entité>`
      — **treize**, dans l'ordre de `SECTIONS_ORDRE` — et son **pliage** suit la
      règle *obligatoire → déplié · facultatif → plié*, ou porte son
      `exceptionPliage` (`npm run lint:etats` refuse dans les deux sens). Un
      composant qui **porte** une section au lieu de l'écrire dans la page la
      **transmet** : sans prop `pliable`, la table a beau dire `pliee`, la
      section s'ouvre — il y en avait **trois** (`npm run lint:pliage-transmis`)
- [ ] Libellé qui NOMME un objet — bouton, titre de boîte, toast, confirmation :
      le mot vient de `$lib/entites/<entité>` (`libelle`, `libelleNouveau`,
      `libelleModifier`), **jamais** réécrit dans un écran. « Publication » et
      « Ticket » sont des noms de modèle ; l'écran dit « Actualité » et
      « Affaire ». Il y en avait **20** avant #1107 (`npm run lint:vocabulaire-ecran`)
- [ ] Périmètre : masqué s'il est celui par défaut (`estPerimetreParDefaut`)
- [ ] Archiver (pas supprimer) sur la vue principale
- [ ] Champs requis : `<EtoileRequis vide={!champ} />` — jamais une astérisque
      tapée. Elle est **collée** au libellé et **rouge tant que le champ est
      vide** : c'est son état, pas une décoration (#1121, 22/09/2026). Les
      libellés de champ sont en MAJUSCULES par le style (`champs.css`), comme
      les intitulés de section — jamais tapées (`npm run lint:champs`)
- [ ] Libellés et nommage en français
- [ ] En-tête de page : `<EntetePage>`, jamais `<div class="page-header">`
      (`ux-patterns` §13)
- [ ] Icône vérifiée dans `$lib/icones-svg.json` — un nom inconnu échoue en silence
      (`npm run lint:icones` le refuse ; un relais d'icône s'appelle `icone`)
- [ ] Tout champ libellé dans un `.field` — jamais une nomenclature locale
      (`npm run lint:champs` ; il y en avait **six** avant #413) — **y compris**
      le champ dont l'intitulé de section est le libellé, et une étoile dans un
      `label.field` enveloppant se tient dans un `<span>` avec son texte (#1230)

### Backend (nouveau endpoint)
- [ ] Modèle dans le module de **son domaine** (`app/models/<domaine>.py`), importé
      par `models/__init__.py` — jamais dans `core.py`
- [ ] Schémas dans `schemas_<domaine>.py` s'ils sont partagés, à côté du routeur sinon
- [ ] Migration `NNNN_slug.py`, numéro suivant le dernier de `alembic/versions/`
- [ ] Routeur inclus dans `main.py` ou dans le `__init__.py` de son paquet —
      `test_routeurs_montes.py` refuse un routeur que personne ne monte : ses URL
      rendraient 404, et rien d'autre ne le dirait
- [ ] ⚠️ Dans un paquet, les routes à segment **fixe** s'incluent AVANT celles à
      paramètre (`/admin/imports/{id}` avant `/admin/{type}/{id}`) : FastAPI retient
      la première qui correspond. Deux écrans d'import sont morts ainsi (#1151) ;
      `test_routes_masquees.py` le tient pour `acces`
- [ ] Lecture d'un objet par `ou_404`, pas `session.get` + 404
- [ ] Client TypeScript ajouté dans le paquet `front/src/lib/api/` — dans le module de son domaine (`acces`, `patrimoine`, `communaute`…), jamais dans un `api.ts` ressuscité à la racine

### Documentation utilisateur — **deux** documents de même rang
- [ ] `docs/manuel-utilisateur.html` — **comment on s'en sert** : mis à jour dans le
      même commit dès qu'un écran, un libellé, un geste ou un parcours change
- [ ] Synchronisé : `Copy-Item docs/manuel-utilisateur.html front/static/manuel-utilisateur.html`
- [ ] `README.md` — **ce que le produit est** : mis à jour dès qu'un module, un écran
      de premier niveau ou une capacité est **ajouté, retiré ou renommé**, que la pile
      change, ou qu'un document du tableau `docs/` bouge
- [ ] Un lot qui ne touche qu'un seul des deux, c'est possible — mais on **dit** lequel
      et pourquoi, on ne l'omet pas en silence

> ⚠️ Le manuel ne se modifie **jamais** avec `sed -i` : il est versionné en CRLF, que
> `sed` réécrit en LF (les dégâts mesurés : `standards/10-encodage-et-fichiers.md` §2). L'écrire en OCTETS, et
> vérifier `git diff --stat`.
>
> Le README était vérifié par personne alors que le point **0e** du pré-check le nomme
> depuis toujours au même rang que le manuel : cette checklist-ci ne citait que le
> manuel, et c'est la liste la plus courte qui a été suivie (11/08/2026, signalé par
> l'utilisateur). Détail et déclencheurs : `.claude/skills/user-manual`.

### Tests préventifs (CI : `api/tests/`, lancés à chaque PR)

> 📖 `standards/05-tests-et-garde-fous.md` — pourquoi un défaut corrigé sans garde-fou
> revient (trois récidives en deux mois ici), les quatre familles de garde-fous qui
> marchent, et l'analyse statique quand le couplage entre deux fichiers est implicite.

Garde-fous contre les classes d'erreurs récurrentes de l'historique GitHub :
- **`test_email_templates.py`** — verrouille les variables Jinja2 de chaque template
  (`EXPECTED_VARS`). Complète le **point 9** (réactif) côté template.
  ⚠️ Si tu modifies les variables d'un template (`seed.EMAIL_TEMPLATES`), **mets à jour
  `EXPECTED_VARS`** ET vérifie que le `send_email(code=...)` correspondant fournit ces
  variables — sinon échec silencieux à l'envoi (cf. bug `'destinataire' is undefined`).
- **`test_migrations.py`** — chaîne Alembic : head unique, base unique, révisions uniques
  (attrape un `down_revision` erroné qui bloquerait `alembic upgrade head` au démarrage).
- Lancer en local (deps requises) : `cd api && pytest tests/ -q`.

### Scripts d'infra — job CI `test-scripts` (depuis le 30/07/2026)
Les scripts qui décident d'arrêter la prod (`bascule.sh`, `health-watch.sh`,
`boot-role-guard.sh`, `check-reliability.sh`…) n'étaient couverts par **aucun**
test : ni Python ni Svelte, donc hors de portée des trois autres jobs. Le job
`test-scripts` vérifie à chaque PR la syntaxe (`bash -n`) de tous les `.sh`
versionnés, les modes git (0b), et exécute les **self-tests**.

**Règle pour toute nouvelle logique de décision d'infra** : l'isoler en fonction
**pure** (aucun SSH, docker, écriture ni `sudo`), exposer `--selftest`, et
l'ajouter au job. C'est le seul moyen de tester une décision de bascule sans les
deux RPi — pattern inauguré par `boot-role-guard.sh --selftest` (15/07/2026),
étendu à `health-watch.sh` et `check-reliability.sh` (30/07/2026).
Lancer en local : `bash <script>.sh --selftest`.

### Navigateur — job CI `e2e-frontend` (depuis le 08/09/2026)
`front/e2e/` porte les tests Playwright — squelette, lien d'évitement, absence de
défilement horizontal, cibles tactiles — sur les profils **bureau ET mobile**.

🔴 **Ils existaient depuis le 06/09 et ne tournaient dans aucun job** : le dépôt
contenait les tests, `npm run e2e` les passait sur le poste de qui y pensait, et
les checks requis restaient verts si l'un d'eux cassait. C'est la même famille que
#409, #410 et #411 — des contrôles qui existent et ne s'exécutent pas. Écrire un
test et le **brancher** sont deux gestes, et le second ne manque à personne.

⚠️ Ces tests s'arrêtent aux écrans **publics** : tout le reste est derrière une
connexion. Ce qui doit être vérifié sur un écran authentifié se mesure autrement —
voir `e2e/cible-tactile.spec.ts`, qui pose son propre témoin dans la page plutôt
que de sauter faute d'en trouver un.

Lancer en local : `cd front && npm run e2e`.

### Rejouer la CI en local — `bash scripts/poste/rejouer-ci.sh` (depuis le 13/08/2026)
Les **cinq** jobs ci-dessus se rejouent en une à deux minutes sur le poste, sans rien
recopier : le script **extrait** les commandes de `.github/workflows/ci.yml`. Une
liste tenue à la main divergerait au premier job ajouté — et c'est justement le job
ajouté, ou celui qu'on ne pense pas à lancer, qui échoue (#319 : Ruff, le 12/08).
Sa trace (`.git/rejeu-ci.ok`) est lue par le **point 16** du pré-check.
Un seul job : `bash scripts/poste/rejouer-ci.sh build-frontend` — mais alors aucune trace n'est
écrite, et le point 16 reste INCONNU.

---

## Infrastructure — l'essentiel

Production **HA sur 2 Raspberry Pi** : rpi1 `192.168.1.222` (PhT-RB5), rpi2
`192.168.1.223` (PhT-RB5i2). Les conteneurs ne tournent que sur le **RPi actif**
(`cat /opt/5hostachy/.active`) ; des conteneurs sur les deux = **split-brain**, à
traiter avant toute autre chose. Site HS : SSH sur l'actif →
`cd /opt/5hostachy && . scripts/lib/lib-env-role.sh && env_role_appliquer .env actif && docker compose up -d`.

⚠️ **Le `env_role_appliquer` n'est pas décoratif** : deux réglages du `.env`
dépendent du rôle — `ORIGIN` (nom public pour l'actif, IP locale pour le standby)
et `COOKIE_SECURE` (**absent** chez l'actif, donc `true` par défaut ; `false` chez
le standby). Démarrer la stack sur un nœud dont le `.env` est resté en rôle
standby sert le public avec une origine locale et un cookie de session sans
drapeau `Secure`. C'est le « gap .env du 15/07/2026 ». La règle vit dans
`scripts/lib/lib-env-role.sh` et nulle part ailleurs (#1077).

> 📇 **Les points d'entrée sont versionnés depuis le 15/08/2026** :
> `infra/points-entree/` porte les crons et l'unité systemd attendus, et le
> **point 17** du pré-check compare l'installé au dépôt. C18 ne compare que les
> nœuds entre eux, donc pas la dérive commune.

| Cron root (identique sur les 2 nœuds) | Rôle |
|---|---|
| `0 2 * * *` `bascule.sh` | bascule active/standby |
| `0 3 * * 0` `maintenance.sh` | purges **demandées à l'API** (`POST /admin/maintenance/purges` — jamais `docker exec … python`, #1232), VACUUM API arrêtée, rotation des logs |
| `*/5 * * * *` `health-watch.sh` | failover automatique si le site est HS |
| `*/15 * * * *` `check-reliability.sh` | contrôles de fiabilité **C1 à C29** (C8 retiré le 17/07/2026 : il causait les pertes qu'il devait prévenir) + alerte e-mail sur `FAIL`, digest quotidien sur `WARN`. ⚠️ La moitié vit dans les modules de `scripts/lib/`, et greper « C25 » dans le script ne le trouve pas. **Où vit chacun** : `grep -rn "── C[0-9]" scripts/` — cette ligne en tenait la liste, et elle plaçait C27 dans le mauvais module (23/09/2026) |

**Les tâches de l'API**, elles, tournent **dans le process** et se déclarent dans
`app/utils/taches.TACHES_PERMANENTES` — avec, pour chacune, **ce qu'on perd** si
elle cesse de tourner. Le démarrage compare les tâches réellement enregistrées à
cette table et journalise tout écart en `WARNING` ; `test_taches_planifiees_declarees.py`
le vérifie aussi en CI, dans les deux sens. Aucun des deux ne suffit seul : le test
lit le code, le contrôle au démarrage lit le scheduler (#1047).

⚠️ « Identique sur les 2 nœuds » **est un invariant, pas un constat** : il était faux
jusqu'au 06/08/2026, rpi2 portant en plus un `check-stack.sh` en échec permanent (récit et
chiffres : `mep-precheck/HISTORIQUE.md`, à « check-stack »). Le vérifier fait partie du point 8 du pré-check. `auto-deploy.sh` (`*/5`) est
à part : c'est le seul cron **utilisateur** (`ptressard`), et c'est ce qui fait
l'objet du point 11.

**Réflexe avant de suspecter un nœud** : depuis l'autre RPi, `curl
http://<actif>/api/health`. S'il répond 200, la panne est sur le **chemin** public
(box, DNS, Cloudflare) et non sur le nœud — ne pas basculer, ne pas redémarrer la
stack.

Toute intervention infra — bascule, base, WhatsApp, incident, coupure de courant,
panne réseau — commence par charger `.claude/skills/infra-rpi` : protections DB,
conduite à tenir en cas de corruption, panne de chemin ≠ panne de nœud, monitoring
APScheduler, bridge WhatsApp, sync DB manuelle et risques connus.

> 📖 `standards/04-fiabilite-des-controles.md` §10 — le réflexe ci-dessus généralisé :
> **deux sondes indépendantes avant toute décision destructive**, pour distinguer la
> panne d'un composant de celle d'une dépendance partagée · `standards/07-observabilite-et-alertes.md`
> §6–8 (rotation par motif, maintenance sur **tous** les nœuds, hygiène surveillée).

---

## Git & MEP — l'essentiel

**Premier réflexe de toute session, avant le moindre commit.** `origin/dev` et
`origin/main` avancent côté GitHub (PR fusionnées, merges `main → dev`) et ne
redescendent **jamais** seules : sans fetch explicite, le clone local dérive
d'exactement le nombre de PR fusionnées depuis le dernier pull manuel.

```bash
git fetch origin && git merge --ff-only origin/dev
```

Garde-fou mécanique : `.githooks/pre-commit` refuse un commit dont la branche est en
retard sur son upstream. Il est versionné mais doit être armé **une fois par clone** :
`git config core.hooksPath .githooks && git config pull.ff only`. Contournement
d'urgence : `ALLOW_STALE=1 git commit …`.

> 📖 `standards/08-git-et-versioning.md` §2–3 — un hook versionné **n'est pas** un
> hook actif (il a déjà été committé en `100644`, donc inerte), et Windows avale
> `chmod +x` en silence. Voir aussi la skill globale `avant-commit` : les six
> contrôles de deux minutes, dont `git diff --stat` et l'encodage.
>
> ⚠️ `standards/13-outillage-claude-code.md` §10 — avant de réécrire un fichier
> partagé, regarder `git worktree list` puis `git -C <autre> status` : rien ne
> signale le travail **non committé** d'une session voisine (vécu le 02/08/2026).

- `main` = production **réellement protégée depuis le 09/08/2026** : les 5 jobs de
  CI sont des *checks requis*, `enforce_admins` est actif, le push direct et le
  `--force` sont refusés. Toute modification passe par une PR depuis `dev`.
  ⚠️ Cette ligne affirmait « production protégé » alors que GitHub répondait
  « Branch not protected » : rien n'empêchait de fusionner une CI rouge — ce qui
  est arrivé trois fois le 08/08. Une consigne fausse est pire qu'absente.
- Préfixes de commit : `feat:` `fix:` `docs:` `refactor:` `test:` `chore:` `perf:`
- 🔴 **Claude crée ET fusionne la PR `dev → main`, et conduit la MEP** (28/08/2026).
  Cette ligne disait le contraire jusque-là — « Claude s'arrête au push sur `dev` » —
  et c'était l'exemple même de la consigne fausse que le point ci-dessus dénonce.
  La contrepartie demandée n'est pas une validation *avant*, c'est un **compte rendu
  après** : à chaque MEP, **la version et les fonctionnalités apportées**.
  Le pré-check ne s'allège pas pour autant : c'est lui qui remplace la relecture.
  `gh pr create` → attendre les **5 checks requis** → `gh pr merge --squash
  --delete-branch` → **réaligner `dev` sur `origin/main`** (la fusion est un squash
  et supprime la branche distante).
  ⚠️ `gh pr merge --delete-branch` supprime aussi la branche **locale** et bascule
  sur `main` : committer sans regarder `git branch --show-current` met le lot suivant
  sur `main`, où le push est refusé.
- MEP : elle n'est **pas** la fusion. `auto-deploy.sh` (cron `*/5`) fait le `git pull`
  **puis** le build : entre les deux, les points 12 et 18 du pré-check échouent
  légitimement — le code est à jour, l'image ne l'est pas. Attendre la ligne
  `Déployé: <sha>` dans `/var/log/hostachy-deploy.log` **sur l'actif**, puis
  post-check. Ne jamais conclure sur le seul `git log` du nœud.
  Reprise en main : `scripts/exploitation/MaJ-Hostachy.sh` sur le **RPi actif**
  uniquement (le script bloque sur le standby)
- **Session cloud** (claude.ai/code) : aucun SSH vers les RPi, donc le lot s'arrête
  à une PR vers `dev` — pré-check, fusion vers `main` et MEP se font du poste.
  Environnement, setup et ce qui y manque : `.claude/cloud/LISEZMOI.md`.
- `.env` non versionné · `SECRET_KEY` ≥ 32 caractères · `ENABLE_API_DOCS=false` en prod
- Bascule manuelle (test) : `sudo bash /opt/5hostachy/scripts/exploitation/bascule.sh` depuis le RPi actif
  (chemin de **relais** ; le script vit dans `scripts/exploitation/` — cf. #337)

**Aucune MEP sans avoir chargé `.claude/skills/mep-precheck`.** Cette skill porte les
étapes 0 et 0 bis (poste de développement, exigences sans exception), le **pré-check**
(`scripts/poste/precheck-mep.sh`), le **post-check P1–P11**, le rollback, la rétrospective du 26/07/2026 et
l'état de la surveillance continue. Elle porte surtout les trois règles qui priment
sur la liste des contrôles :

1. **Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.**
2. **Ce qui est critique en continu ne doit pas être vérifié seulement en MEP.**
3. **Vérifier le fait, pas le symptôme attendu** — et le comportement, jamais l'artefact.

> 📖 Ces trois règles sont nées ici le 26/07/2026 ; le socle en porte **d'autres**,
> toutes issues d'incidents : `standards/04-fiabilite-des-controles.md`. Elles valent
> aussi pour ce projet — notamment le **cas zéro** (§2), le **battement manquant** (§4), le
> **contrôle sans destinataire** (§7) et **observer la chose, pas son enregistrement**
> (§14), qui ont tous produit un faux vert ici.
> Principes de livraison, pré-check générique et post-check :
> `standards/09-livraison-et-mep.md`.

---

## Versioning (`front/package.json`)

> 📖 `standards/08-git-et-versioning.md` §6 — la règle patch/minor/major, le commit
> dédié, et le bump **d'office** dès qu'une MEP est demandée, sans rappel.

Instanciation 5Hostachy :
- Le fichier est **`front/package.json`** ; la version s'affiche dans le **pied de
  page** du site — c'est ce que contrôle **P3** du post-check.
- Bump **avant** le push final sur `dev`, commit dédié `chore(version): bump vX.Y.Z`.
- ⚠️ Un onglet PWA resté ouvert peut servir une version en cache : le bandeau de mise
  à jour (v2.24.0) existe pour ça, et `api/tests/test_pwa_maj.py` le verrouille.
