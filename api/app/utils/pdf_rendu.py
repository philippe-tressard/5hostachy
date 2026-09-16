"""Le rendu WeasyPrint, **hors du process de l'API**.

## Ce que ce module fait, et ce qu'il ne fait PAS

Il isole le rendu des documents imprimables dans un process jetable. Il achète
deux choses, mesurées sur le RPi le 16/09/2026 avec un vrai uvicorn mono-worker
servant le manuel complet (14 pages, ~20 s de rendu) pendant qu'un client
sondait `/health` :

| | `/health` au repos | `/health` pendant le rendu | durée du rendu |
|---|---|---|---|
| rendu **dans** le process | 0,6 ms | médiane 1,5 ms, **max 122 ms** | 20,4 s |
| rendu **hors** process | 0,6 ms | médiane 1,2 ms, **max 3,3 ms** | 22,5 s |

1. **une pointe de latence divisée par 37** sur les requêtes concurrentes ;
2. surtout, **l'isolation des pannes** : un WeasyPrint qui plante, boucle ou
   épuise la mémoire du RPi ne peut plus emporter l'API avec lui. C'est la
   raison principale de ce module.

🔴 **Ce qu'il ne corrige PAS, et il faut le dire ici parce que l'inverse a été
écrit et cru pendant une demi-journée** : il n'empêche aucun « figeage » du
site, parce qu'il n'y en avait pas. Le 16/09/2026 au matin, un
`GET /manuel/pdf` a mis 21 s et les logs de l'API ne montraient aucune autre
requête servie pendant ce temps — on en a conclu que le site était bloqué. La
mesure ci-dessus a infirmé cette lecture : hors démonstration ce site voit une
dizaine de requêtes par minute, et l'absence de requêtes ne dit rien de la
capacité à en servir. C'était un raisonnement sur un silence
(`standards/04-fiabilite-des-controles.md` §2, le cas zéro).

⚠️ **Le coût est réel : +1,5 à 2 s par document.** Il se paie sur chaque PDF, y
compris la fiche arrivant et l'annonce de hall qui se rendaient en moins d'une
seconde. C'est le prix de l'isolation, accepté en connaissance de cause.

## 🔴 SPAWN, JAMAIS FORK — et c'est la règle d'or anti-corruption

Le défaut de Python 3.12 sous Linux est `fork` (vérifié sur l'image :
`mp.get_start_method()` → `fork`). Un enfant **forké** hérite des descripteurs
de fichier ouverts du parent, **y compris ceux de `app.db`** tenus par le pool
SQLAlchemy. Quand il se termine, SQLite peut s'y croire dernière connexion et
supprimer `app.db-wal` sous l'API vivante : l'incident du 17/07/2026, ~12 h
d'écritures perdues, mais déclenché depuis l'intérieur.

`spawn` démarre un interpréteur neuf qui ne partage **aucun** descripteur. Le
prix est un import à payer (`import weasyprint` : 0,59 s mesuré sur le RPi).

C'est vérifié par le **comportement**, pas par la forme du code :
`test_pdf_hors_process.py` importe `app.database` dans le parent puis exige que
l'enfant ne l'ait pas — ce qu'un `fork` ne pourrait pas satisfaire.

⚠️ Corollaire de `spawn` : le module principal de l'appelant est réimporté dans
l'enfant. Il doit donc porter un garde `if __name__ == "__main__"`, sans quoi il
se rejoue en entier. Le point d'entrée de production l'a (`/usr/local/bin/uvicorn`,
vérifié), et pytest aussi ; un script maison, non — c'est ce qui est arrivé à la
première vérification de ce module, d'où la mention dans le message d'erreur.

## Pourquoi un process jetable et non un worker résident

Un worker persistant économiserait 0,59 s par document. Il coûterait en échange
une mémoire résidente permanente sur un RPi, un recyclage à écrire (WeasyPrint
fuit), une fermeture à câbler au `lifespan`, et un plantage qui empoisonne
l'appel suivant. Les PDF de ce site se comptent par jour, pas par seconde.

## Le journal de l'enfant remonte au parent — ce n'est pas un détail

Les lignes `weasyprint` et `fontTools` sont émises **dans l'enfant**, où rien
n'est configuré : elles seraient perdues. Or elles servent deux fois :

1. **en production** — ce sont elles qui ont permis de dater le rendu de 21 s à
   la seconde près ;
2. **en test** — `test_documents_pdf.py::test_la_fiche_avec_ses_icones…` lit
   `caplog` pour vérifier que WeasyPrint ne se plaint pas du document. Un
   `caplog` devenu vide l'aurait rendu **toujours vert** : le contrôle serait
   mort sans que rien ne le dise (`standards/04` §14).

L'enfant les collecte donc et les renvoie ; le parent les **rejoue** dans les
loggers de même nom, où ses propres niveaux et handlers s'appliquent comme
avant. Seule différence observable : elles arrivent groupées à la fin du rendu
plutôt qu'au fil de l'eau.
"""
from __future__ import annotations

import logging
import multiprocessing
import os
import sys

logger = logging.getLogger("hostachy.pdf")

#: Au-delà, le rendu est considéré perdu et le process abattu. Large à dessein :
#: le manuel complet demande ~21 s sur un RPi, et un document plus lourd doit
#: pouvoir sortir. Ce délai ne protège pas le site (l'isolation s'en charge) —
#: il protège seulement d'une requête HTTP qui ne se terminerait jamais.
DELAI_RENDU_S = 180.0

#: Borne du journal remonté. Un rendu normal en produit quelques centaines (une
#: ligne `fontTools` par table de police) ; la borne existe pour qu'un document
#: pathologique ne fasse pas transiter des mégaoctets de texte.
MAX_JOURNAL = 5_000


class RenduPdfImpossible(RuntimeError):
    """Le PDF n'a pas pu être produit — on ne rend jamais un document partiel."""


def _rendre_dans_l_enfant(tube, html: str) -> None:
    """Rend le PDF et le renvoie par le tube. **Exécuté dans le process enfant.**

    Rien ici ne doit toucher la base : ce module n'importe volontairement que la
    bibliothèque standard et WeasyPrint, et `test_pdf_hors_process.py` vérifie
    qu'il en reste ainsi.
    """
    journal: list[tuple[str, int, str]] = []

    class _Collecteur(logging.Handler):
        def emit(self, enregistrement: logging.LogRecord) -> None:
            if len(journal) < MAX_JOURNAL:
                journal.append((
                    enregistrement.name,
                    enregistrement.levelno,
                    enregistrement.getMessage(),
                ))

    racine = logging.getLogger()
    racine.setLevel(logging.INFO)
    racine.addHandler(_Collecteur())

    #  Cette ligne est le témoin de l'isolation : elle nomme le process qui a
    #  vraiment rendu, et dit si la base a été chargée ici. `base chargée` doit
    #  rester False — un True signifierait un retour au `fork` et une exposition
    #  de `app.db` (cf. l'en-tête). C'est ce que le test lit.
    logger.info(
        "Rendu PDF dans le process %d (base chargée : %s)",
        os.getpid(),
        "app.database" in sys.modules,
    )

    try:
        from weasyprint import HTML

        pdf = HTML(string=html).write_pdf()
    except BaseException as exc:  # noqa: BLE001 — tout est remonté au parent
        tube.send(("erreur", f"{type(exc).__name__}: {exc}", journal))
    else:
        tube.send(("ok", pdf, journal))
    finally:
        tube.close()


def _rejouer(journal: list[tuple[str, int, str]]) -> None:
    """Réémet dans ce process les lignes produites par l'enfant."""
    for nom, niveau, message in journal:
        logging.getLogger(nom).log(niveau, message)


def rendre_pdf(html: str, *, delai_s: float = DELAI_RENDU_S) -> bytes:
    """Rend un document HTML autonome en PDF, dans un process séparé.

    Le HTML doit être **autonome** : CSS dans un `<style>`, images en data-URI.
    Aucune requête réseau n'est effectuée au rendu.

    Lève `RenduPdfImpossible` si le rendu échoue, dépasse `delai_s`, ou si le
    process meurt en route (OOM — le risque est réel sur un RPi).
    """
    contexte = multiprocessing.get_context("spawn")
    lecture, ecriture = contexte.Pipe(duplex=False)
    enfant = contexte.Process(
        target=_rendre_dans_l_enfant,
        args=(ecriture, html),
        name="rendu-pdf",
        daemon=True,
    )
    enfant.start()
    #  ⚠️ Fermer NOTRE copie de l'extrémité d'écriture, sinon le tube n'atteint
    #  jamais EOF quand l'enfant meurt : `poll()` attendrait le délai complet au
    #  lieu de signaler la mort immédiatement.
    ecriture.close()

    try:
        if not lecture.poll(delai_s):
            raise RenduPdfImpossible(
                f"rendu abandonné après {delai_s:.0f} s — document trop lourd "
                "ou moteur bloqué"
            )
        try:
            message = lecture.recv()
        except EOFError as exc:
            #  ⚠️ Deux causes très différentes, et les nommer toutes les deux
            #  évite l'heure perdue au mauvais endroit : la première est
            #  plausible en production sur un RPi, la seconde apparaît dès qu'on
            #  appelle ce module depuis un script sans garde `if __name__ ==
            #  "__main__"` — `spawn` réimporte le module principal, qui se
            #  rejoue alors en entier dans l'enfant. Vu dès la première
            #  vérification du correctif (16/09/2026).
            raise RenduPdfImpossible(
                f"le process de rendu est mort sans rien produire (code de "
                f"sortie {enfant.exitcode}) — mémoire insuffisante, ou module "
                f"principal sans garde `if __name__ == \"__main__\"` "
                f"(voir la trace du process enfant ci-dessus)"
            ) from exc
    finally:
        lecture.close()
        enfant.join(5)
        if enfant.is_alive():
            enfant.terminate()
            enfant.join(5)
        if enfant.is_alive():
            enfant.kill()
            enfant.join()

    etat, charge, journal = message
    _rejouer(journal)
    if etat == "erreur":
        raise RenduPdfImpossible(charge)
    return charge
