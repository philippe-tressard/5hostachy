"""Garde-fous des calculs de télémétrie (#354).

Ces tests existent parce que le défaut qu'ils décrivent était **invisible** :
la colonne « UTILISATEURS » de Top pages additionnait des cardinalités de
distincts, et la capture qui a servi à le signaler montrait 1 partout — un seul
jour était agrégé. Le calcul faux et le calcul juste donnaient donc le même
résultat ce jour-là. Il fallait plusieurs jours pour que l'erreur se voie, et
personne ne regardait.

Le premier test est le **cas zéro** (`standards/04` §2) : il échoue sur l'ancien
calcul et passe sur le nouveau. Sans lui, ces tests ne prouveraient pas qu'ils
savent détecter quoi que ce soit.
"""

from app.utils.telemetrie_calculs import uniques_par_page, vues_non_attribuees


def test_meme_visiteur_plusieurs_jours_compte_pour_un():
    """LE défaut de #354 : trois jours du même visiteur ne font pas trois visiteurs.

    L'ancien code sommait les agrégats journaliers — 1 + 1 + 1 = 3. La vérité est
    1, et c'est ce que compte une union d'ensembles.
    """
    trois_jours_du_meme = [("/actualites", 7), ("/actualites", 7), ("/actualites", 7)]
    assert uniques_par_page(trois_jours_du_meme) == {"/actualites": 1}


def test_visiteurs_differents_s_additionnent_bien():
    """Le pendant du précédent : le nouveau calcul ne sous-compte pas non plus."""
    paires = [("/actualites", 7), ("/actualites", 8), ("/actualites", 9)]
    assert uniques_par_page(paires) == {"/actualites": 3}


def test_pages_distinctes_sont_comptees_separement():
    paires = [("/actualites", 7), ("/tickets", 7), ("/tickets", 8)]
    assert uniques_par_page(paires) == {"/actualites": 1, "/tickets": 2}


def test_vues_anonymes_ignorees_et_ne_creent_pas_de_page():
    """Une page vue UNIQUEMENT par des anonymes n'a aucun utilisateur à montrer.

    Elle ne doit pas apparaître avec « 0 utilisateur » comme s'il s'agissait d'une
    mesure : elle n'est simplement pas attribuable. Le total de ces vues est rendu
    par `vues_non_attribuees()`, qui est là pour ça.
    """
    assert uniques_par_page([("/faq", None), ("/faq", None)]) == {}


def test_liste_vide():
    assert uniques_par_page([]) == {}


def test_ecart_explique_le_cas_signale():
    """Les nombres exacts de la capture du 15/08/2026 : 78 vues, 74 attribuées."""
    assert vues_non_attribuees(78, 74) == 4


def test_ecart_nul_quand_tout_est_attribue():
    assert vues_non_attribuees(74, 74) == 0


def test_ecart_negatif_borne_a_zero():
    """Les deux totaux ne viennent pas de la même source ni de la même fraîcheur :
    les agrégats de 02:00 d'un côté, les événements bruts de l'autre. Selon
    l'heure, l'écart peut s'inverser — mieux vaut n'afficher aucun écart qu'un
    nombre absurde."""
    assert vues_non_attribuees(70, 74) == 0
