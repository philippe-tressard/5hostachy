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

#: Routeurs qui écrivent des fichiers à accès restreint. `prestataires.py` les a
#: rejoints le 03/08/2026 (migration 0125) : ses devis étaient consommés par une
#: URL publique stockée en base, ce qui imposait d'abord un endpoint de
#: téléchargement authentifié. Plus aucune exception à ce jour.
ROUTEURS_PRIVES = ("documents.py", "diagnostics.py", "prestataires.py")


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


# ── forward_auth : le reste de /uploads exige une session ────────────────────

def test_uploads_exige_une_session_authentifiee():
    """Photos de profil, de ticket et pièces jointes ne sont plus publiques."""
    contenu = _caddyfile()
    bloc = re.search(
        r"handle\s+/uploads/\*\s*\{(.*?)\n    \}", contenu, re.S
    )
    assert bloc, "bloc /uploads/* introuvable"
    assert "forward_auth" in bloc.group(1), (
        "Le service statique de /uploads/* ne passe plus par forward_auth : "
        "toutes les pièces jointes redeviennent publiques."
    )
    assert "/auth/verifier-acces" in bloc.group(1), (
        "forward_auth n'interroge plus l'endpoint de vérification attendu"
    )


def test_les_images_dactualite_restent_publiques_pour_whatsapp():
    """Le bridge reçoit une URL absolue et la récupère en anonyme.

    `app/utils/whatsapp.py::_resolve_image_url` construit `https://<site>/uploads/…`
    et le bridge va chercher l'image lui-même, sans cookie. Protéger ce dossier
    casserait le partage sur le groupe — et son contenu est justement destiné à
    être diffusé.
    """
    contenu = _caddyfile()
    publications = contenu.find("handle /uploads/publications/*")
    protege = re.search(r"handle\s+/uploads/\*\s*\{", contenu)

    assert publications != -1, (
        "Le dossier des images d'actualité n'est plus servi publiquement : "
        "le partage WhatsApp d'une actualité avec photo va échouer."
    )
    assert protege and publications < protege.start(), (
        "Le bloc publications est placé APRÈS le bloc protégé : Caddy applique le "
        "premier `handle` qui correspond, les images passeraient sous forward_auth."
    )


def test_l_endpoint_de_verification_existe_et_reste_authentifie():
    """Un endpoint qui cesserait d'exiger une session rendrait forward_auth inerte."""
    source = (RACINE / "api" / "app" / "routers" / "auth.py").read_text(encoding="utf-8")
    bloc = re.search(
        r'@router\.get\("/verifier-acces".*?\ndef verifier_acces\((.*?)\)', source, re.S
    )
    assert bloc, "l'endpoint /auth/verifier-acces a disparu — forward_auth pointe dans le vide"
    assert "get_current_user" in bloc.group(1), (
        "verifier_acces ne dépend plus de get_current_user : il répondrait 204 "
        "à tout le monde, et forward_auth n'empêcherait plus rien."
    )


def test_les_fichiers_proteges_ne_sont_pas_mis_en_cache_par_le_cdn():
    """Sans cette directive, `forward_auth` ne protège rien.

    Cloudflare met en cache les extensions statiques (.pdf, .jpg…) par défaut.
    Le premier accès AUTORISÉ peuple donc l'edge, qui sert ensuite le fichier à
    tout le monde sans jamais revenir à l'origine.

    Constaté le 03/08/2026, quelques minutes après la mise en production de
    forward_auth : sur une pièce jointe de ticket, l'origine répondait 401 et
    l'edge 200, avec `CF-Cache-Status: HIT` et `Age: 344`. Le contrôle était
    parfaitement fonctionnel — et parfaitement inutile.

    Une purge du cache ne suffit pas : le premier accès autorisé suivant
    repeuple l'edge. Seule la directive à l'origine règle le problème.
    """
    contenu = _caddyfile()
    bloc = re.search(r"handle\s+/uploads/\*\s*\{(.*?)\n    \}", contenu, re.S)
    assert bloc, "bloc /uploads/* introuvable"

    directive = re.search(
        r'header\s+Cache-Control\s+"([^"]+)"', bloc.group(1)
    )
    assert directive, (
        "Le bloc protégé n'impose plus de Cache-Control : Cloudflare remettra "
        "les pièces jointes en cache et les servira sans authentification."
    )
    valeur = directive.group(1).lower()
    assert "private" in valeur or "no-store" in valeur, (
        f"Cache-Control « {directive.group(1)} » n'interdit pas le stockage par "
        "un cache partagé — une réponse qui dépend d'un cookie ne doit être "
        "conservée nulle part."
    )


def test_les_images_publiques_restent_cacheables():
    """Le contraire du test précédent : ne pas dégrader ce qui doit être servi vite.

    Les images d'actualité sont publiques par nécessité (WhatsApp) ; les priver
    de cache ferait repartir chaque vignette jusqu'au Raspberry Pi.
    """
    contenu = _caddyfile()
    bloc = re.search(
        r"handle\s+/uploads/publications/\*\s*\{(.*?)\n    \}", contenu, re.S
    )
    assert bloc, "bloc /uploads/publications/* introuvable"
    assert "no-store" not in bloc.group(1), (
        "Les images d'actualité sont devenues non-cacheables : chaque affichage "
        "repartira jusqu'au RPi."
    )


# ── Fichiers de prestataires : autorisation, pas seulement authentification ──

def test_les_fichiers_de_prestataires_exigent_le_role_cs():
    """`forward_auth` ne vérifie qu'une session — pas le rôle.

    Devis, ordres de service, conditions d'assurance et relevés de compteur ne
    s'affichent que dans un écran réservé au conseil syndical. Tant qu'ils
    étaient servis en statique, tout résident disposant de l'URL pouvait les
    lire : authentifié n'est pas autorisé. Servis par un endpoint, ils héritent
    enfin de `require_cs_or_admin`.
    """
    source = (
        RACINE / "api" / "app" / "routers" / "prestataires.py"
    ).read_text(encoding="utf-8")

    for endpoint in ("/devis/{d_id}/fichier/{nom}", "/releves/{r_id}/photo/{nom}"):
        assert f'@router.get("{endpoint}")' in source, (
            f"L'endpoint {endpoint} a disparu : les URLs stockées en base "
            "pointent dans le vide et les pièces jointes deviennent illisibles."
        )

    bloc = source[source.index("def _servir_fichier_prive"):]
    assert "require_cs_or_admin" in source[source.index("download_fichier_devis") - 400:], (
        "Le téléchargement des pièces de devis n'exige plus le rôle CS/admin."
    )
    assert "noms_autorises" in bloc, "la validation d'appartenance a disparu"


def test_un_endpoint_prestataire_ne_peut_pas_servir_un_pv_dag():
    """`prive/` contient AUSSI les PV d'AG et les diagnostics.

    Un endpoint qui servirait un nom arbitraire depuis ce répertoire
    contournerait le contrôle d'accès à trois couches de la bibliothèque
    documentaire. La validation par appartenance à la ressource est donc une
    condition de sécurité, pas une commodité — et un `basename` ne suffit pas.
    """
    source = (
        RACINE / "api" / "app" / "routers" / "prestataires.py"
    ).read_text(encoding="utf-8")

    assert "if nom not in noms_autorises:" in source, (
        "La vérification d'appartenance a été retirée : l'endpoint peut servir "
        "n'importe quel fichier de prive/, PV d'assemblée générale compris."
    )
    # Les noms proposés viennent des colonnes de la ressource, jamais de l'URL.
    assert "_noms_du_devis" in source and "d.fichiers_urls" in source


def test_les_urls_stockees_pointent_vers_les_endpoints_authentifies():
    """Le front lit ces URLs depuis la base : elles font foi.

    Si le code réécrivait `/uploads/…`, les fichiers seraient à nouveau demandés
    en statique — donc introuvables (ils sont dans `prive/`), et l'affichage
    casserait sans erreur serveur.
    """
    source = (
        RACINE / "api" / "app" / "routers" / "prestataires.py"
    ).read_text(encoding="utf-8")

    fautifs = re.findall(r'f"/uploads/\{[^"]*\}"', source)
    assert not fautifs, (
        f"{len(fautifs)} URL(s) publique(s) encore écrite(s) en base : {fautifs}"
    )
    assert '/api/prestataires/devis/' in source
    assert '/api/prestataires/releves/' in source


def test_les_urls_de_fichiers_portent_le_nom_du_fichier():
    """Une URL qui sert à RETROUVER un fichier doit contenir son nom.

    La 0125 a stocké `/api/prestataires/releves/{id}/photo` — sans nom — alors
    que l'endpoint dérivait le nom de cette même URL. `basename` rendait
    « photo », et la migration avait écrasé la seule copie du vrai nom : toutes
    les photos de relevé sont devenues introuvables en production, une heure
    après la mise en service. Réparé par la 0126, à partir de la base du standby.

    La leçon tient en une phrase : **ne pas écraser la seule copie d'une donnée
    par une valeur qui en dépend**. Le circuit était fermé sur lui-même.
    """
    source = (
        RACINE / "api" / "app" / "routers" / "prestataires.py"
    ).read_text(encoding="utf-8")

    urls = re.findall(r'= f"(/api/prestataires/[^"]+)"', source)
    assert urls, "aucune URL de fichier construite — le module a changé de forme"
    for url in urls:
        assert url.rstrip("/").endswith("}"), (
            f"L'URL « {url} » ne se termine pas par un segment variable : si "
            "c'est le nom du fichier qui manque, l'endpoint ne pourra pas le "
            "retrouver et la donnée d'origine sera perdue."
        )
        assert "basename(dest)" in source, (
            "le nom du fichier n'est plus injecté dans l'URL stockée"
        )
