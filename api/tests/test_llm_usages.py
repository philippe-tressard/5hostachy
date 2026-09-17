"""L'assistant IA par USAGE — deux étages de configuration (#984, 17/09/2026).

## Ce que ce test protège

1. **Le commun et le par-usage sont deux étages**, lus ensemble par
   `config_llm(session, usage)`. Le modèle, le prompt et le plafond viennent
   des clés `llm_<usage>_*` ; la clé, le fournisseur et le délai du commun.
2. **Pas de modèle commun** : un usage sans modèle ne part pas, et le message
   nomme l'usage. Le repli silencieux sur `fournisseur.modele_defaut` a
   disparu — il faisait appeler un modèle que personne n'avait choisi.
3. **Le prompt se replie sur l'origine** quand la clé est vide : « Rétablir le
   prompt d'origine » vide la clé, et un modèle sans consigne serait pire.
4. **L'activation se vérifie aux deux étages**, et le test de connexion n'en
   exige aucun.
5. **La migration 0194** déplace les anciennes clés et pose les prompts UNE
   fois, sans écraser ce qu'un administrateur a déjà réglé.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.core import ConfigSite
from app.utils.llm import ErreurLLM, config_llm
from app.utils.llm_usages import (
    CHAMPS_USAGE,
    USAGES,
    USAGE_DESCRIPTION,
    USAGE_SYNTHESE_CONTRAT,
    decrire,
)
from app.utils.synthese_format import CONSIGNE


@pytest.fixture()
def session():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        yield s


def _poser(session, **valeurs):
    for cle, valeur in valeurs.items():
        existant = session.get(ConfigSite, cle)
        if existant:
            existant.valeur = valeur
            session.add(existant)
        else:
            session.add(ConfigSite(cle=cle, valeur=valeur))
    session.commit()


# ── 1. Le registre ─────────────────────────────────────────────────────────


def test_les_deux_usages_sont_declares_et_chacun_a_un_prompt_d_origine():
    assert set(USAGES) == {USAGE_SYNTHESE_CONTRAT, USAGE_DESCRIPTION}
    for u in USAGES.values():
        assert u.prompt_defaut.strip()
        assert u.max_jetons_defaut > 0


def test_le_prompt_d_origine_de_la_synthese_EST_la_consigne_assemblee():
    """Philippe : *« initialise le prompt à partir de ce qui a déjà été défini
    pour le use case 1 »*. C'est la consigne complète — gabarit, citations,
    règles, format — pas un fragment."""
    assert USAGES[USAGE_SYNTHESE_CONTRAT].prompt_defaut == CONSIGNE


def test_les_cles_suivent_UNE_convention():
    u = USAGES[USAGE_DESCRIPTION]
    assert u.cle("modele") == "llm_description_modele"
    assert u.cle("prompt") == "llm_description_prompt"


def test_l_ecran_recoit_les_cles_et_les_origines_jamais_les_valeurs():
    """Les valeurs courantes viennent de `GET /config/admin` : ce descriptif ne
    doit pas devenir une seconde lecture de la configuration."""
    for d in decrire():
        assert set(d["cles"]) == set(CHAMPS_USAGE)
        assert "prompt_defaut" in d
        assert "valeur" not in d and "modele" not in d


# ── 2. Deux étages de configuration ────────────────────────────────────────


def test_le_par_usage_vient_des_cles_de_l_usage(session):
    _poser(
        session,
        llm_actif="1",
        llm_api_key="sk-x",
        llm_delai_s="12",
        llm_synthese_contrat_actif="1",
        llm_synthese_contrat_modele="gpt-5",
        llm_synthese_contrat_prompt="MA CONSIGNE",
        llm_synthese_contrat_max_jetons="4200",
        llm_description_modele="gpt-4o-mini",
    )
    cfg = config_llm(session, USAGE_SYNTHESE_CONTRAT)
    assert cfg.delai_s == 12                    # commun
    assert cfg.modele == "gpt-5"                # usage
    assert cfg.prompt == "MA CONSIGNE"
    assert cfg.max_jetons == 4200
    assert cfg.actif_usage is True
    #  L'autre usage lit SES clés — rien ne fuit de l'un à l'autre.
    autre = config_llm(session, USAGE_DESCRIPTION)
    assert autre.modele == "gpt-4o-mini"
    assert autre.actif_usage is False


def test_sans_modele_l_usage_ne_part_PAS_et_le_dit(session):
    """🔴 Plus de repli sur le modèle par défaut du fournisseur : l'arbitrage
    est « un modèle par usage », et un repli silencieux appellerait un modèle
    que personne n'a choisi pour cet usage."""
    _poser(session, llm_actif="1", llm_api_key="sk-x", llm_description_actif="1")
    cfg = config_llm(session, USAGE_DESCRIPTION)
    assert cfg.modele == ""
    with pytest.raises(ErreurLLM) as e:
        cfg.verifier()
    assert "modèle" in str(e.value).lower()
    assert "Rédaction d'une description" in str(e.value)


def test_un_prompt_vide_retombe_sur_l_origine(session):
    _poser(session, llm_synthese_contrat_prompt="   ")
    assert config_llm(session, USAGE_SYNTHESE_CONTRAT).prompt == CONSIGNE


def test_les_anciennes_cles_ne_sont_PLUS_lues(session):
    """`llm_modele` a été déplacée par la 0194 : la relire ici redonnerait deux
    vérités — l'écran en écrirait une, l'appel en lirait une autre."""
    _poser(session, llm_modele="gpt-oublie", llm_max_jetons="99")
    cfg = config_llm(session, USAGE_SYNTHESE_CONTRAT)
    assert cfg.modele == ""
    assert cfg.max_jetons == USAGES[USAGE_SYNTHESE_CONTRAT].max_jetons_defaut


# ── 3. L'activation aux deux étages ────────────────────────────────────────


def _complet(session, **kw):
    valeurs = dict(
        llm_actif="1",
        llm_api_key="sk-x",
        llm_description_actif="1",
        llm_description_modele="m",
    )
    valeurs.update(kw)
    _poser(session, **valeurs)


def test_le_commun_coupe_tout_d_un_geste(session):
    _complet(session, llm_actif="0")
    cfg = config_llm(session, USAGE_DESCRIPTION)
    assert cfg.pret is False
    with pytest.raises(ErreurLLM) as e:
        cfg.verifier()
    assert "désactivé" in str(e.value)


def test_l_usage_se_coupe_seul_et_le_message_le_nomme(session):
    _complet(session, llm_description_actif="0")
    cfg = config_llm(session, USAGE_DESCRIPTION)
    assert cfg.pret is False
    with pytest.raises(ErreurLLM) as e:
        cfg.verifier()
    assert "Rédaction d'une description" in str(e.value)


def test_le_test_de_connexion_n_exige_aucune_activation(session):
    """L'ordre naturel : je saisis, je teste, PUIS j'active — aux deux étages."""
    _complet(session, llm_actif="0", llm_description_actif="0")
    config_llm(session, USAGE_DESCRIPTION).verifier(exiger_actif=False)


def test_pret_dit_oui_quand_tout_y_est(session):
    _complet(session)
    assert config_llm(session, USAGE_DESCRIPTION).pret is True


def test_le_catalogue_des_modeles_n_exige_pas_de_modele(session):
    """Le catalogue sert justement à en CHOISIR un : l'exiger avant serait
    circulaire."""
    _poser(session, llm_api_key="sk-x")
    config_llm(session).verifier(exiger_actif=False, exiger_modele=False)


# ── 4. La migration 0194 — déplacer sans écraser, poser une fois ───────────

_MIGRATION = (
    Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0194_assistant_ia_par_usage.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("mig0194", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_la_migration_couvre_TOUTES_les_tables_qui_portent_la_marque():
    """Le mixin est hérité par neuf modèles ; la migration doit poser la
    colonne sur les neuf, ni plus ni moins — comparé au CODE, pas à une liste."""
    from app.utils.assiste_ia import AssisteIAMixin

    import app.models.core  # noqa: F401 — charge les tables dans la metadata
    import app.models.communaute  # noqa: F401
    import app.models.evenement  # noqa: F401

    def descendants(cls):
        for sous in cls.__subclasses__():
            yield sous
            yield from descendants(sous)

    #  Seules les TABLES comptent : les mixins intermédiaires (`EvolutionMixin`)
    #  ne sont pas `table=True` et n'ont rien à recevoir.
    attendues = {
        m.__tablename__
        for m in descendants(AssisteIAMixin)
        if getattr(m, "__table__", None) is not None
    }
    assert len(attendues) >= 9, attendues
    assert set(_module().TABLES_ASSISTE_IA) == attendues


def test_la_migration_deplace_les_anciennes_cles_et_ne_les_laisse_pas(session):
    """Deux clés pour un réglage seraient deux vérités."""
    _poser(session, llm_actif="1", llm_modele="gpt-4o", llm_max_jetons="8000")
    m = _module()
    conn = session.connection()
    for ancienne, nouvelle in m.DEPLACEMENTS.items():
        valeur = m._lire(conn, ancienne)
        m._poser_si_absent(conn, nouvelle, valeur)
        m._retirer(conn, ancienne)
    assert m._lire(conn, "llm_synthese_contrat_modele") == "gpt-4o"
    assert m._lire(conn, "llm_synthese_contrat_max_jetons") == "8000"
    assert m._lire(conn, "llm_modele") is None


def test_poser_si_absent_n_ecrase_JAMAIS_un_reglage_existant(session):
    """Une migration se rejoue (`standards/06` §3) : un prompt que
    l'administrateur a réécrit doit survivre au redémarrage suivant."""
    _poser(session, llm_synthese_contrat_prompt="LE MIEN")
    m = _module()
    conn = session.connection()
    m._poser_si_absent(conn, "llm_synthese_contrat_prompt", "ORIGINE")
    assert m._lire(conn, "llm_synthese_contrat_prompt") == "LE MIEN"
    m._poser_si_absent(conn, "llm_description_prompt", "ORIGINE 2")
    assert m._lire(conn, "llm_description_prompt") == "ORIGINE 2"
