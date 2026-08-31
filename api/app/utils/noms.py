"""Comment le nom d'une personne S'AFFICHE — une seule écriture pour tout le site.

## La règle, arbitrée à l'écran le 31/08/2026

> *« L'affichage devrait être Prénom NOM => Nom en majuscule »*

Signalé sur une carte du fil qui rendait **« Jean-Sébastien CourT »** : la casse
telle qu'elle avait été tapée, avec un « T » final resté majuscule. Le prénom
garde sa casse, le nom passe en capitales — c'est l'usage administratif français,
et surtout c'est ce qui rend la lecture homogène quand la saisie ne l'est pas.

## 🔴 Pourquoi une fonction et pas un `f"…"` de plus

`f"{x.prenom} {x.nom}"` est écrit **31 fois** dans `app/`. Chacune est correcte,
et toutes ensemble forment la seule chose qu'on ne peut pas corriger : une règle
d'affichage qui n'existe nulle part. Uniformiser la casse demandait donc trente
et une modifications, dont on aurait manqué au moins une — c'est exactement la
duplication que `standards/02` §2 décrit, sur la notion la plus banale du site.

⚠️ **Ne pas confondre avec `_nom_presentable`** (`utils/destinataires.py`), qui
fait l'INVERSE : « DUPONT » → « Dupont ». Elle sert à s'ADRESSER à quelqu'un —
« Madame Dupont » dans un courriel — où la capitale crierait. Ici on IDENTIFIE
une personne dans une liste. Deux besoins opposés, deux fonctions, et les
confondre donnerait des courriels qui hurlent ou des annuaires illisibles.

## Ce que la fonction ne fait pas

Elle ne touche **ni à la donnée, ni au prénom**. Le nom reste enregistré tel
qu'il a été saisi : c'est un rendu, pas une normalisation. Une particule
(« de La Tour ») passe donc en capitales à l'affichage, ce qui est l'usage.
"""
from __future__ import annotations

from typing import Optional


def nom_affiche(prenom: Optional[str], nom: Optional[str]) -> str:
    """« Jean-Sébastien », « CourT » → « Jean-Sébastien COURT ».

    Tolère l'absence de l'un ou de l'autre : une personne dont on ne connaît que
    le nom doit s'afficher quand même, et sans espace en trop.
    """
    prenom = (prenom or "").strip()
    nom = (nom or "").strip().upper()
    return " ".join(p for p in (prenom, nom) if p)
