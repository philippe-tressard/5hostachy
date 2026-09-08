"""Les jetons d'authentification — rafraîchissement, mot de passe oublié, e-mail.

## Pourquoi ce module (#833, 08/09/2026)

Extraits de `models/core.py` quand le garde-fou de modularité a refusé de le
laisser grossir (1 066 lignes). Le refus désignait juste : ces trois modèles
n'ont **aucun `Relationship`** et ne référencent aucun autre modèle. C'est ce qui
les rendait déplaçables sans risque — et c'est aussi ce qui montrait qu'ils
n'avaient rien à faire au milieu du patrimoine et des tickets.

Ils accompagnent `routers/auth_mot_de_passe.py` et `routers/auth_telemetrie.py`,
sortis du même fichier pour la même raison.

⚠️ `core.py` les réimporte : `from app.models.core import RefreshToken` reste
valide, et c'est cet import qui enregistre les tables dans les métadonnées
SQLModel. Le retirer ferait disparaître trois tables d'une base neuve — sans
erreur, jusqu'à la première écriture.
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_token"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    revoked: bool = False


class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_token"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    used: bool = False


class EmailVerificationToken(SQLModel, table=True):
    __tablename__ = "email_verification_token"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    used: bool = False
