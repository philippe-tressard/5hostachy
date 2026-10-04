"""Un composant système suivi par C30 s'installe par apt, jamais en binaire posé à la main.

Le 04/10/2026 (#1591), rpi2 faisait tourner un `cloudflared` 2026.3.0 vieux de
sept mois : `scripts/installation/install-cloudflared.sh` le téléchargeait dans
`/usr/local/bin`, hors de tout gestionnaire de paquets — donc jamais mis à jour,
et premier dans le `PATH` devant un éventuel paquet. C30 le disait « absent ».
Le nœud a été réaligné à la main ; la procédure de réinstallation, elle, aurait
reposé le même binaire au prochain nœud reconstruit.

La liste des composants vient de `PAQUETS_PARITE` (`scripts/lib/lib-paquets.sh`),
celle que C30 compare entre les nœuds : elle n'est pas recopiée ici.
"""

import re

from tests.conftest import racine_depot

RACINE = racine_depot()
INSTALLEUR = "scripts/installation/install-cloudflared.sh"


def _paquets_parite() -> list[str]:
    texte = (RACINE / "scripts" / "lib" / "lib-paquets.sh").read_text(encoding="utf-8")
    m = re.search(r'^PAQUETS_PARITE="([^"]+)"', texte, re.M)
    assert m, "PAQUETS_PARITE introuvable dans lib-paquets.sh : le contrôle ne lit plus rien"
    return m.group(1).split()


def _scripts() -> list[str]:
    return sorted(
        str(p.relative_to(RACINE)).replace("\\", "/")
        for p in (RACINE / "scripts").rglob("*.sh")
    )


def test_la_liste_des_composants_est_lue():
    #  Cas zéro : une liste vide rendrait le test suivant vert sans rien vérifier.
    assert "cloudflared" in _paquets_parite()


def test_aucun_script_ne_pose_un_composant_suivi_hors_apt():
    fautes = []
    for chemin in _scripts():
        texte = (RACINE / chemin).read_text(encoding="utf-8", errors="replace")
        for paquet in _paquets_parite():
            if re.search(rf"-o\s+\S*/usr/local/bin/{re.escape(paquet)}\b", texte) or re.search(
                rf"releases/\S*/{re.escape(paquet)}-linux", texte
            ):
                fautes.append(f"{chemin} : {paquet}")
    assert not fautes, (
        "Composant suivi par C30 téléchargé en binaire — apt ne le mettra jamais à jour "
        f"(#1591) : {fautes}"
    )


def test_l_installeur_du_tunnel_passe_par_le_depot_apt():
    #  Le témoin : sans lui, retirer le script rendrait le test précédent vert.
    texte = (RACINE / INSTALLEUR).read_text(encoding="utf-8")
    assert "pkg.cloudflare.com/cloudflared" in texte
    assert re.search(r"apt-get install[^\n]*\bcloudflared\b", texte)
