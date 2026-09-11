"""La synthèse proposée d'un contrat — ce qu'on envoie, et ce qu'on n'envoie pas.

## Ce que ce test protège

1. **Le geste n'est proposé que s'il a un sens** : assistant configuré, et
   matière à lire. Une icône qui échoue toujours est pire qu'une icône absente.
2. **Le gabarit en sept sections est imposé**, pas suggéré : c'est le format du
   carnet d'entretien de cette copropriété, pas celui qu'un modèle trouverait
   joli.
3. **Les synthèses déjà écrites servent d'exemples** — c'est ce qui fait que la
   proposition ressemble à celles du conseil syndical, et pas à un texte générique.
4. **Rien n'est enregistré.** Le modèle propose ; le conseil syndical relit et
   valide. Une synthèse fausse au carnet d'entretien serait pire que pas de
   synthèse : ce carnet est un document réglementaire (décret n° 2001-477).
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.documents import Document
from app.models.prestataires import ContratEntretien, Prestataire
from app.models.core import ConfigSite
from app.utils.llm import config_llm
from app.utils.synthese_contrat import (
    GABARIT,
    CONSIGNE,
    construire_matiere,
    construire_message,
    documents_du_contrat,
    entete_provenance,
    exemples,
    synthese_disponible,
)


@pytest.fixture()
def session():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        s.add(Prestataire(id=1, nom="5M Services", specialite="ascenseur"))
        s.commit()
        yield s


def _config(session, **kw):
    valeurs = {"llm_actif": "1", "llm_api_key": "sk-x", "llm_envoi_document": "1"}
    valeurs.update(kw)
    for cle, valeur in valeurs.items():
        existant = session.get(ConfigSite, cle)
        if existant:
            existant.valeur = valeur
            session.add(existant)
        else:
            session.add(ConfigSite(cle=cle, valeur=valeur))
    session.commit()


def _contrat(session, libelle="Ascenseur Bât. 1", **kw):
    c = ContratEntretien(
        copropriete_id=1,
        prestataire_id=1,
        libelle=libelle,
        date_debut=date(2024, 1, 1),
        **kw,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def _document(session, contrat, **kw):
    kw.setdefault("titre", "Contrat")
    kw.setdefault("fichier_chemin", "/introuvable/c.pdf")
    d = Document(
        fichier_nom="c.pdf",
        mime_type="application/pdf",
        contrat_id=contrat.id,
        publie_par_id=1,
        **kw,
    )
    session.add(d)
    session.commit()
    session.refresh(d)
    return d


# ── 1. Quand le geste est-il proposé ? ──────────────────────────────────────


def test_sans_assistant_configuré_le_geste_n_est_PAS_proposé(session):
    c = _contrat(session)
    _document(session, c)
    _config(session, llm_actif="0")
    assert synthese_disponible(session, c) is False


def test_sans_clé_le_geste_n_est_PAS_proposé(session):
    """Une icône qui échoue toujours est pire qu'une icône absente."""
    c = _contrat(session)
    _document(session, c)
    _config(session, llm_api_key="")
    assert synthese_disponible(session, c) is False


def test_sans_document_le_geste_n_est_PAS_proposé(session):
    """Quatre sections sur sept resteraient vides : montants, prestations
    incluses et exclues ne vivent que dans le PDF."""
    c = _contrat(session)
    _config(session)
    assert synthese_disponible(session, c) is False


def test_sans_document_MAIS_envoi_désactivé_le_geste_reste_proposé(session):
    """La synthèse est alors partielle — et c'est un choix assumé de
    l'administration, pas un accident."""
    c = _contrat(session)
    _config(session, llm_envoi_document="0")
    assert synthese_disponible(session, c) is True


def test_TOUS_les_documents_du_contrat_sont_lus(session):
    """🔴 Un contrat en a PLUSIEURS, et c'est le cas normal (signalé à l'écran).

    Contrat initial, avenants, conditions générales, attestation. N'en lire
    qu'un produirait une synthèse fausse dès le premier avenant : les conditions
    financières y changent, et la section 6 annoncerait l'ancien prix.
    """
    c = _contrat(session)
    initial = _document(session, c)
    avenant = _document(session, c)
    lus = documents_du_contrat(session, c)
    assert [d.id for d in lus] == [initial.id, avenant.id]


def test_l_ordre_est_CHRONOLOGIQUE_car_un_avenant_modifie_ce_qui_précède(session):
    """Ce qui vient après amende ce qui précède : l'ordre porte le sens, on ne
    trie donc ni par titre ni par taille."""
    from datetime import datetime

    c = _contrat(session)
    recent = _document(session, c, publie_le=datetime(2026, 5, 1))
    ancien = _document(session, c, publie_le=datetime(2024, 1, 1))
    assert [d.id for d in documents_du_contrat(session, c)] == [ancien.id, recent.id]


def test_le_document_DÉSIGNÉ_vient_en_tête_s_il_n_est_pas_déjà_joint(session):
    """C'est le contrat de référence — celui que les autres amendent."""
    c = _contrat(session)
    joint = _document(session, c)
    designe = Document(
        titre="Contrat de référence",
        fichier_nom="ref.pdf",
        fichier_chemin="/x/ref.pdf",
        mime_type="application/pdf",
        publie_par_id=1,
    )
    session.add(designe)
    session.commit()
    session.refresh(designe)
    c.document_id = designe.id
    session.add(c)
    session.commit()
    assert [d.id for d in documents_du_contrat(session, c)] == [designe.id, joint.id]


# ── 2. Ce qu'on envoie ──────────────────────────────────────────────────────


def test_les_SEPT_sections_sont_imposées():
    for n in range(1, 8):
        assert f"{n}." in GABARIT
    assert "Prestations non incluses" in GABARIT
    assert "Points d'attention" in GABARIT
    assert GABARIT in CONSIGNE


def test_la_consigne_INTERDIT_d_inventer():
    """🔴 Le point qui compte le plus. Un modèle comble volontiers une section
    vide par une formule plausible — et une synthèse plausible mais fausse, dans
    un document réglementaire, est le pire résultat possible."""
    assert "n'invente jamais" in CONSIGNE
    assert "non précisé dans les éléments fournis" in CONSIGNE


def test_les_synthèses_existantes_servent_d_EXEMPLES(session):
    """Le format s'apprend des synthèses de la maison, il ne se décrit pas."""
    _contrat(session, "Ancien", notes="1. Identification du fournisseur\n- Untel",
             type_equipement="ascenseur")
    c = _contrat(session, type_equipement="ascenseur")
    assert exemples(session, c) == ["1. Identification du fournisseur\n- Untel"]

    _config(session)
    message = construire_message(session, c, avec_document=False)
    assert "Untel" in message
    assert "déjà rédigées" in message


def test_un_contrat_du_MÊME_équipement_passe_devant(session):
    """Une synthèse d'ascenseur ressemble plus à une autre synthèse d'ascenseur
    qu'à celle d'un contrat d'espaces verts."""
    _contrat(session, "Vert", notes="SYNTHÈSE ESPACES VERTS", type_equipement="espaces_verts")
    _contrat(session, "Asc", notes="SYNTHÈSE ASCENSEUR", type_equipement="ascenseur")
    c = _contrat(session, type_equipement="ascenseur")
    assert exemples(session, c)[0] == "SYNTHÈSE ASCENSEUR"


def test_sans_texte_lisible_on_le_DIT_au_modèle(session):
    """⚠️ Sans cette phrase, le modèle comble les sections manquantes par des
    formules plausibles — le défaut exact que la consigne interdit."""
    c = _contrat(session)
    _document(session, c)  # chemin introuvable : aucun texte extrait
    _config(session)
    message = construire_message(session, c, avec_document=True)
    assert "Aucun texte de contrat n'a pu être lu" in message
    assert "non précisé dans les éléments fournis" in message


def test_les_champs_connus_de_la_base_partent_toujours(session):
    c = _contrat(session, numero_contrat="AB123", duree_initiale_valeur=3,
                 duree_initiale_unite="ans")
    _config(session)
    message = construire_message(session, c, avec_document=False)
    assert "5M Services" in message
    assert "AB123" in message
    assert "3 ans" in message


#  ── L'encart de provenance ────────────────────────────────────────────────
#  Demandé le 11/09/2026 : la synthèse atterrit dans les notes du contrat, où
#  rien ne la distingue de celles que le conseil syndical a écrites. Les trois
#  informations verrouillées ici répondent chacune à une question qui se pose
#  plus tard — qui l'a écrite, quand, et sur quoi.


def _matiere(lus=(), joints=(), ecartes=()):
    from app.utils.synthese_contrat import Matiere

    return Matiere("msg", (), tuple(lus), tuple(joints), tuple(ecartes))


def test_l_encart_nomme_le_modele_la_date_et_les_fichiers(session):
    _config(session)
    encart = entete_provenance(
        config_llm(session),
        _matiere(lus=("Conditions Particulières AXA.pdf", "Conditions Générales AXA.pdf")),
        quand=datetime(2026, 9, 11, 12, 32),
        documents_joints=0,
    )
    assert "OpenAI" in encart
    assert "11 septembre 2026 à 14:32" in encart  # UTC → Paris
    assert "Conditions Particulières AXA.pdf ; Conditions Générales AXA.pdf" in encart


def test_l_encart_dit_quand_aucun_document_n_a_ete_lu(session):
    """Sans document, la synthèse ne vaut que ce que la fiche sait — et le dire
    est ce qui empêche de la lire comme une lecture du contrat."""
    _config(session)
    encart = entete_provenance(
        config_llm(session), _matiere(), quand=datetime(2026, 9, 11, 12, 0), documents_joints=0
    )
    assert "seules données de la fiche" in encart


def test_un_titre_de_fichier_est_echappe(session):
    """Un nom de fichier voyage jusqu'à un `{@html}` : il est échappé ICI, sans
    faire reposer la correction du rendu sur l'assainisseur du front."""
    _config(session)
    encart = entete_provenance(
        config_llm(session),
        _matiere(lus=("Avenant <n°2> & suite.pdf",)),
        quand=datetime(2026, 9, 11, 12, 0),
        documents_joints=0,
    )
    assert "<n°2>" not in encart
    assert "&lt;n°2&gt; &amp; suite.pdf" in encart


#  ── Ce qui n'a PAS été lu se dit ───────────────────────────────────────────
#
#  🔴 11/09/2026, premier vrai contrat : les deux PDF de la porte de parking
#  étaient des numérisations sans couche de texte. Quatre sections sur sept
#  sortaient « non précisé » et rien n'expliquait pourquoi — cela ressemblait à
#  un mauvais modèle, alors que le modèle n'avait tout simplement rien reçu.


def test_un_document_ecarte_est_ANNONCE_avec_son_motif(session):
    _config(session)
    encart = entete_provenance(
        config_llm(session),
        _matiere(lus=("Contrat.pdf",), ecartes=(("Plan.pdf", "illisible ou trop volumineux"),)),
        quand=datetime(2026, 9, 11, 12, 0),
        documents_joints=0,
    )
    assert "synthèse est donc partielle" in encart
    assert "Plan.pdf (illisible ou trop volumineux)" in encart


def test_un_fichier_joint_REFUSE_par_le_service_compte_comme_non_lu(session):
    """🔴 C'est le nombre REÇU qui fait foi, pas celui qu'on espérait joindre.
    Sans cela, l'encart nommerait comme lu un document que le service a refusé —
    et la synthèse, appauvrie, se présenterait comme complète."""
    _config(session)
    encart = entete_provenance(
        config_llm(session),
        _matiere(joints=("Contrat scanné.pdf",)),
        quand=datetime(2026, 9, 11, 12, 0),
        documents_joints=0,
    )
    assert "seules données de la fiche" in encart
    assert "Contrat scanné.pdf (non transmis au service)" in encart


def test_un_fichier_joint_ACCEPTE_figure_parmi_les_sources(session):
    _config(session)
    encart = entete_provenance(
        config_llm(session),
        _matiere(joints=("Contrat scanné.pdf",)),
        quand=datetime(2026, 9, 11, 12, 0),
        documents_joints=1,
    )
    assert "à partir de Contrat scanné.pdf" in encart
    assert "partielle" not in encart


def test_la_consigne_impose_le_HTML_que_le_champ_de_notes_accepte(session):
    """Les notes sont un champ ENRICHI : du texte brut avec des tirets y arrive
    en un seul paragraphe. Les balises citées sont celles que `sanitize.ts`
    laisse passer ET que Tiptap sait relire."""
    for balise in ("<h3>", "<ul><li>", "<p>"):
        assert balise in CONSIGNE
    assert "Markdown" in CONSIGNE


#  ── La source des faits est CE contrat, et rien d'autre ───────────────────
#
#  🔴 Demandé le 11/09/2026 après le premier essai. Le risque n'est pas
#  théorique : trois synthèses d'AUTRES contrats voyagent dans le même message
#  comme exemples de format, et un modèle qui les lit peut en reprendre un
#  montant ou une durée. Rien, à la relecture, ne distinguerait alors un chiffre
#  emprunté d'un chiffre lu — et la synthèse alimente le carnet d'entretien,
#  qui est réglementaire (décret n° 2001-477).


def test_la_consigne_interdit_toute_source_autre_que_le_contrat():
    for exigence in ("CE contrat", "connaissance générale", "habituel"):
        assert exigence in CONSIGNE


def test_les_exemples_s_annoncent_comme_UN_FORMAT_pas_comme_des_faits(session):
    """Le bloc d'exemples doit se désigner lui-même comme un modèle de rédaction
    portant sur d'AUTRES contrats — sinon il se lit comme de la matière."""
    autre = _contrat(session, libelle="Ascenseur Bât. 2", notes="1. Fournisseur : ACME")
    assert autre.notes
    c = _contrat(session)
    _config(session)
    message = construire_message(session, c, avec_document=False)
    assert "AUTRES" in message
    assert "n'en reprends AUCUN fait" in message


def test_la_synthese_est_annoncee_comme_une_synthese_de_COPROPRIETE():
    """Le domaine cadre la lecture : un contrat de copropriété ne se résume pas
    comme un contrat commercial — ce qui compte est ce que la copropriété devra
    surveiller."""
    assert "COPROPRIÉTÉ" in CONSIGNE


#  ── Un PDF sans couche de texte part TEL QUEL ─────────────────────────────
#
#  🔴 C'est le cas NORMAL, pas l'exception : un contrat signé est numérisé. Les
#  deux PDF du contrat de porte de parking rendaient zéro caractère à `pypdf`
#  (mesuré en production le 11/09/2026, 2 pages et 1 page, 212 et 417 Ko).


def _pdf_sans_texte(tmp_path, nom="scan.pdf"):
    """Un PDF valide dont aucune page ne porte de texte — comme une numérisation."""
    from pypdf import PdfWriter

    chemin = tmp_path / nom
    ecrivain = PdfWriter()
    ecrivain.add_blank_page(width=595, height=842)
    with open(chemin, "wb") as f:
        ecrivain.write(f)
    return str(chemin)


def test_un_pdf_sans_texte_est_JOINT_au_lieu_d_etre_abandonne(session, tmp_path):
    c = _contrat(session)
    _document(session, c, titre="Contrat signé", fichier_chemin=_pdf_sans_texte(tmp_path))
    _config(session)
    m = construire_matiere(session, c, avec_document=True)
    assert len(m.fichiers) == 1
    assert m.joints == ("Contrat signé",)
    assert m.lus_en_texte == ()
    #  Et le message DIT au modèle de les lire lui-même, sinon il ne sait pas
    #  qu'il a reçu autre chose que du texte.
    assert "lis-les toi-même" in m.message
    #  ⚠️ Surtout, il ne porte PLUS la phrase qui ordonne de rendre les sections
    #  vides : elle ferait rendre « non précisé » alors que le contrat est joint.
    assert "Aucun texte de contrat n'a pu être lu" not in m.message


def test_un_pdf_LISIBLE_part_en_texte_et_pas_en_fichier(session, tmp_path):
    """Joindre un fichier dont le texte s'extrait coûterait bien plus cher pour
    exactement le même contenu."""
    c = _contrat(session)
    d = _document(session, c, titre="Contrat natif")
    _config(session)
    #  `texte_du_document` rend du texte : on simule un PDF avec couche texte.
    import app.utils.synthese_contrat as mod

    origine = mod.texte_du_document
    mod.texte_du_document = lambda doc: "ARTICLE 1 — Objet du contrat"
    try:
        m = construire_matiere(session, c, avec_document=True)
    finally:
        mod.texte_du_document = origine
    assert d.titre
    assert m.fichiers == ()
    assert m.lus_en_texte == ("Contrat natif",)


def test_un_fichier_ABSENT_est_ecarte_avec_son_motif(session):
    """Le chemin des fixtures est introuvable : ni texte, ni fichier joignable."""
    c = _contrat(session)
    _document(session, c, titre="Fantôme")
    _config(session)
    m = construire_matiere(session, c, avec_document=True)
    assert m.fichiers == ()
    assert m.ecartes == (("Fantôme", "illisible ou trop volumineux"),)


def test_un_fichier_TROP_LOURD_n_est_pas_joint(session, tmp_path, monkeypatch):
    """Une requête trop lourde est refusée par le service — et le base64
    l'alourdit encore d'un tiers. Mieux vaut l'écarter en le disant."""
    import app.utils.synthese_contrat as mod

    monkeypatch.setattr(mod, "MAX_OCTETS_DOCUMENT_JOINT", 10)
    c = _contrat(session)
    _document(session, c, titre="Plan", fichier_chemin=_pdf_sans_texte(tmp_path))
    _config(session)
    m = construire_matiere(session, c, avec_document=True)
    assert m.fichiers == ()
    assert m.ecartes == (("Plan", "illisible ou trop volumineux"),)


#  ── La citation, ce qui rend la synthèse VÉRIFIABLE ───────────────────────
#
#  🔴 11/09/2026, proposé par Philippe après le premier essai. Un montant sans
#  la phrase qui le porte oblige à rouvrir le PDF pour le contrôler — c'est-à-
#  dire à refaire le travail. Avec la citation, une erreur du modèle saute aux
#  yeux : la citation ne dit pas ce que la puce affirme.


def test_la_consigne_exige_une_CITATION_sous_chaque_fait_chiffre():
    for exigence in ("phrase EXACTE", "guillemets", "montant", "préavis"):
        assert exigence in CONSIGNE


def test_ne_pas_pouvoir_citer_vaut_ne_pas_avoir_LU():
    """La citation ne remplace pas l'interdiction d'inventer : elle la rend
    constatable. Un fait qu'on ne peut pas citer n'a pas été lu."""
    assert "Si tu ne peux pas citer" in CONSIGNE


def test_le_gabarit_reste_GENERIQUE_a_tout_contrat_de_copropriete():
    """⚠️ Un schéma détaillé par type de contrat (porte de parking, contrôle
    d'accès) aurait été exact une fois et faux au contrat suivant : une assurance
    n'a ni visites annuelles ni pièces détachées. Ce qui est imposé vaut pour
    TOUT contrat ; le détail vient du document."""
    for specifique in ("parking", "ascenseur", "contrôle d'accès", "porte"):
        assert specifique not in GABARIT.lower()
    #  Ce qui, en revanche, vaut partout et doit être demandé :
    for universel in ("SIRET", "préavis", "indexation", "option"):
        assert universel.lower() in GABARIT.lower()


def test_l_unite_d_un_montant_ne_se_perd_pas():
    """« 390 € HT/an » n'est pas « environ 390 € » : l'unité EST l'information,
    et une option chiffrée n'est pas une prestation incluse."""
    assert "HT ou TTC" in CONSIGNE
    assert "en supplément" in CONSIGNE

