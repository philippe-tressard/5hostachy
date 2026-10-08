"""La politique de confidentialité nomme les services tiers de CETTE instance (#1585).

Le gabarit du seed laisse « À RENSEIGNER » quatre faits qui dépendent du
déploiement : le groupe de messagerie, le fournisseur du modèle de langage et
son pays, le service d'envoi des courriels, celui de réception. La page servie
les affichait encore le 08/10/2026 — quatre mentions incomplètes sur une page
PUBLIQUE, que l'utilisateur a demandé de compléter.

## Chaque fait est LU dans la configuration de l'instance, jamais supposé

Une mention fausse est pire qu'une mention vague (`seed/contenus_legaux.py`, en
tête). La migration ne remplit donc un passage que si la configuration en base
le prouve, au moment où elle s'applique :

| Passage | Rempli si… |
|---|---|
| messagerie instantanée | la diffusion est ACTIVE (`whatsapp_enabled` = « 1 ») |
| modèle de langage | le fournisseur configuré est OpenAI (`llm_fournisseur`, ou son défaut) |
| envoi des courriels | le serveur SMTP est chez OVH (`smtp_server` en `.ovh.net`) |
| réception des courriels | le serveur IMAP est chez OVH (`imap_server` en `.ovh.net`) |

Sinon, le passage garde son « À RENSEIGNER » : c'est à l'administration de le
compléter (Admin › Légal), et le contrôle de la page servie le dira.

Chaque passage porte la phrase qui le précède quand le fragment seul se répète
(« lequel. » termine deux rubriques). Une page réécrite depuis l'administration
n'est pas touchée (`utils/textes_livres.remplacer_passage`). Le downgrade fait
le remplacement inverse, avec les mêmes faits.

Revision ID: 0271
Revises: 0270
"""

import sqlalchemy as sa
from alembic import op

revision = "0271"
down_revision = "0270"
branch_labels = None
depends_on = None

A_RENSEIGNER = "<strong>À RENSEIGNER</strong>"

#: Les passages du gabarit, au caractère près (espaces insécables comprises).
DIFFUSION = f"{A_RENSEIGNER} si cette diffusion est active sur cette instance, et vers quel groupe."
MODELE = f"{A_RENSEIGNER}\xa0: lequel, et depuis quel pays il opère."
ENVOI = f"le contenu du message. {A_RENSEIGNER}\xa0: lequel."
RECEPTION = f"selon ses propres règles. {A_RENSEIGNER}\xa0: lequel."

DIFFUSION_ACTIVE = (
    "Cette diffusion est active\xa0: elle se fait vers le <strong>groupe WhatsApp de la "
    "résidence</strong>, dont l'accès est donné par le conseil syndical. Pour les utilisateurs de"
    " l'Union européenne, le service est fourni par <strong>WhatsApp Ireland Limited</strong> "
    "(Dublin, Irlande)."
)
MODELE_OPENAI = (
    "Le service configuré est <strong>OpenAI</strong>, fourni aux utilisateurs européens par "
    "<strong>OpenAI Ireland Limited</strong> (Dublin, Irlande)\xa0; les données peuvent être "
    "traitées hors de l'Union européenne, notamment aux <strong>États-Unis</strong>."
)
ENVOI_OVH = (
    "le contenu du message. Il s'agit d'<strong>OVH SAS</strong> (Roubaix, France), hébergeur de"
    " la messagerie du domaine de la résidence\xa0; les messages sont traités dans l'Union "
    "européenne."
)
RECEPTION_OVH = (
    "selon ses propres règles. Il s'agit d'<strong>OVH SAS</strong> (Roubaix, France)\xa0: la "
    "boîte est hébergée sur sa messagerie Zimbra, dans l'Union européenne."
)

#: Le fournisseur que l'application emploie quand la clé est absente
#: (`utils/llm_fournisseurs.FOURNISSEUR_DEFAUT`) — écrit ici en dur : une
#: migration décrit l'instant où elle s'applique, pas le code qui suivra.
FOURNISSEUR_DEFAUT = "openai"


def _config(conn) -> dict[str, str]:
    lignes = conn.execute(
        sa.text(
            "SELECT cle, valeur FROM config_site WHERE cle IN "
            "('whatsapp_enabled', 'llm_fournisseur', 'smtp_server', 'imap_server')"
        )
    ).all()
    return {cle: (valeur or "").strip() for cle, valeur in lignes}


def remplacements(cfg: dict[str, str]) -> list[tuple[str, str]]:
    """(passage du gabarit, texte de l'instance) pour chaque fait PROUVÉ par `cfg`. PURE."""
    faits = []
    if cfg.get("whatsapp_enabled") == "1":
        faits.append((DIFFUSION, DIFFUSION_ACTIVE))
    if (cfg.get("llm_fournisseur") or FOURNISSEUR_DEFAUT) == "openai":
        faits.append((MODELE, MODELE_OPENAI))
    if cfg.get("smtp_server", "").lower().endswith(".ovh.net"):
        faits.append((ENVOI, ENVOI_OVH))
    if cfg.get("imap_server", "").lower().endswith(".ovh.net"):
        faits.append((RECEPTION, RECEPTION_OVH))
    return faits


def _jouer(inverse: bool) -> None:
    from app.utils.textes_livres import remplacer_passage

    conn = op.get_bind()
    for avant, apres in remplacements(_config(conn)):
        if inverse:
            avant, apres = apres, avant
        remplacer_passage(
            conn, "config_site", {"cle": "politique_confidentialite"}, "valeur", avant, apres
        )


def upgrade() -> None:
    _jouer(inverse=False)


def downgrade() -> None:
    _jouer(inverse=True)
