"""Garde-fou : les fichiers privés ne doivent jamais être servis en statique.

`/uploads/*` est publié par Caddy **sans authentification**. Jusqu'au 03/08/2026,
`documents.py` et `diagnostics.py` écrivaient à la racine de ce volume : 48
fichiers — PV d'assemblée générale, plan pluriannuel de travaux, modification du
règlement de copropriété, rapports de diagnostic — étaient accessibles à qui
connaissait l'URL. Leur endpoint de téléchargement applique pourtant un contrôle
d'accès à trois couches (`document_visible`) : l'URL statique le contournait
entièrement.

Deux conditions doivent tenir ensemble, et aucune ne se suffit :

1. le code écrit ces fichiers dans `REPERTOIRE_PRIVE`, pas à la racine ;
2. le `Caddyfile` refuse `/uploads/prive/*`, **avant** le service statique —
   Caddy applique le premier `handle` qui correspond, une directive placée après
   ne servirait à rien.

Le second point est un piège classique : la protection tient à l'**ordre** de
deux blocs, ce qu'aucune relecture rapide ne vérifie.
"""
import os
import pathlib
import re

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]
CADDYFILE = RACINE / "Caddyfile"

#: Routeurs qui écrivent des fichiers à accès restreint. `prestataires.py` en est
#: volontairement absent : le front consomme ses devis par une URL publique
#: stockée en base, les déplacer casserait l'affichage tant qu'un endpoint de
#: téléchargement authentifié n'existe pas. Lot distinct, exposition connue.
ROUTEURS_PRIVES = ("documents.py", "diagnostics.py")


def _caddyfile() -> str:
    contenu = CADDYFILE.read_text(encoding="utf-8")
    # Cible introuvable ⇒ INCONNU, jamais OK.
    assert len(contenu) > 200, "Caddyfile vide ou illisible : contrôle impossible"
    return contenu


def test_le_repertoire_prive_est_refuse_par_caddy():
    contenu = _caddyfile()
    assert re.search(r"handle\s+/uploads/prive/\*\s*\{[^}]*respond\s+404", contenu), (
        "Le Caddyfile ne refuse plus /uploads/prive/* : les PV d'AG et les "
        "rapports de diagnostic redeviennent téléchargeables sans authentification."
    )


def test_le_refus_precede_le_service_statique():
    """L'ordre EST la protection : Caddy applique le premier `handle` qui matche."""
    contenu = _caddyfile()
    prive = contenu.find("handle /uploads/prive/*")
    statique = re.search(r"handle\s+/uploads/\*\s*\{", contenu)

    assert prive != -1, "bloc /uploads/prive/* introuvable"
    assert statique, "bloc /uploads/* introuvable — le Caddyfile a changé de forme"
    assert prive < statique.start(), (
        "Le refus de /uploads/prive/* est placé APRÈS le service statique : "
        "Caddy sert les fichiers avant de l'atteindre, la protection est inerte."
    )


def test_les_annonces_de_hall_restent_protegees():
    """Même mécanisme, antérieur : une régression d'ordre les toucherait aussi."""
    contenu = _caddyfile()
    hall = contenu.find("handle /uploads/annonces-hall/*")
    statique = re.search(r"handle\s+/uploads/\*\s*\{", contenu)
    assert hall != -1 and statique and hall < statique.start()


@pytest.mark.parametrize("routeur", ROUTEURS_PRIVES)
def test_les_routeurs_prives_n_ecrivent_plus_a_la_racine(routeur):
    """Un fichier privé posé à la racine serait servi malgré le Caddyfile."""
    source = (RACINE / "api" / "app" / "routers" / routeur).read_text(encoding="utf-8")

    assert "REPERTOIRE_PRIVE" in source, (
        f"{routeur} n'utilise plus REPERTOIRE_PRIVE"
    )
    fautifs = re.findall(r"os\.path\.join\(\s*UPLOADS_DIR\s*,", source)
    assert not fautifs, (
        f"{routeur} écrit encore à la racine du volume servi "
        f"({len(fautifs)} occurrence(s)) : utiliser REPERTOIRE_PRIVE."
    )


def test_le_repertoire_prive_est_bien_sous_le_volume_repliqué():
    """Un volume dédié serait absent de bascule.sh et de backup.py.

    `bascule.sh` réplique `5hostachy_uploads` par son NOM, `backup.py` archive
    `/app/uploads` par son CHEMIN. Sortir les fichiers de cette arborescence les
    priverait des deux — perte à la première bascule.
    """
    from app.utils.fichiers import REPERTOIRE_PRIVE

    racine = os.getenv("UPLOADS_DIR", "/app/uploads")
    assert os.path.normpath(REPERTOIRE_PRIVE).startswith(os.path.normpath(racine)), (
        "REPERTOIRE_PRIVE est hors du volume répliqué et sauvegardé"
    )

    bascule = (RACINE / "bascule.sh").read_text(encoding="utf-8")
    assert "5hostachy_uploads" in bascule, "bascule.sh ne réplique plus ce volume"
    backup = (RACINE / "api" / "app" / "utils" / "backup.py").read_text(encoding="utf-8")
    assert '"/app/uploads"' in backup, "backup.py n'archive plus ce répertoire"


# ── Migration 0124 : déplacement des fichiers existants ──────────────────────

def _module_migration():
    """Charge la migration sans contexte Alembic (on ne teste que sa logique)."""
    import importlib.util

    chemin = RACINE / "api" / "alembic" / "versions" / "0124_documents_prives_hors_tronc_servi.py"
    spec = importlib.util.spec_from_file_location("mig0124", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_la_migration_deplace_puis_devient_inoperante(tmp_path, monkeypatch):
    """Idempotence : le standby rejoue les migrations sur un volume déjà synchronisé."""
    mig = _module_migration()
    monkeypatch.setattr(mig, "RACINE", str(tmp_path))
    monkeypatch.setattr(mig, "PRIVE", str(tmp_path / "prive"))

    source = tmp_path / "abc123_PV_27.01.2026.pdf"
    source.write_bytes(b"%PDF-1.4")

    nouveau = mig._deplacer(str(source))
    assert nouveau == str(tmp_path / "prive" / "abc123_PV_27.01.2026.pdf")
    assert os.path.isfile(nouveau), "le fichier doit avoir été déplacé"
    assert not source.exists(), "l'ancien emplacement doit être libéré"

    # Rejouée sur la ligne déjà migrée : plus rien à faire.
    assert mig._deplacer(nouveau) is None


def test_la_migration_ne_touche_pas_une_ligne_dont_le_fichier_manque(tmp_path, monkeypatch):
    """Un fichier absent laisse sa ligne inchangée — pas de chemin cassé en base."""
    mig = _module_migration()
    monkeypatch.setattr(mig, "RACINE", str(tmp_path))
    monkeypatch.setattr(mig, "PRIVE", str(tmp_path / "prive"))

    assert mig._deplacer(str(tmp_path / "jamais_arrive.pdf")) is None
    assert mig._deplacer("") is None


def test_la_migration_ne_leve_jamais(tmp_path, monkeypatch):
    """`start.sh` a `set -e` : une exception ici bloquerait le conteneur, donc le site."""
    mig = _module_migration()
    monkeypatch.setattr(mig, "RACINE", str(tmp_path))
    monkeypatch.setattr(mig, "PRIVE", str(tmp_path / "prive"))

    source = tmp_path / "def456_rapport.pdf"
    source.write_bytes(b"x")

    def _echec(*_a, **_k):
        raise OSError("disque plein")

    monkeypatch.setattr(mig.shutil, "move", _echec)
    assert mig._deplacer(str(source)) is None, "un échec doit rendre None, pas lever"
    assert source.exists(), "le fichier d'origine reste en place"
