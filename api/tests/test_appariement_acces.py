"""Garde-fou : appariement des badges Vigik et télécommandes aux résidents.

**Ce mécanisme n'était couvert par aucun test depuis son ouverture** — 1 203
lignes réparties sur `auto_match_service.py`, `import_vigiks.py` et
`import_telecommandes.py`. Rien ne signalait une régression, ni un effet de bord
d'une évolution voisine. Constat du 03/08/2026, à la demande de l'utilisateur.

Ce que ces tests couvrent : les fonctions **pures** de rapprochement de noms,
qui sont le cœur de la décision et la partie la plus fragile — un fichier
d'import contient des noms saisis à la main par le syndic, avec titres,
accents, apostrophes, occupants multiples dans une même cellule.

Ce qu'ils ne couvrent PAS, faute de base de test dans ce projet : la création
effective des liens (`_create_user_vigiks`, `_auto_match_tc`) et les lecteurs de
fichiers Excel. C'est une limite assumée, pas un oubli — cf.
`standards/04-fiabilite-des-controles.md` §12.

Ce sont des tests de **caractérisation** : ils figent le comportement observé,
y compris ses arbitrages discutables (voir `test_le_prenom_seul_ne_matche_pas`).
Les faire échouer n'est donc pas nécessairement un défaut — c'est un changement
de règle qui doit être conscient.
"""
import pytest

from app.utils.auto_match_service import (
    _matches_user,
    _norm,
    _split_name_candidates,
    _tokens,
    _user_keys,
)


# ── Normalisation ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("brut, attendu", [
    ("DUPONT", "dupont"),
    ("  Dupont  ", "dupont"),
    ("Éric", "eric"),
    ("MÜLLER", "muller"),
    ("D'ARTAGNAN", "d artagnan"),
    ("Saint-Exupéry", "saint exupery"),
    ("de La Fontaine", "de la fontaine"),
    ("M. DUPONT", "m dupont"),
    (None, ""),
    ("", ""),
    ("   ", ""),
])
def test_normalisation(brut, attendu):
    """Accents, casse, ponctuation et espaces multiples se neutralisent."""
    assert _norm(brut) == attendu


# ── Découpage des cellules multi-occupants ───────────────────────────────────

@pytest.mark.parametrize("brut, attendu", [
    ("DUPONT Jean", ["DUPONT Jean"]),
    ("DUPONT; MARTIN", ["DUPONT", "MARTIN"]),
    ("DUPONT / MARTIN", ["DUPONT", "MARTIN"]),
    ("DUPONT | MARTIN", ["DUPONT", "MARTIN"]),
    ("DUPONT & MARTIN", ["DUPONT", "MARTIN"]),
    ("DUPONT + MARTIN", ["DUPONT", "MARTIN"]),
    ("DUPONT ET MARTIN", ["DUPONT", "MARTIN"]),
    ("DUPONT et MARTIN", ["DUPONT", "MARTIN"]),
    ("DUPONT OU MARTIN", ["DUPONT", "MARTIN"]),
    ("", []),
    (None, []),
])
def test_decoupage_multi_occupants(brut, attendu):
    """Une cellule d'import contient souvent plusieurs occupants d'un même lot."""
    assert _split_name_candidates(brut) == attendu


def test_le_decoupage_ne_casse_pas_un_nom_contenant_et():
    """« ET » n'est un séparateur qu'entouré d'espaces — pas dans « GAETAN »."""
    assert _split_name_candidates("GAETAN DUPONT") == ["GAETAN DUPONT"]


# ── Clés de recherche d'un résident ──────────────────────────────────────────

def test_les_cles_couvrent_les_deux_ordres_et_les_variantes_compactes():
    cles = _user_keys("Dupont", "Jean")
    for attendu in ("dupont", "dupont jean", "jean dupont", "dupontjean", "jeandupont"):
        assert attendu in cles, attendu


def test_le_prenom_seul_ne_matche_pas():
    """Arbitrage volontaire, documenté dans le code : sans lui, un prénom
    courant apparierait un homonyme au badge d'un autre copropriétaire."""
    cles = _user_keys("Dupont", "Philippe")
    assert "philippe" not in cles
    assert not _matches_user("PHILIPPE", cles)


def test_un_nom_compose_reste_apparie():
    cles = _user_keys("de La Fontaine", "Jean")
    assert _matches_user("DE LA FONTAINE", cles)
    assert _matches_user("de la fontaine Jean", cles)


# ── Correspondance — les cas réels des fichiers du syndic ────────────────────

@pytest.mark.parametrize("saisie", [
    "DUPONT Jean",
    "Jean DUPONT",
    "dupont jean",
    "DUPONT  JEAN",          # espaces multiples
    "M. DUPONT JEAN",        # civilité en préfixe
    "DUPONT",                # nom seul
    "Mme DUPONT",
    "DUPONT-Jean",           # trait d'union
])
def test_correspondances_attendues(saisie):
    assert _matches_user(saisie, _user_keys("Dupont", "Jean")), saisie


@pytest.mark.parametrize("saisie", [
    "MARTIN Pierre",
    "",
    "   ",
    "SCI DU PARC",
])
def test_non_correspondances(saisie):
    assert not _matches_user(saisie, _user_keys("Dupont", "Jean")), saisie


def test_un_occupant_est_trouve_dans_une_cellule_partagee():
    """Cas courant : deux noms dans la même cellule d'un lot en indivision."""
    cles = _user_keys("Masson", "Christophe")
    assert _matches_user("ALIF; MASSON", cles)
    assert _matches_user("DUPONT ET MASSON", cles)
    assert _matches_user("ALIF MASSON", cles)


def test_un_homonyme_de_prenom_n_est_pas_apparie():
    """Le risque le plus grave : donner à un résident le badge d'un autre.

    « Philippe MARTIN » ne doit pas récupérer le badge de « Philippe DUPONT ».
    """
    cles_dupont = _user_keys("Dupont", "Philippe")
    assert not _matches_user("MARTIN Philippe", cles_dupont)
    assert not _matches_user("Philippe MARTIN", cles_dupont)


# ── Tokens significatifs ─────────────────────────────────────────────────────

def test_les_mots_courts_sont_ecartes():
    """Un seuil trop bas apparierait sur « de », « la », « du »."""
    assert _tokens("de la fontaine") == ["fontaine"]
    assert _tokens("M. DUPONT") == ["dupont"]


# ── La chaîne d'appel doit rester branchée ───────────────────────────────────

def test_l_appariement_est_declenche_a_la_validation_d_un_compte():
    """Sans ces points d'appel, un nouveau résident n'obtient jamais ses badges.

    C'est la partie que les tests unitaires ne peuvent pas voir : la logique
    peut être parfaite et n'être appelée par personne.
    """
    import pathlib

    racine = pathlib.Path(__file__).resolve().parents[2]
    appelants = {
        "api/app/routers/auth.py": "inscription / validation d'e-mail",
        "api/app/routers/admin.py": "activation d'un compte par un administrateur",
    }
    for chemin, contexte in appelants.items():
        source = (racine / chemin).read_text(encoding="utf-8")
        assert "auto_match_pour_utilisateur" in source, (
            f"{chemin} n'appelle plus l'appariement ({contexte}) : les badges "
            "ne seront plus rattachés automatiquement, sans aucune erreur visible."
        )


# ── Ce que l'appariement accepte volontairement, et ses conséquences ─────────
#
# Les tests ci-dessous NE SONT PAS des validations : ils figent un comportement
# à risque pour qu'il soit visible et surveillé. Les faire échouer signifierait
# que la règle a changé — ce qui serait une bonne nouvelle, mais doit être
# conscient.

def test_le_prenom_de_l_import_n_ecarte_jamais():
    """Le prénom sert à AJOUTER des clés, jamais à en exclure.

    Conséquence : deux foyers portant le même nom de famille sont appariés l'un
    à l'autre. Et `_auto_match_tc` ne propose pas — il CRÉE la télécommande et
    passe l'import en « résolu », sans revue humaine. Le premier des deux qui
    active son compte récupère donc les accès de l'autre.

    Signalé le 03/08/2026. Décision de conception en attente : l'atténuation la
    moins intrusive serait de ne pas AUTO-RÉSOUDRE quand la correspondance n'a
    été obtenue que par le nom de famille seul — proposer au lieu de créer.
    """
    cles = _user_keys("Martin", "Jean")
    for saisie in ("MARTIN Pierre", "MARTIN Sophie", "Pierre MARTIN"):
        assert _matches_user(saisie, cles), (
            f"« {saisie} » n'est plus apparié à Martin Jean — si c'est voulu, "
            "retirer ce test ; la correction attendue est côté auto-résolution."
        )


def test_les_noms_de_famille_courts_echappent_a_cet_elargissement():
    """Asymétrie non voulue : effet de bord du seuil « mot > 3 caractères ».

    Un résident nommé Roy, Gay ou Cot n'est apparié que sur une correspondance
    exacte — il bénéficie donc d'une règle plus sûre, mais aussi de bien moins
    d'appariements automatiques, sans que ce soit un choix.
    """
    cles = _user_keys("Roy", "Jean")
    assert _matches_user("ROY", cles), "le nom seul reste apparié"
    assert not _matches_user("ROY Pierre", cles), (
        "les noms de 3 caractères ou moins ne s'apparient pas par le nom seul"
    )


def test_une_societe_portant_le_nom_du_coproprietaire_est_appariee():
    """« SCI DUPONT ET FILS » est apparié à Dupont Jean.

    Souvent souhaitable — le gérant de la SCI est le résident — mais c'est un
    appariement d'une personne morale à une personne physique, sans contrôle.
    """
    assert _matches_user("SCI DUPONT ET FILS", _user_keys("Dupont", "Jean"))


def test_l_auto_resolution_cree_le_badge_sans_revue():
    """`_auto_match_tc` ne propose pas : il crée la Telecommande et résout.

    C'est ce qui rend les appariements larges ci-dessus conséquents. Contrôle
    statique — la logique est trop couplée à la base pour être exercée ici.
    """
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parents[1]
        / "app" / "utils" / "auto_match_service.py"
    ).read_text(encoding="utf-8")

    assert "StatutImport.resolu" in source and "session.add(tc)" in source, (
        "L'auto-résolution a changé de forme : revoir si la création sans revue "
        "est toujours le comportement, et mettre ces tests à jour."
    )
