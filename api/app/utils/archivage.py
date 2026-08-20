"""L'archivage automatique — **la règle, écrite une seule fois** (#515 point 2).

## Pourquoi ce module

Sept objets du site ont vocation à quitter d'eux-mêmes les listes actives au
bout d'un délai. Avant ce module, ils étaient traités par **trois codes qui ne
se connaissaient pas** :

  - `publications/commun.py::_is_archived` — actualités, deux seuils ;
  - `annonces.py::est_archivee` — petites annonces, un `ARCHIVAGE_JOURS = 30`
    **codé en dur**, invisible depuis l'écran d'administration ;
  - `calendrier/+page.svelte` — son propre calcul, côté navigateur.

Et quatre objets (ticket, idée, sondage, affiche de hall) n'en avaient aucun.

🔴 **Le défaut n'était pas la duplication, c'était l'inévitabilité de la
divergence.** Le jour où le délai du site change, l'administration en affiche un
et les petites annonces suivent le leur, sans que rien ne le signale. C'est le
motif exact du ticket : *« sept implémentations séparées divergeraient au
premier ajustement »*.

⚠️ **Le piège du 17/07/2026, à ne pas refaire** : la règle doit être tranchée au
**même endroit** pour toutes les vues. Le jour où le fil d'activité et l'écran
des actualités ont décidé séparément, un élément apparaissait dans l'une et pas
dans l'autre.

## Ce que ce module ne fait pas

Il ne **stocke** rien. L'archivage automatique est une **conséquence du temps**,
pas une étape que quelqu'un choisit — en faire un état donnerait deux notions
pour la même chose, celle qu'on pose et celle qui arrive, libres de se
contredire. C'est l'arbitrage déjà pris pour les annonces (`StatutAnnonce`) et
les actualités ; il vaut ici pour les sept.

Il ne supprime rien non plus. La purge des actualités annulées est une notion
distincte, avec son propre délai : voir `PURGE_ANNULE_HEURES`.

## Test : `api/tests/test_archivage.py`

Il ne se contente pas d'éprouver la décision : il **confronte les déclarations
ci-dessous aux modèles réels** — chaque champ déclaré doit exister, chaque
statut déclaré doit être une valeur possible. Sans cela un statut mal
orthographié ne lèverait rien : la règle serait simplement **fausse en silence**
pour cet objet, et vraie pour les six autres. Le risque n'est pas théorique —
les statuts de ticket sont les seuls accentués de tout le site (`résolu`,
`annulé`), et le ticket #515 le signalait comme le piège principal.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

#: Le délai unique, en jours. Arbitré à l'écran le 19/08/2026 : *« un seul
#: champ, mais valable pour tous les types d'écran… 30 j »*. Surchargeable en
#: configuration (`archivage_delai_jours`), et par ce seul réglage.
ARCHIVAGE_DELAI_JOURS = 30

#: ⚠️ **Rien à voir avec l'archivage, et c'est pourquoi il est nommé
#: autrement.** Une actualité *annulée* est SUPPRIMÉE au bout de ce délai —
#: elle ne part pas aux archives, elle disparaît. Cette valeur portait le nom
#: `ARCHIVAGE_DELAI_HEURES` et servait aux DEUX usages : c'est une des raisons
#: pour lesquelles le site comptait « trois délais » là où il en fallait un.
#: Les rendre indépendants était indispensable AVANT d'unifier l'autre — sinon
#: porter le délai d'archivage à 30 jours aurait retardé d'un mois une
#: **suppression** de données.
PURGE_ANNULE_HEURES = 48


@dataclass(frozen=True)
class RegleArchivage:
    """Comment un type d'objet quitte les listes actives.

    Une ligne par type, et rien d'autre à écrire : c'est la déclaration qui
    varie, jamais l'algorithme. Un huitième objet s'ajoute ici, pas ailleurs.
    """

    #: Les dates candidates, **dans l'ordre de repli**. La première renseignée
    #: fait foi. Un objet en état terminal sans aucune de ces dates n'est PAS
    #: archivé : on ne sait pas dater la décision, donc on ne décide pas.
    champs_date: tuple[str, ...]
    #: Le champ qui porte l'état, s'il y en a un.
    champ_statut: Optional[str] = None
    #: Ce que vaut l'état quand il est `None` en base. `Publication.statut`
    #: vaut « publie » par défaut ; un `None` hérité doit se lire pareil.
    statut_defaut: Optional[str] = None
    #: Archivage **immédiat**, sans délai. « Annulé = immédiat quel que soit le
    #: type » — arbitré à l'écran le 19/08/2026.
    statuts_immediats: tuple[str, ...] = ()
    #: Les états qui déclenchent le compte à rebours. Vide = **le temps seul
    #: décide** (sondage clos, événement passé, affiche envoyée).
    statuts_terminaux: tuple[str, ...] = ()
    #: L'archivage à la main. Décision humaine : elle prime sur tout.
    champ_archive_manuel: Optional[str] = None
    #: L'épinglage : « garder en vue ». Il interdit l'archivage automatique.
    champ_epingle: Optional[str] = None
    #: Un brouillon n'est pas encore publié — il n'a rien à quitter.
    champ_brouillon: Optional[str] = None
    #: Le déclencheur en une phrase, destinée au manuel utilisateur. L'écrire
    #: ici plutôt que dans un ticket évite qu'il ne soit plus lisible que dans
    #: une issue fermée.
    declencheur: str = ""


#  ── LES SEPT DÉCLARATIONS ───────────────────────────────────────────────────
#
#  Les sept déclencheurs ont été tranchés à l'écran le 19/08/2026. Ils sont
#  écrits ici, et **seulement** ici.
REGLES: dict[str, RegleArchivage] = {
    "publication": RegleArchivage(
        champ_statut="statut",
        statut_defaut="publie",
        statuts_immediats=("annule",),
        #  ⚠️ « en_cours » n'y est PAS : une actualité en cours de traitement
        #  demande encore du suivi, elle ne doit pas s'effacer toute seule.
        statuts_terminaux=("publie", "resolu"),
        champs_date=("statut_change_le", "publiee_le", "cree_le"),
        champ_archive_manuel="archivee",
        champ_epingle="epingle",
        champ_brouillon="brouillon",
        declencheur="30 jours après la publication (ou le passage en « Résolu »).",
    ),
    "ticket": RegleArchivage(
        champ_statut="statut",
        #  🔴 ACCENTUÉS, et seuls de tout le site à l'être (`StatutTicket`).
        #  Une règle générale qui compare des chaînes doit le savoir, sinon
        #  elle est vraie pour six objets et fausse pour un — silencieusement.
        #  C'est le test qui le tient, pas ce commentaire.
        statuts_immediats=("annulé",),
        statuts_terminaux=("résolu",),
        champs_date=("ferme_le", "mis_a_jour_le", "cree_le"),
        declencheur="30 jours après le passage en « Résolu ». « Annulé » : immédiat.",
    ),
    "annonce": RegleArchivage(
        champ_statut="statut",
        statuts_immediats=("annule",),
        #  « reserve » n'est pas terminal : une réservation peut tomber, et
        #  l'annonce doit rester sous les yeux de son auteur.
        statuts_terminaux=("vendu", "donne"),
        #  ⚠️ `statut_change_le` et non `mis_a_jour_le` : corriger une faute de
        #  frappe sur une annonce vendue repousserait sinon son archivage d'un
        #  mois, à chaque retouche.
        champs_date=("statut_change_le", "mis_a_jour_le", "cree_le"),
        declencheur="30 jours après « Vendu » ou « Donné ». « Annulé » : immédiat.",
    ),
    "idee": RegleArchivage(
        champ_statut="statut",
        #  Aucun immédiat : « le dernier état, pour laisser le temps de voir
        #  aux gens » — y compris pour une idée rejetée, dont l'auteur doit
        #  pouvoir constater la décision.
        statuts_terminaux=("retenue", "realisee", "rejetee"),
        #  `statut_change_le` n'existait pas sur `Idee` : la migration 0155
        #  l'ajoute. Sans elle, le repli sur `cree_le` aurait archivé d'un coup
        #  toutes les idées anciennes, décidées ou non — et c'est le test de
        #  concordance des champs qui a rendu ce manque visible, pas une
        #  relecture.
        champs_date=("statut_change_le", "cree_le"),
        declencheur="30 jours après la décision (retenue, réalisée ou rejetée).",
    ),
    "sondage": RegleArchivage(
        #  Pas de statut : un sondage a une date de clôture, c'est tout.
        #  `cloture_le` peut être dans le FUTUR — le calcul le gère sans cas
        #  particulier, l'écart est alors négatif.
        champs_date=("cloture_le",),
        declencheur="30 jours après la date de clôture.",
    ),
    "evenement": RegleArchivage(
        champ_statut="statut_kanban",
        statuts_immediats=("annule",),
        #  🔴 `statuts_terminaux` volontairement VIDE : le déclencheur est **la
        #  date de l'événement**, pas son statut. C'est ce qui rend la règle
        #  robuste au cas rencontré le 19/08/2026 — l'AG 2026 portait
        #  `statut_kanban = NULL`, absente du Kanban et éternellement en tête
        #  du fil. Une règle qui aurait lu le statut serait restée muette.
        champs_date=("fin", "debut"),
        champ_archive_manuel="archivee",
        champ_epingle="epingle",
        declencheur="30 jours après la fin de l'événement. « Annulé » : immédiat.",
    ),
    "annonce_hall": RegleArchivage(
        #  Pas envoyée = pas de date = pas d'archivage. Une affiche préparée et
        #  jamais affichée reste en préparation.
        champs_date=("envoye_le",),
        champ_archive_manuel="archivee",
        declencheur="30 jours après l'envoi.",
    ),
}


def _statut_de(objet: Any, regle: RegleArchivage) -> Optional[str]:
    """L'état de l'objet, `statut_defaut` compris. Accepte un enum ou une str."""
    if not regle.champ_statut:
        return None
    brut = getattr(objet, regle.champ_statut, None)
    if brut is None:
        return regle.statut_defaut
    #  `StatutTicket.résolu` est une `str` Enum : comparer l'objet enum
    #  fonctionnerait aujourd'hui et casserait au premier enum ordinaire.
    return getattr(brut, "value", brut)


def _date_de_reference(objet: Any, regle: RegleArchivage) -> Optional[datetime]:
    """La première date renseignée parmi les candidates, ou `None`."""
    for champ in regle.champs_date:
        valeur = getattr(objet, champ, None)
        if isinstance(valeur, datetime):
            return valeur
    return None


def est_archivable(
    type_objet: str,
    objet: Any,
    seuil_jours: int = ARCHIVAGE_DELAI_JOURS,
    maintenant: Optional[datetime] = None,
) -> bool:
    """Cet objet a-t-il quitté les listes actives pour les Archives ?

    **Pure** : aucune session, aucune base, aucune horloge imposée — c'est ce
    qui la rend éprouvable pour les sept types sans monter une base de test.

    L'ordre des règles n'est pas cosmétique, chacune peut annuler la suivante :

    1. **archivage manuel** — décision humaine, elle ne se discute pas ;
    2. **brouillon** — pas encore publié, rien à quitter ;
    3. **épinglé** — « garder en vue » ; s'auto-archiver contredirait le
       marqueur (décision du 01/08/2026, prise avec le bandeau « Épinglé ») ;
    4. **état d'annulation** — immédiat, sans délai ;
    5. **état terminal** (s'il y en a) — sinon l'objet reste actif ;
    6. **délai écoulé** depuis la date de référence.
    """
    regle = REGLES.get(type_objet)
    if regle is None:
        #  Un type inconnu ne s'archive pas : la règle ne le connaît pas, elle
        #  n'a donc rien constaté. Répondre « vrai » ferait disparaître des
        #  objets sur une déclaration manquante — `standards/04` §1.
        return False

    if regle.champ_archive_manuel and getattr(objet, regle.champ_archive_manuel, False):
        return True
    if regle.champ_brouillon and getattr(objet, regle.champ_brouillon, False):
        return False
    if regle.champ_epingle and getattr(objet, regle.champ_epingle, False):
        return False

    statut = _statut_de(objet, regle)
    if statut is not None and statut in regle.statuts_immediats:
        return True
    if regle.statuts_terminaux and statut not in regle.statuts_terminaux:
        return False

    reference = _date_de_reference(objet, regle)
    if reference is None:
        #  🔴 On ne sait pas dater l'événement déclencheur. On ne décide donc
        #  PAS d'archiver : l'objet reste visible, ce qui se voit et se
        #  corrige. L'inverse — le faire disparaître faute d'information —
        #  serait une absence affirmée sans avoir été constatée.
        return False

    maintenant = maintenant or datetime.utcnow()
    return (maintenant - reference) >= timedelta(days=seuil_jours)


def seuil_archivage_jours(session: Any) -> int:
    """Le délai du site, lu **une seule fois** et au même endroit.

    Repli sur `publie_visibilite_jours` tant qu'une base n'a pas reçu la
    migration 0155 : un site à jour du code mais pas de sa configuration doit
    continuer de se comporter comme avant.

    🔴 **Et surtout pas sur `archivage_delai_heures`**, qui semble pourtant le
    candidat naturel. Cette clé vaut 48 **heures** : s'en servir ferait basculer
    les sept objets du site à **deux jours** au lieu de trente, du seul fait
    d'un déploiement. Elle ne gouvernait qu'un statut de publication devenu
    inatteignable — et la purge, qui supprime. `publie_visibilite_jours` (30 j)
    est le seul ancien réglage qui gouvernait vraiment ce que ce délai
    gouverne : quand un contenu quitte les listes actives.
    """
    from app.models.core import ConfigSite  # import local : évite un cycle

    row = session.get(ConfigSite, "archivage_delai_jours")
    if row and str(row.valeur).isdigit():
        return int(row.valeur)
    legacy = session.get(ConfigSite, "publie_visibilite_jours")
    if legacy and str(legacy.valeur).isdigit():
        return int(legacy.valeur)
    return ARCHIVAGE_DELAI_JOURS
