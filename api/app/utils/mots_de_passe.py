"""La règle de robustesse d'un mot de passe — écrite une fois.

Extraite de `routers/auth.py` le 14/08/2026 avec le bloc « mot de passe » : trois
routes l'appellent, et deux d'entre elles vivent désormais dans un autre fichier.
La laisser dans `auth.py` aurait obligé le second module à importer un nom privé
d'un router, ou — bien pire — à recopier les quatre critères.

Un critère recopié diverge : c'est exactement ce qui produirait un mot de passe
accepté à l'inscription et refusé au changement, sans que rien ne le signale.
"""
import re

from fastapi import HTTPException


def verifier_robustesse(password: str) -> None:
    """Vérifie la complexité du mot de passe. Lève HTTPException 400 si les critères ne sont pas satisfaits."""
    errors = []
    if len(password) < 8:
        errors.append("au moins 8 caractères")
    if not re.search(r"[A-Z]", password):
        errors.append("une lettre majuscule")
    if not re.search(r"\d", password):
        errors.append("un chiffre")
    if not re.search(r"[@$!%*?&#._\-+]", password):
        errors.append("un caractère spécial (@$!%*?&#._-+)")
    if errors:
        raise HTTPException(400, "Le mot de passe doit contenir : " + ", ".join(errors) + ".")
