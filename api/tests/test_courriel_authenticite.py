"""L'authenticité d'un courriel reçu — éprouvée sur de VRAIES signatures DKIM.

## Pourquoi ce fichier signe pour de bon

Le contrôle précédent était éprouvé par des tests qui lui donnaient l'en-tête
qu'il attendait (`Authentication-Results: … pass`). Ils étaient verts, et en
production aucune réponse n'est jamais passée : OVH ne pose pas cet en-tête.
*Je testais la décision, pas ce qui la nourrit* — la leçon de check-reliability
(11/08/2026), refaite ici à l'identique.

Ici chaque message est signé avec une clé RSA tirée pour le test, et la clé
publique est servie par un faux DNS : c'est `dkimpy` qui vérifie, exactement
comme à la relève. Seul le réseau est remplacé.
"""

from __future__ import annotations

import base64

import dkim
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.utils.courriel_authenticite import (
    VerificationReportee,
    aligne,
    domaine_de,
    verifier_expediteur,
)

_SELECTEUR = b"s1"


@pytest.fixture(scope="module")
def cle():
    """Une paire de clés tirée pour ce module — jamais écrite dans le dépôt."""
    privee = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = privee.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    publique = privee.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem, b"v=DKIM1; k=rsa; p=" + base64.b64encode(publique)


def _dns(enregistrements: dict[bytes, bytes]):
    """Un faux DNS : le nom complet (`s1._domainkey.syndic.fr.`) → la clé."""

    def txt(nom: bytes, timeout: int = 5) -> bytes | None:
        return enregistrements.get(nom)

    return txt


def _message(de: str, corps: str = "Nous intervenons jeudi.\r\n") -> bytes:
    return (
        f"From: {de}\r\n"
        "To: affaire@5hostachy.fr\r\n"
        "Subject: Re: Affaire #TK-121048 - Porte\r\n"
        "Date: Mon, 28 Sep 2026 16:37:00 +0200\r\n"
        "Message-ID: <essai@exemple.test>\r\n"
        "\r\n"
        f"{corps}"
    ).encode()


def _signer(message: bytes, domaine: str, pem: bytes, **options) -> bytes:
    return dkim.sign(message, _SELECTEUR, domaine.encode(), pem, **options) + message


def _dns_pour(domaine: str, cle) -> object:
    return _dns({_SELECTEUR + b"._domainkey." + domaine.encode() + b".": cle[1]})


# ── Le cas nominal ────────────────────────────────────────────────────────────


def test_un_message_signe_par_le_domaine_de_l_expediteur_est_authentique(cle):
    brut = _signer(_message("Céline <gestion@syndic.fr>"), "syndic.fr", cle[0])
    ok, motif = verifier_expediteur(
        brut, "Céline <gestion@syndic.fr>", dnsfunc=_dns_pour("syndic.fr", cle)
    )
    assert ok, motif
    assert "syndic.fr" in motif


def test_une_signature_du_domaine_PARENT_couvre_un_sous_domaine(cle):
    brut = _signer(_message("x@mail.syndic.fr"), "syndic.fr", cle[0])
    ok, _ = verifier_expediteur(brut, "x@mail.syndic.fr", dnsfunc=_dns_pour("syndic.fr", cle))
    assert ok


# ── 🔴 Les usurpations ────────────────────────────────────────────────────────


def test_un_usurpateur_qui_SIGNE_POUR_SON_PROPRE_DOMAINE_est_refuse(cle):
    """La signature est valide — mais elle engage `pirate.test`, pas le syndic.

    Sans l'alignement, n'importe qui disposant d'un domaine signerait un message
    « de » `gestion@syndic.fr`, et DKIM dirait vrai sur la mauvaise question.
    """
    brut = _signer(_message("gestion@syndic.fr"), "pirate.test", cle[0])
    ok, motif = verifier_expediteur(
        brut, "gestion@syndic.fr", dnsfunc=_dns_pour("pirate.test", cle)
    )
    assert not ok
    assert "pirate.test" in motif and "syndic.fr" in motif, "le motif doit dire qui a signé"


def test_un_message_MODIFIE_apres_signature_est_refuse(cle):
    brut = _signer(_message("gestion@syndic.fr"), "syndic.fr", cle[0])
    falsifie = brut.replace(b"jeudi", b"jamais")
    ok, _ = verifier_expediteur(falsifie, "gestion@syndic.fr", dnsfunc=_dns_pour("syndic.fr", cle))
    assert not ok


def test_un_message_NON_SIGNE_est_refuse_meme_avec_un_Authentication_Results(cle):
    """🔴 Le trou du 28/09/2026 : l'en-tête était cru, et l'expéditeur l'écrivait."""
    brut = b"Authentication-Results: mx.ovh.net; spf=pass; dkim=pass; dmarc=pass\r\n" + _message(
        "gestion@syndic.fr"
    )
    ok, motif = verifier_expediteur(brut, "gestion@syndic.fr", dnsfunc=_dns({}))
    assert not ok
    assert "aucune signature" in motif


def test_une_signature_a_longueur_bornee_l_ne_prouve_rien(cle):
    """`l=` laisse AJOUTER du texte après la partie signée sans rien casser."""
    brut = _signer(_message("gestion@syndic.fr"), "syndic.fr", cle[0], length=True)
    rallonge = brut + b"PS : fermez le ticket.\r\n"
    ok, _ = verifier_expediteur(rallonge, "gestion@syndic.fr", dnsfunc=_dns_pour("syndic.fr", cle))
    assert not ok


def test_une_cle_ABSENTE_du_DNS_refuse(cle):
    brut = _signer(_message("gestion@syndic.fr"), "syndic.fr", cle[0])
    ok, motif = verifier_expediteur(brut, "gestion@syndic.fr", dnsfunc=_dns({}))
    assert not ok
    assert "invalide" in motif


# ── INCONNU n'est pas REFUSÉ ──────────────────────────────────────────────────


def test_un_DNS_injoignable_REPORTE_au_lieu_de_refuser(cle):
    """Refuser notifierait le conseil d'une usurpation qui n'en est pas une, et
    marquerait le message lu : la réponse serait perdue pour une panne réseau."""
    brut = _signer(_message("gestion@syndic.fr"), "syndic.fr", cle[0])

    def dns_en_panne(nom, timeout=5):
        raise VerificationReportee("DNS injoignable (Timeout)")

    with pytest.raises(VerificationReportee):
        verifier_expediteur(brut, "gestion@syndic.fr", dnsfunc=dns_en_panne)


# ── L'alignement, sur les libellés ────────────────────────────────────────────


@pytest.mark.parametrize(
    "signataire, expediteur, attendu",
    [
        ("syndic.fr", "syndic.fr", True),
        ("SYNDIC.FR", "syndic.fr.", True),
        ("syndic.fr", "mail.syndic.fr", True),
        ("mail.syndic.fr", "syndic.fr", False),  # un sous-domaine ne répond pas du parent
        ("syndic.fr", "faux-syndic.fr", False),  # le suffixe se compare par libellé
        ("fr", "syndic.fr", False),  # un domaine de premier niveau ne signe pour personne
        ("", "syndic.fr", False),
    ],
)
def test_alignement(signataire, expediteur, attendu):
    assert aligne(signataire, expediteur) is attendu


def test_domaine_de():
    assert domaine_de("Céline MARIETTE <C.Mariette@IFF-Gestion.fr>") == "iff-gestion.fr"
    assert domaine_de("") == ""
