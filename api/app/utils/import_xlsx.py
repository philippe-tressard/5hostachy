"""Lecture d'un classeur Excel d'import — la mécanique, écrite une fois.

Les trois imports (lots, télécommandes, vigiks) partageaient **trois fonctions
identiques au mot près** : `normaliser`, `importer_depuis_bytes` et
`importer_depuis_fichier`. Seuls le nom dans la docstring et le traitement de
lignes appelé changeaient. Cinquante-sept lignes recopiées trois fois, dont la
gestion d'`openpyxl` absent, l'ouverture en lecture seule, la fermeture du
classeur et la transaction.

C'est la duplication décrite par `standards/02-factorisation.md` §2 : la mécanique
d'un import n'a aucune raison de dépendre de ce qu'on importe. Ce qui diffère
vraiment — comment interpréter les lignes — reste dans chaque module, sous la
forme d'un `traiter(rows, session, remplacer)` passé en paramètre.

Ce qui n'est **pas** ici, volontairement : la lecture des colonnes, la résolution
des bâtiments, la détection des doublons. Ce sont trois règles métier distinctes
qui se ressemblent peu ; les fondre créerait le couplage que le §4 du même
standard met en garde.
"""
import io
import unicodedata
from pathlib import Path
from typing import Callable, Optional

from sqlmodel import Session

from app.database import engine

#: Signature du traitement propre à chaque import : (lignes, session, remplacer) → stats.
Traitement = Callable[[list, Session, bool], dict]

_ERREUR_OPENPYXL = "openpyxl n'est pas installé. Ajouter au requirements.txt."


def normaliser(s: Optional[str]) -> str:
    """Normalise une chaîne : majuscules, sans accents, espaces normalisés.

    Sert à comparer des noms saisis à la main dans trois fichiers différents —
    « Dupont-Martin », « DUPONT MARTIN » et « Dupont  Martin » doivent
    s'apparier. Écrite trois fois à l'identique jusqu'au 08/08/2026.
    """
    if not s:
        return ""
    s = s.strip().upper()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(s.split())


def _lignes(source) -> list:
    """Toutes les lignes de la première feuille, classeur refermé derrière.

    `read_only` + `data_only` : on lit des valeurs, jamais des formules, et sans
    charger le classeur entier en mémoire — un import de lots fait plusieurs
    milliers de lignes.
    """
    try:
        import openpyxl  # type: ignore
    except ImportError:
        raise RuntimeError(_ERREUR_OPENPYXL)

    classeur = openpyxl.load_workbook(source, read_only=True, data_only=True)
    try:
        return list(classeur.active.iter_rows(values_only=True))
    finally:
        #  Fermeture dans un `finally` : en `read_only`, openpyxl garde un
        #  descripteur ouvert sur l'archive. Les trois copies d'origine
        #  fermaient après la lecture, donc jamais si celle-ci levait.
        classeur.close()


def importer_bytes(
    contenu: bytes,
    session: Session,
    remplacer: bool,
    traiter: Traitement,
) -> dict:
    """Import depuis des octets en mémoire — chemin du téléversement HTTP.

    La session est celle de la requête : c'est l'appelant qui décide de sa
    portée, on se contente de valider la transaction.
    """
    stats = traiter(_lignes(io.BytesIO(contenu)), session, remplacer)
    session.commit()
    return stats


def importer_fichier(chemin: str, remplacer: bool, traiter: Traitement) -> dict:
    """Import depuis un fichier sur disque — chemin du script en ligne de commande.

    Ouvre sa **propre** session : appelé hors requête, il n'y en a aucune à
    reprendre.
    """
    path = Path(chemin)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {chemin}")

    rows = _lignes(str(path))
    with Session(engine) as session:
        stats = traiter(rows, session, remplacer)
        session.commit()
    return stats
