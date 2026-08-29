"""Garde-fou de sécurité : le PÉRIMÈTRE d'un document à catégorie (#617).

Extrait de `test_documents_acces.py` le 29/08/2026 : ce fichier passait 501
lignes, et la coupe suit une frontière réelle plutôt qu'un compte.

## Deux régimes, deux fichiers

`document_visible` le dit lui-même : « un document tire sa protection soit de
l'objet qui le porte, soit de son profil d'accès de catégorie — **jamais des
deux, jamais d'aucun** ».

  • `test_documents_acces.py` couvre le premier — une pièce jointe suit son
    actualité, son ticket, son événement, et refuse quand le porteur a disparu ;
  • **ce fichier-ci** couvre le second — profil d'accès de catégorie, puis
    périmètre. C'est le régime des documents de la bibliothèque, dont les
    comptes-rendus d'AG.

Les deux ne partagent aucun montage : le premier a besoin d'un porteur, le
second d'un profil. Les garder ensemble obligeait chaque lecteur à trier.
"""
from app.models.core import StatutUtilisateur
from app.utils.visibility import document_visible

# ═══════════════════════════════════════════════════════════════════════════════
#  #617 — le ciblage MULTI-bâtiments d'un CR d'AG ne protégeait rien
# ═══════════════════════════════════════════════════════════════════════════════
#
#  POURQUOI (29/08/2026, trouvé en instruisant #470). L'écran des comptes-rendus
#  d'AG écrit DEUX formes de ciblage selon le nombre de bâtiments cochés :
#
#      un bâtiment    → perimetre='bâtiment' + batiment_id=N
#      deux ou plus   → perimetre='résidence' + batiments_ids_json='[1,2]'
#
#  `document_visible` ne lisait que la première. Cocher un bâtiment de plus
#  repassait donc par « résidence », le contrôle de périmètre ne s'appliquait
#  plus, et le seul champ portant encore le ciblage n'était jamais lu. Mesuré :
#
#       refusé   CR d'AG du seul bâtiment 1
#      VISIBLE   CR d'AG des bâtiments 1 ET 2      ← le défaut
#
#  🔴 Rien ne pouvait le signaler : chaque forme était cohérente prise seule, et
#  l'écran affichait « Bâtiment(s) spécifique(s) » dans les deux cas. C'est la
#  signature du ciblage à deux formes — celle qu'on relit le moins devient fausse.
#
#  Ces tests fixent la règle dans les DEUX sens : ce qui doit passer autant que ce
#  qui doit être refusé. Un test qui ne vérifierait que le refus laisserait
#  fermer un accès légitime sans que rien ne le dise.

class _ProfilOuvertATous:
    """Profil d'accès de catégorie qui n'exclut personne par son RÔLE.

    C'est le point : le profil filtre par rôle, jamais par bâtiment. Le filtrage
    géographique est le travail de la dernière étape de `document_visible` —
    celle que #617 corrige.
    """

    roles_autorises = '["resident", "locataire"]'
    profil_acces_id = 1


class _SessionProfil:
    """`session.get()` rend toujours le profil : seule branche exercée ici."""

    def get(self, _modele, _id):
        return _ProfilOuvertATous()


def _cr_ag(perimetre="résidence", batiment_id=None, batiments_ids_json=None):
    """Un CR d'AG : rattaché à une CATÉGORIE, donc protégé par son profil d'accès.

    ⚠️ Objet minimal, pour la même raison que `_ResidentDuBatiment` : `categorie`
    est une RELATION SQLModel, et lui affecter un objet hors ORM déclenche
    l'événement de backref. On expose exactement les champs que
    `document_visible` consulte — la surface de la règle se lit ainsi d'un coup.
    """
    return type(
        "CrAg",
        (),
        {
            "id": 99,
            "contrat_id": None,
            "publication_id": None,
            "ticket_id": None,
            "evenement_id": None,
            "categorie_id": 1,
            "profil_acces_override_id": None,
            "perimetre": perimetre,
            "batiment_id": batiment_id,
            "lot_id": None,
            "batiments_ids_json": batiments_ids_json,
            "categorie": _ProfilOuvertATous(),
        },
    )()


class _ResidentDuBatiment:
    """Un résident dont le seul lot est dans le bâtiment `numero`.

    ⚠️ Objet minimal et non le modèle `Utilisateur` : `user_lots` est une
    RELATION SQLModel, et lui affecter des objets hors ORM déclenche l'événement
    de backref (`'_UserLot' object has no attribute '_sa_instance_state'`).
    Monter de vraies lignes exigerait une base — pour éprouver une fonction qui
    n'en ouvre aucune.

    Il expose exactement ce que `document_visible` consulte, et rien de plus :
    c'est aussi ce qui rend visible, à la lecture, la surface dont dépend la
    règle. Même parti pris que `_SessionSansBase` plus haut.
    """

    def __init__(self, numero: int):
        lot = type("Lot", (), {"batiment_id": numero, "id": 500 + numero})()
        self.user_lots = [
            type("UserLot", (), {"actif": True, "lot": lot, "lot_id": 500 + numero})()
        ]
        self.statut = StatutUtilisateur.locataire
        self.roles = ["resident"]

    def has_role(self, *_roles):
        #  Ni admin ni conseil syndical : ce sont eux qui court-circuitent tout
        #  en tête de `document_visible`, et ce n'est pas ce qu'on éprouve ici.
        return False


def _resident_du_batiment(numero: int) -> _ResidentDuBatiment:
    return _ResidentDuBatiment(numero)


# ── Ce qui doit être REFUSÉ ──────────────────────────────────────────────────

def test_cr_ag_multi_batiments_refuse_a_un_resident_d_ailleurs():
    """🔴 LE défaut de #617 : deux bâtiments cochés ouvraient à toute la copro."""
    doc = _cr_ag(batiments_ids_json="[1,2]")
    assert document_visible(_resident_du_batiment(3), doc, _SessionProfil()) is False


def test_cr_ag_mono_batiment_refuse_a_un_resident_d_ailleurs():
    """La forme qui marchait déjà — elle doit continuer."""
    doc = _cr_ag(perimetre="bâtiment", batiment_id=1)
    assert document_visible(_resident_du_batiment(3), doc, _SessionProfil()) is False


def test_cr_ag_liste_de_batiments_illisible_refuse():
    """Un JSON cassé n'autorise pas : en cas de doute sur un droit, on refuse.

    Sans ce cas, replier sur « aucune restriction » rouvrirait le document à tout
    le monde à la première donnée abîmée — et le contrôle serait vert.
    """
    doc = _cr_ag(batiments_ids_json="[1,2")  # JSON tronqué
    assert document_visible(_resident_du_batiment(1), doc, _SessionProfil()) is False


def test_cr_ag_liste_de_batiments_qui_n_est_pas_une_liste_refuse():
    doc = _cr_ag(batiments_ids_json='{"bat": 1}')
    assert document_visible(_resident_du_batiment(1), doc, _SessionProfil()) is False


# ── Ce qui doit RESTER lisible ───────────────────────────────────────────────

def test_cr_ag_multi_batiments_lisible_par_un_resident_cible():
    """Le lecteur a un lot dans L'UN des bâtiments visés : il lit."""
    doc = _cr_ag(batiments_ids_json="[1,2]")
    assert document_visible(_resident_du_batiment(2), doc, _SessionProfil()) is True


def test_cr_ag_de_toute_la_copropriete_reste_lisible():
    """Le cas le plus courant — aucun ciblage, aucune restriction géographique."""
    assert document_visible(_resident_du_batiment(3), _cr_ag(), _SessionProfil()) is True


def test_cr_ag_liste_vide_ne_cible_personne_donc_ne_restreint_rien():
    """Cas zéro : une liste VIDE n'est pas un ciblage, c'est l'absence de ciblage.

    La confondre avec « personne n'a le droit » rendrait invisibles des documents
    dont la liste a été vidée — un refus silencieux, le pire des deux.
    """
    doc = _cr_ag(batiments_ids_json="[]")
    assert document_visible(_resident_du_batiment(3), doc, _SessionProfil()) is True


def test_cr_ag_mono_batiment_lisible_par_son_batiment():
    doc = _cr_ag(perimetre="bâtiment", batiment_id=1)
    assert document_visible(_resident_du_batiment(1), doc, _SessionProfil()) is True
