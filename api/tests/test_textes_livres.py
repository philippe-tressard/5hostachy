"""Remplacer un texte livré en base — une règle, plus quinze copies (24/09/2026).

`_remplacer` était recopié dans quinze migrations, chacune avec sa requête SQL
écrite à la main. Une migration appliquée ne se modifie jamais : les quinze
sont FIGÉES ici, et la seizième est refusée — elle appelle
`utils/textes_livres.remplacer_si_intact`.
"""
from __future__ import annotations

import pathlib

import sqlalchemy as sa

from app.utils.textes_livres import remplacer_passage, remplacer_si_intact

_VERSIONS = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"

#: Les copies d'avant le 24/09/2026 — de l'historique, pas un retard à résorber.
COPIES_FIGEES = frozenset({
    "0121_relance_syndic_preambule.py", "0128_liens_morts_modeles_email.py",
    "0131_relance_syndic_signature.py", "0133_relance_syndic_interlocuteurs.py",
    "0135_objet_email_nomme.py", "0136_reference_copro_obligatoire.py",
    "0162_ticket_syndic_perimetre.py", "0164_annonce_hall_lien_actualite.py",
    "0184_calendrier_suivi_annonce_ses_pieces.py", "0185_document_publie_description_et_lien.py",
    "0192_nom_affiche_dans_les_courriels.py", "0195_faq_locataire_corrigee.py",
    "0198_faq_ecrans_renommes.py", "0201_faq_dit_affaire.py", "0203_les_courriels_disent_affaire.py",
})


def test_aucune_nouvelle_copie_de_remplacer():
    copies = {f.name for f in _VERSIONS.glob("*.py") if "def _remplacer" in f.read_text(encoding="utf-8")}
    assert copies, "cas zéro : aucune copie trouvée — le motif a dérivé, ce contrôle ne mesure plus rien"
    assert copies <= COPIES_FIGEES, f"copie nouvelle de `_remplacer` : {sorted(copies - COPIES_FIGEES)}"
    assert COPIES_FIGEES <= copies, f"copie figée disparue : {sorted(COPIES_FIGEES - copies)}"


def test_seul_le_texte_intact_est_remplace():
    moteur = sa.create_engine("sqlite://")
    with moteur.begin() as conn:
        conn.execute(sa.text("CREATE TABLE faq_item (question TEXT, reponse TEXT)"))
        conn.execute(sa.text("INSERT INTO faq_item VALUES ('Q', 'livré'), ('Q', 'reformulé par le conseil')"))
        n = remplacer_si_intact(conn, "faq_item", {"question": "Q", "reponse": "livré"}, {"reponse": "corrigé"})
        lignes = sorted(r[0] for r in conn.execute(sa.text("SELECT reponse FROM faq_item")))
    assert n == 1
    assert lignes == ["corrigé", "reformulé par le conseil"]


def test_un_passage_n_est_remplace_que_s_il_figure_tel_quel():
    moteur = sa.create_engine("sqlite://")
    with moteur.begin() as conn:
        conn.execute(sa.text("CREATE TABLE config_site (cle TEXT, valeur TEXT)"))
        conn.execute(sa.text("INSERT INTO config_site VALUES ('a', 'avant FAUX après'), ('b', 'reformulé')"))
        n_a = remplacer_passage(conn, "config_site", {"cle": "a"}, "valeur", "FAUX", "JUSTE")
        n_b = remplacer_passage(conn, "config_site", {"cle": "b"}, "valeur", "FAUX", "JUSTE")
        n_c = remplacer_passage(conn, "config_site", {"cle": "absente"}, "valeur", "FAUX", "JUSTE")
        lignes = dict(conn.execute(sa.text("SELECT cle, valeur FROM config_site")).all())
    assert (n_a, n_b, n_c) == (1, 0, 0)
    assert lignes == {"a": "avant JUSTE après", "b": "reformulé"}
