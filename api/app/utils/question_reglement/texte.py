"""Le texte du règlement : le préparer, le charger, lire la version en vigueur.

## Ce qui entre

Un fichier **Markdown** choisi par un membre du conseil, lu par le navigateur
et envoyé comme TEXTE — jamais écrit sur disque, jamais servi en `/uploads` :
il ne passe donc pas par `utils/fichiers.enregistrer_fichier_recu`, qui garde
ce qui se dépose sur le volume. Il est borné ici (taille, nature) au même titre.

## Une version par contenu

Recharger exactement le texte en vigueur ne crée pas de version : l'empreinte
le reconnaît, et la version existante est rendue. Un texte corrigé, lui, en crée
une — les questions déjà posées gardent la leur (`models/reglement`).
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.models.reglement import TexteReglement

#: Environ 250 000 jetons : au-delà, ce n'est plus un règlement, et l'appel
#: dépasserait la fenêtre de la plupart des modèles.
MAX_CARACTERES_TEXTE = 1_000_000
#: En deçà, ce n'est pas un règlement — un fichier vide ou le mauvais fichier.
MIN_CARACTERES_TEXTE = 1_000
#: Le titre de l'en-tête YAML (`title: "…"`), s'il y en a un.
_TITRE_YAML = re.compile(r"\A---\s*\n(?:.*\n)*?title:\s*[\"']?(.+?)[\"']?\s*\n", re.MULTILINE)


def preparer(contenu: str, nom_fichier: str) -> tuple[str, str, str]:
    """PURE. (contenu normalisé, titre, empreinte) — ou `HTTPException(400|413)`.

    BOM retiré, fins de ligne en LF : deux enregistrements du même fichier sous
    Windows et sous macOS doivent avoir la même empreinte.
    """
    if not nom_fichier.lower().endswith((".md", ".markdown", ".txt")):
        raise HTTPException(400, "Le texte du règlement doit être un fichier Markdown (.md).")
    texte = contenu.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in texte:
        raise HTTPException(400, "Ce fichier n'est pas un texte.")
    if len(texte) > MAX_CARACTERES_TEXTE:
        raise HTTPException(413, "Le texte dépasse un million de caractères.")
    if len(texte.strip()) < MIN_CARACTERES_TEXTE:
        raise HTTPException(400, "Ce texte est trop court pour être un règlement de copropriété.")
    m = _TITRE_YAML.match(texte)
    titre = (m.group(1).strip() if m else "") or nom_fichier.rsplit(".", 1)[0]
    empreinte = hashlib.sha256(texte.encode("utf-8")).hexdigest()
    return texte, titre[:300], empreinte


def charger(
    session: Session, contenu: str, nom_fichier: str, auteur_id: Optional[int]
) -> tuple[TexteReglement, bool]:
    """(version, créée) — la version en vigueur si le contenu est le même.

    ⚠️ On compare à la version EN VIGUEUR seulement : recharger un texte
    ancien, c'est le remettre en vigueur, donc une version de plus.
    """
    texte, titre, empreinte = preparer(contenu, nom_fichier)
    en_vigueur = texte_en_vigueur(session)
    if en_vigueur and en_vigueur.empreinte == empreinte:
        return en_vigueur, False
    version = TexteReglement(
        titre=titre,
        nom_fichier=nom_fichier[:255],
        contenu=texte,
        empreinte=empreinte,
        charge_par_id=auteur_id,
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version, True


def texte_en_vigueur(session: Session) -> Optional[TexteReglement]:
    """La version la plus récente — celle qu'on interroge."""
    return session.exec(
        select(TexteReglement).order_by(
            col(TexteReglement.cree_le).desc(), col(TexteReglement.id).desc()
        )
    ).first()


__all__ = ["MAX_CARACTERES_TEXTE", "charger", "preparer", "texte_en_vigueur"]
