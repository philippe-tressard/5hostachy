import secrets
from datetime import datetime, timedelta
from typing import Optional

import jwt
from jwt.exceptions import PyJWTError
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# rounds=10 : conforme OWASP (minimum recommandé), ~4× plus rapide que 12
# sur Raspberry Pi (auto-hébergé, <100 utilisateurs)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=10)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def verify_and_rehash(plain: str, hashed: str) -> tuple[bool, str | None]:
    """Vérifie le mot de passe et retourne (valide, nouveau_hash_si_upgrade_nécessaire).
    Permet de migrer silencieusement les hashes 12-rounds vers 10-rounds au login.
    """
    return pwd_context.verify_and_update(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(data: dict) -> str:
    """Un jeton de rafraîchissement — **unique par construction**.

    ## Pourquoi le `jti` (19/08/2026, trouvé par le point 6 du pré-check)

    Le contenu était entièrement déterministe : `{"sub": …, "exp": …, "type": …}`.
    `exp` a une résolution d'UNE SECONDE. Deux rafraîchissements du même
    utilisateur dans la même seconde produisaient donc deux jetons **identiques
    octet pour octet**, et la colonne `refresh_token.token` étant UNIQUE :

        sqlite3.IntegrityError: UNIQUE constraint failed: refresh_token.token
        POST /auth/refresh → 500

    Ce n'était pas un cas de bord. Quand une page charge, plusieurs appels
    reçoivent 401 **en même temps** et déclenchent chacun un rafraîchissement :
    sur les dernières 24 h de production, **4 collisions pour 4 appels** — c'est
    la totalité d'entre eux.

    `jti` est le champ prévu pour cela par la RFC 7519 (« JWT ID ») : un
    identifiant unique par jeton. `token_urlsafe(16)` donne 128 bits d'entropie,
    tirés de `secrets` — le générateur cryptographique, jamais `random`.

    ⚠️ Le jeton d'accès n'en a pas besoin : il n'est stocké nulle part, donc
    aucune contrainte d'unicité ne le concerne. En ajouter un rallongerait chaque
    en-tête de requête sans rien protéger.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh", "jti": secrets.token_urlsafe(16)})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except PyJWTError:
        return None
