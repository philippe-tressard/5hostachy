"""Le DIALECTE de la base : tout ce qui ne vaut que pour un moteur, et nulle part ailleurs (#1747).

Chantier multi-copropriétés, D4 : la plateforme passera sous PostgreSQL, la
résidence reste sous SQLite tant que DI-7 n'est pas fait. Ce qui ne s'écrit pas
pareil dans les deux — `PRAGMA`, URL de fichier, `sqlite_master`, journal WAL,
format SQL d'une date — vit ICI, derrière un nom qui dit la QUESTION posée
(« vider le journal », « la base est-elle saine ? », « le mois de cette date »),
jamais la commande d'un moteur.

🔒 `tests/test_adherence_sqlite.py` refuse ces formes partout ailleurs dans
`app/`, sur l'AST — un commentaire qui parle de SQLite n'est pas une adhérence.

## Ce que chaque moteur fait d'une question

| Question | SQLite | PostgreSQL |
|---|---|---|
| clés étrangères | `PRAGMA foreign_keys=ON` à chaque connexion | toujours vérifiées : rien à poser |
| réglages de durabilité | WAL, `synchronous=FULL`, `busy_timeout` | ceux du serveur |
| vider le journal | `wal_checkpoint` | rien à vider (`None`) |
| la base est-elle saine ? | `quick_check` | **non mesuré** — le verdict le dit, jamais « ok » |
| compacter | `VACUUM` puis `optimize` | `VACUUM ANALYZE` |
| le jour, le mois d'une date | `strftime` | `to_char` |

⚠️ « Non mesuré » n'est pas « sain » (`standards/04` §1) : sur PostgreSQL,
`verifier_integrite` rend un verdict qui n'est pas « ok », et les appelants le
signalent. Choisir la mesure (`amcheck`, sondes du serveur) est un geste de DI-7.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import String, event, literal, text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement

#: Le préfixe d'une base-fichier — la seule écriture de l'URL d'un moteur (#1747).
_PREFIXE_FICHIER = "sqlite:///"


def dialecte_de(lien) -> str:
    """Le nom du dialecte d'un moteur, d'une connexion ou d'une session."""
    dialecte = getattr(lien, "dialect", None)
    if dialecte is None:
        dialecte = lien.get_bind().dialect
    return dialecte.name


def est_fichier(lien) -> bool:
    """La base est-elle un fichier local, que l'exploitation copie et compacte ?"""
    return dialecte_de(lien) == "sqlite"


# ── L'adresse d'une base ─────────────────────────────────────────────────────


def url_fichier(chemin: str | Path) -> str:
    """L'URL d'une base-fichier : `/app/data/app.db` → l'adresse que lit SQLAlchemy."""
    return f"{_PREFIXE_FICHIER}{Path(chemin).as_posix()}"


def chemin_fichier(url) -> Path | None:
    """Le fichier d'une base, ou `None` si elle n'en a pas (serveur, mémoire)."""
    adresse = str(url)
    if not adresse.startswith(_PREFIXE_FICHIER) or ":memory:" in adresse:
        return None
    reste = adresse.removeprefix(_PREFIXE_FICHIER)
    return Path(reste) if reste else None


def options_connexion(url) -> dict:
    """Les `connect_args` du moteur de l'application.

    Une base-fichier est partagée entre les fils de l'API et du planificateur ;
    un serveur l'est d'office et refuserait l'option.
    """
    return {"check_same_thread": False} if str(url).startswith("sqlite") else {}


# ── Les réglages d'un moteur ─────────────────────────────────────────────────


def regler_moteur(moteur) -> None:
    """Pose les réglages de durabilité du moteur de l'application (base-fichier seulement).

    WAL : lectures et écritures concurrentes sans blocage mutuel.
    synchronous=FULL : chaque commit est fsync'd intégralement (WAL + en-tête).
      NORMAL était plus rapide mais laisse une fenêtre de torn-write sur coupure/
      arrêt brutal ; sur une copro à faible trafic le surcoût est négligeable et la
      durabilité prime (cf. corruptions récurrentes telemetry_event 05+17/06/2026).
    busy_timeout=5000 : attend jusqu'à 5 s si la base est verrouillée au lieu
      d'échouer immédiatement.
    """
    if not est_fichier(moteur):
        return
    with moteur.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=FULL"))
        conn.execute(text("PRAGMA busy_timeout=5000"))
        conn.commit()


def moteur_jetable(chemin: Path):
    """Un moteur sur une base NEUVE, au fichier `chemin`, dans le dialecte de l'application.

    Ce qui ouvre une base de travail — la vérification d'une restauration
    (`utils/export_copropriete`, #1749) — la demande ici, sans écrire d'URL. Les
    clés étrangères y sont vérifiées comme sur la base de l'application.
    """
    from sqlmodel import create_engine

    moteur = create_engine(url_fichier(chemin))
    activer_cles_etrangeres(moteur)
    return moteur


# ── Les gestes d'exploitation ────────────────────────────────────────────────


def point_de_controle(conn, mode: str = "TRUNCATE"):
    """Vide le journal dans la base ; rend `(occupé, pages, reportées)`, ou `None`.

    `None` : le moteur n'a pas de journal à vider par l'application.
    """
    if not est_fichier(conn):
        return None
    if mode not in ("PASSIVE", "FULL", "RESTART", "TRUNCATE"):
        raise ValueError(f"mode de point de contrôle inconnu : {mode}")
    return conn.execute(text(f"PRAGMA wal_checkpoint({mode})")).first()  # noqa: S608 — mode en liste blanche


def verifier_integrite(conn) -> str:
    """Le verdict d'intégrité du moteur : « ok » si sain, sinon ce qu'il signale.

    ⚠️ Sur un moteur que ce module ne sait pas mesurer, le verdict le DIT — un
    contrôle qui ne peut pas s'exécuter n'est jamais vert (`standards/04` §1).
    """
    if not est_fichier(conn):
        return f"non mesurée sur {dialecte_de(conn)}"
    ligne = conn.execute(text("PRAGMA quick_check")).first()
    return ligne[0] if ligne else "(aucun résultat)"


def compacter(conn) -> None:
    """Rend l'espace des lignes supprimées et rafraîchit les statistiques.

    `conn` doit être en AUTOCOMMIT : aucun des deux moteurs ne compacte dans une
    transaction.
    """
    if est_fichier(conn):
        conn.execute(text("VACUUM"))
        conn.execute(text("PRAGMA optimize"))
    else:
        conn.execute(text("VACUUM ANALYZE"))


# ── Les clés étrangères ──────────────────────────────────────────────────────


def cles_etrangeres_actives(conn) -> bool:
    """Le moteur refusera-t-il une écriture qui casse une clé ?"""
    if not est_fichier(conn):
        return True
    return bool(conn.execute(text("PRAGMA foreign_keys")).scalar())


def lignes_orphelines(conn) -> list[tuple]:
    """Les lignes dont le parent a disparu : `(table, rowid, table parente, n° de clé)`.

    Toujours vide sur un moteur qui vérifie ses clés depuis toujours.
    """
    if not est_fichier(conn):
        return []
    return [tuple(ligne) for ligne in conn.execute(text("PRAGMA foreign_key_check"))]


def cles_de_table(conn, table: str) -> dict[int, list[str]]:
    """Les colonnes de chaque clé étrangère de `table`, par numéro de clé.

    Le numéro est celui que rend `lignes_orphelines` : il n'a de sens que pour
    lui. `table` vient des métadonnées du moteur, jamais d'une entrée.
    """
    cles: dict[int, list[str]] = {}
    for f in conn.execute(text(f'PRAGMA foreign_key_list("{table}")')):  # noqa: S608 — nom lu dans le moteur
        cles.setdefault(f[0], []).append(f[3])
    return cles


@contextmanager
def cles_suspendues(conn):
    """Suspend la vérification des clés le temps d'une réparation, puis rétablit l'ÉTAT D'ORIGINE.

    Le réglage vaut pour la CONNEXION : le laisser modifié contaminerait tout ce
    qui la réutilise (piège qui a désarmé la suite de tests le 30/08/2026).
    """
    if not est_fichier(conn):
        yield
        return
    avant = conn.execute(text("PRAGMA foreign_keys")).scalar()
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    try:
        yield
    finally:
        conn.execute(text(f"PRAGMA foreign_keys={'ON' if avant else 'OFF'}"))  # noqa: S608 — ON ou OFF
        conn.commit()


# ── Le jour et le mois d'une date, en SQL ────────────────────────────────────


class _DateEnTexte(FunctionElement):
    """Une date rendue en texte par le moteur ; `MOTIFS` donne le format de chacun."""

    type = String()
    inherit_cache = True
    MOTIFS: dict[str, str] = {}


class _Jour(_DateEnTexte):
    name = "jour"
    inherit_cache = True
    MOTIFS = {"sqlite": "%Y-%m-%d", "postgresql": "YYYY-MM-DD"}


class _Mois(_DateEnTexte):
    name = "mois"
    inherit_cache = True
    MOTIFS = {"sqlite": "%Y-%m", "postgresql": "YYYY-MM"}


@compiles(_DateEnTexte, "sqlite")
def _date_sqlite(element, compiler, **kw):
    colonne, *decalage = element.clauses.clauses
    args = [f"'{element.MOTIFS['sqlite']}'", compiler.process(colonne, **kw)]
    args += [compiler.process(d, **kw) for d in decalage]
    return f"strftime({', '.join(args)})"


@compiles(_DateEnTexte, "postgresql")
def _date_postgresql(element, compiler, **kw):
    colonne, *decalage = element.clauses.clauses
    expression = compiler.process(colonne, **kw)
    if decalage:
        expression = f"({expression} + CAST({compiler.process(decalage[0], **kw)} AS INTERVAL))"
    return f"to_char({expression}, '{element.MOTIFS['postgresql']}')"


def jour(colonne, decalage: str | None = None):
    """Le jour d'un horodatage, « AAAA-MM-JJ » ; `decalage` : « +2 hours »."""
    return _Jour(colonne, *([literal(decalage)] if decalage else []))


def mois(colonne, decalage: str | None = None):
    """Le mois d'un horodatage, « AAAA-MM » ; `decalage` : « +2 hours »."""
    return _Mois(colonne, *([literal(decalage)] if decalage else []))


# ── Les clés étrangères de l'application ─────────────────────────────────────


def activer_cles_etrangeres(moteur) -> None:
    """Fait poser `PRAGMA foreign_keys=ON` sur CHAQUE connexion de `moteur`.

    ✅ **Appelé sur le moteur de l'application depuis le 30/08/2026** — fin de
    #546. Ce paragraphe a dit le contraire pendant deux jours, et c'était juste :
    la fonction existait, éprouvée, et n'était pas branchée. Il est corrigé le
    jour où il cesse de l'être, parce qu'un commentaire qui survit à ce qu'il
    décrit est pire qu'absent.

    ## Ce que l'absence de ce PRAGMA coûtait

    SQLite ne vérifie **aucune** clé étrangère par défaut, et le réglage n'est
    **pas** persisté dans le fichier — contrairement à `journal_mode=WAL`. Il vaut
    pour la connexion, pas pour la base. Aucune des FK déclarées dans les modèles
    n'est donc vérifiée : une ligne peut référencer un parent supprimé, et rien ne
    l'empêche ni ne le signale. L'intégrité repose entièrement sur le code
    applicatif — ce qui est tenable, et n'est pas une bonne surprise à découvrir
    le jour d'un incident.

    ## Pourquoi l'écouteur doit être posé ICI et pas plus bas

    Le bloc d'amorçage ci-dessous ouvre une connexion et la **rend au pool**, où
    elle est réutilisée : l'événement `connect` n'est alors plus jamais émis. Un
    écouteur enregistré six lignes trop bas laisse le relevé dire `foreign_keys =
    0` alors qu'il est « en place ». Vérifié.

    ## Pourquoi l'activation a attendu le 30/08/2026

    Activer le PRAGMA ne valide **pas** l'existant : SQLite ne relit pas la base,
    une ligne orpheline reste lisible, et seules les écritures futures sont
    refusées. Le risque n'était donc pas au démarrage — la crainte inverse avait
    immobilisé ce ticket depuis le 20/08, et elle était fausse.

    Trois conditions ont dû être remplies, dans cet ordre :

      1. **les fixtures** ne construisent plus de lignes orphelines (4 lots, 103
         erreurs ramenées à zéro — régime par défaut de la suite depuis le 29/08) ;
      2. **les suppressions** ont été exercées : 11 endpoints DELETE testés, six
         défauts corrigés. Deux ne se voyaient qu'en traçant le SQL émis ;
      3. **la base** a été purgée : 50 lignes orphelines relevées, supprimées
         depuis l'écran d'administration, relevé rendu à zéro par deux sondes.

    ⚠️ **L'ordre n'était pas négociable.** Sans la 3, l'activation n'aurait rien
    cassé au démarrage, mais toute écriture touchant l'une de ces lignes aurait
    échoué ensuite — avec un message ne disant pas qu'elle datait de mois.
    """

    #  PostgreSQL vérifie ses clés étrangères toujours (#1747) : rien à poser.
    if not est_fichier(moteur):
        return

    @event.listens_for(moteur, "connect")
    def _poser(dbapi_connection, _record):  # pragma: no cover — appelé par SQLAlchemy
        curseur = dbapi_connection.cursor()
        curseur.execute("PRAGMA foreign_keys=ON")
        curseur.close()
