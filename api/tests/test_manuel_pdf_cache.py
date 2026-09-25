"""Le manuel PDF s'affiche tout de suite — même après un déploiement (#1071).

## Ce que ce contrôle protège (25/09/2026, arbitré : « visualisation instantanée »)

Trois trous laissaient le premier lecteur attendre les 21 s d'un rendu :

1. **le cache ne survivait pas au redémarrage** — il vivait dans le process ;
2. **deux lecteurs simultanés lançaient deux rendus** complets, chacun dans son
   process, sur un Raspberry Pi ;
3. **le préchauffage abandonnait au premier échec** — or après un déploiement,
   `front` démarre APRÈS l'API, et le manuel n'était pas encore lisible.

⚠️ Aucun test ne rend de PDF : WeasyPrint n'est pas installé sur un poste. Le
moteur est remplacé par un compteur — ce qu'on vérifie, c'est QUAND il est
appelé, pas ce qu'il produit.
"""

from __future__ import annotations

import threading
import time
from datetime import date

import pytest

from app.utils import manuel_pdf as m
from app.utils import manuel_pdf_cache as cache

MANUEL = '<main><h2>Un écran</h2><div class="ecran-card">x</div></main>'
JOUR = date(2026, 9, 25)


@pytest.fixture
def moteur(monkeypatch):
    """Un moteur factice qui compte ses rendus, et une mémoire vide."""
    appels: list[str] = []
    m._CACHE.clear()
    monkeypatch.setattr(m, "html_to_pdf", lambda doc: appels.append(doc) or b"%PDF-x")
    yield appels
    m._CACHE.clear()


def _generer(dossier, *, jour=JOUR, manuel=MANUEL):
    return m.generer_manuel_pdf(
        "5Hostachy", "https://exemple.fr", html_manuel=manuel, edite_le=jour, dossier=dossier
    )


def test_le_PDF_SURVIT_au_redemarrage(moteur, tmp_path):
    """🔴 Le fait mesuré : mémoire vidée (= redémarrage), aucun rendu refait."""
    premier = _generer(tmp_path)
    m._CACHE.clear()
    assert _generer(tmp_path) == premier
    assert len(moteur) == 1, "le disque n'a pas servi : le premier lecteur repaie 21 s"


def test_un_manuel_MODIFIE_n_est_jamais_servi_depuis_le_disque(moteur, tmp_path):
    """Le nom du fichier EST l'empreinte : pas d'invalidation à écrire, donc à oublier."""
    _generer(tmp_path)
    m._CACHE.clear()
    _generer(tmp_path, manuel=MANUEL.replace("Un écran", "Un écran retouché"))
    assert len(moteur) == 2


def test_le_disque_est_BORNE(moteur, tmp_path):
    for i in range(m._CACHE_MAX + 3):
        _generer(tmp_path, jour=date(2026, 9, 1 + i))
    assert len(list(tmp_path.glob("*.pdf"))) == m._CACHE_MAX
    assert not list(tmp_path.glob("*.tmp")), "un fichier provisoire est resté"


def test_UN_SEUL_rendu_pour_deux_lecteurs_simultanes(monkeypatch, tmp_path):
    """🔴 Deux clics sur un cache vide : le second attend le premier, il ne recompose pas."""
    appels: list[str] = []

    def lent(doc):
        appels.append(doc)
        time.sleep(0.3)
        return b"%PDF-x"

    m._CACHE.clear()
    monkeypatch.setattr(m, "html_to_pdf", lent)
    depart = threading.Barrier(2)
    resultats: list[bytes] = []

    def lecteur():
        depart.wait()
        resultats.append(_generer(tmp_path))

    fils = [threading.Thread(target=lecteur) for _ in range(2)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    m._CACHE.clear()
    assert resultats == [b"%PDF-x", b"%PDF-x"]
    assert len(appels) == 1, f"{len(appels)} rendus pour un seul document"


def test_un_disque_INUTILISABLE_ne_coute_pas_le_document(moteur, tmp_path):
    """Un disque plein ou en lecture seule perd le cache de demain, pas le PDF d'aujourd'hui."""
    bloque = tmp_path / "fichier"
    bloque.write_text("pas un dossier")
    assert _generer(bloque / "cache") == b"%PDF-x"


def test_le_dossier_vit_a_cote_de_la_base_et_HORS_des_uploads(monkeypatch):
    """`uploads` est servi en statique : un PDF posé là serait public."""
    from app.config import get_settings

    reglages = get_settings()
    monkeypatch.setattr(reglages, "database_url", "sqlite:////app/data/app.db")
    monkeypatch.setattr(reglages, "uploads_dir", "/app/uploads")
    dossier = cache.dossier_par_defaut()
    # `as_posix` : sur un poste Windows, `str` rend « \app\data\… » (rejeu local).
    assert dossier.as_posix() == "/app/data/cache-manuel-pdf"
    assert not dossier.as_posix().startswith(reglages.uploads_dir)

    monkeypatch.setattr(reglages, "database_url", "sqlite:///:memory:")
    assert cache.dossier_par_defaut() is None


def test_le_prechauffage_ATTEND_le_front(monkeypatch):
    """🔴 Après un déploiement, `front` démarre après l'API : le manuel est
    illisible les premières secondes. Abandonner là, c'était laisser le premier
    lecteur payer le rendu."""
    essais = []

    def front_lent(*_a, **_k):
        essais.append(1)
        if len(essais) < 3:
            raise m.ManuelIndisponible("front pas encore prêt")
        return b"%PDF-x"

    monkeypatch.setattr(m, "generer_manuel_pdf", front_lent)
    assert m.prechauffer("5Hostachy", "https://exemple.fr", pause_s=0) is True
    assert len(essais) == 3


def test_le_prechauffage_finit_par_RENONCER(monkeypatch):
    essais = []

    def jamais(*_a, **_k):
        essais.append(1)
        raise m.ManuelIndisponible("front absent")

    monkeypatch.setattr(m, "generer_manuel_pdf", jamais)
    assert m.prechauffer("5Hostachy", "https://exemple.fr", pause_s=0) is False
    assert len(essais) == m.TENTATIVES_PRECHAUFFAGE


def test_un_MOTEUR_en_panne_ne_se_reessaie_pas(monkeypatch):
    """Un rendu cassé le serait encore quinze secondes plus tard."""
    essais = []

    def casse(*_a, **_k):
        essais.append(1)
        raise RuntimeError("moteur indisponible")

    monkeypatch.setattr(m, "generer_manuel_pdf", casse)
    assert m.prechauffer("5Hostachy", "https://exemple.fr", pause_s=0) is False
    assert len(essais) == 1
