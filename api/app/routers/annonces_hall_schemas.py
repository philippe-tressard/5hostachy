"""Les schémas de l'affiche de hall — ce qui entre, ce qui sort.

Extrait de `routers/annonces_hall.py` le 02/09/2026, quand le plafond de
modularité a refusé le branchement de la règle d'archivage (#515). Troisième
découpage du même fichier, après `annonces_hall_courriels` et
`annonces_hall_apercu` — la couture est la même à chaque fois : ce qui DÉCLARE
part, ce qui DÉCIDE reste.

⚠️ `AnnonceHallRead` n'existe pas : la lecture est construite à la main par
`_to_read`, qui compose le PDF, les destinataires et l'état d'archivage. La
déclarer ici en ferait une seconde description de la même sortie.
"""
from pydantic import BaseModel


class AnnonceHallBase(BaseModel):
    titre: str
    message: str
    perimetre_cible: list[str] = ["résidence"]
    format_demande: str = "auto"
    images: list[str] = []


class AnnonceHallCreate(AnnonceHallBase):
    #  🔴 La DIFFUSION est un ACTE, et elle se coche (section 9 du cadre #430).
    #
    #  L'envoi au CS était AUTOMATIQUE jusqu'au 18/08, puis supprimé le même jour
    #  parce qu'il partait au moindre essai de mise en page. Il revient ici sous sa
    #  forme juste : un choix, décoché par défaut.
    #
    #  ⚠️ Décoché par défaut, et c'est le point : la valeur par défaut d'un envoi
    #  est « ne pas envoyer ». Un défaut à `True` reproduirait l'automatisme qu'on
    #  vient de retirer, en donnant l'illusion du choix.
    envoyer_cs: bool = False
    #  Les deux autres canaux de la Diffusion (#480). Mêmes règles : décochés par
    #  défaut, et CONSOMMÉS — un champ ouvert dans l'interface que le serveur
    #  ignorerait est ce que le cadre interdit.
    envoyer_syndic: bool = False
    partager_whatsapp: bool = False
    #  La 4e case : « Envoyer une copie à … ». Le destinataire est l'auteur de
    #  l'AFFICHE — voir `app/utils/copie_auteur.py`.
    envoyer_auteur: bool = False


class AnnonceHallArchive(BaseModel):
    #: État EFFECTIF : archivée à la main, **ou** par la règle du site — 30 jours
    #: après l'envoi (`utils/archivage`, #515). C'est lui que les deux listes
    #: emploient, et c'est ce qu'un lecteur voit.
    archivee: bool
    #: La DÉCISION HUMAINE, seule. Elle sert à savoir si « Restaurer » a un effet :
    #: retirer un archivage manuel ramène l'affiche ; sur une affiche archivée par
    #: le temps, le même geste ne ferait rien, et l'écran ne le propose donc pas.
    archivee_manuellement: bool
