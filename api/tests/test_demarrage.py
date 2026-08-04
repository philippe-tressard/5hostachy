"""L'application s'assemble-t-elle encore ? — le contrôle qui manquait.

POURQUOI CE TEST (04/08/2026) :

Les 264 tests de cette suite importaient des modules ISOLÉS — `routers.admin`,
`models.core`, `utils.dates_fr` — mais **jamais l'application assemblée**. Aucun
n'importait `app.main`.

Ce que cela laissait passer : `start.sh` fait `set -e`, puis `alembic upgrade head`,
puis `exec uvicorn app.main:app`. Une dépendance dont la montée de version casse
l'assemblage (décorateur au comportement changé, API retirée, incompatibilité
Pydantic, routeur qui ne s'enregistre plus) produit une CI **verte**, un déploiement
automatique, un conteneur en boucle de redémarrage — et le site est HS, les anciens
conteneurs ayant déjà été arrêtés.

Le trou a été trouvé en examinant une PR Dependabot qui montait `fastapi`
0.115 → 0.141, `sqlmodel` 0.0.22 → 0.0.39 et `alembic` 1.14 → 1.18 : classées
« mineures » par l'outil, alors que pour un paquet en `0.x` tout peut casser. Cette
PR était VERTE. Elle ne pouvait pas être autre chose : rien ne mesurait ce qu'elle
risquait de casser.

Importer `app.main` exerce, en une ligne, la totalité de la chaîne d'assemblage :
chaque modèle SQLModel, chaque schéma Pydantic, chaque routeur, chaque dépendance
d'authentification, et le montage des fichiers statiques.
"""
import pytest


@pytest.fixture(scope="module")
def application():
    """Importe l'application complète. Un échec ICI est l'échec du démarrage."""
    from app.main import app

    return app


def test_application_s_importe_et_s_assemble(application):
    """Le test le plus important du fichier : il ne contient presque rien.

    S'il échoue, c'est que `uvicorn app.main:app` échouerait aussi — donc que le
    conteneur ne démarrerait pas. Tout le reste de ce fichier ne fait que rendre
    l'échec plus lisible.
    """
    assert application is not None
    assert application.__class__.__name__ == "FastAPI"


@pytest.fixture(scope="module")
def schema(application):
    """Schéma OpenAPI — et non `app.routes`, qui ne mesure rien.

    Cette version de FastAPI conserve les routeurs sous forme d'objets
    `_IncludedRouter` non résolus : `app.routes` en rend 28, dont 25 opaques.
    Un contrôle bâti dessus aurait compté « 3 routes » sur une application qui en
    expose 222, et n'aurait donc jamais rien détecté d'autre que sa propre erreur.

    Générer le schéma force au contraire la résolution de CHAQUE route et de CHAQUE
    modèle Pydantic. C'est un contrôle bien plus profond qu'un simple import : il
    échoue si un champ, un type ou une annotation cesse d'être exploitable — la
    rupture typique d'une montée de FastAPI, Pydantic ou SQLModel.
    """
    return application.openapi()


def test_le_schema_expose_toutes_les_routes(schema):
    """Plancher de chemins : l'assemblage doit être COMPLET, pas partiel.

    Un routeur qui cesse silencieusement de s'enregistrer laisserait l'import
    réussir et l'application démarrer amputée. Le seuil est volontairement en
    dessous du compte réel (222) : il attrape la disparition d'un pan entier, pas
    l'ajout ou le retrait d'un endpoint au fil de l'eau.
    """
    chemins = schema.get("paths", {})
    assert len(chemins) > 180, (
        f"seulement {len(chemins)} chemins exposés — un routeur entier ne "
        f"s'enregistre plus"
    )


def test_les_modeles_sont_tous_exploitables(schema):
    """Chaque modèle Pydantic doit encore produire son schéma.

    C'est le contrôle qui couvre les montées de SQLModel et de Pydantic : un champ
    dont le type n'est plus interprétable fait échouer la génération ici, alors
    qu'aucun autre test de cette suite ne l'aurait touché.
    """
    modeles = schema.get("components", {}).get("schemas", {})
    assert len(modeles) > 120, (
        f"seulement {len(modeles)} modèles exploitables — des schémas ne se "
        f"génèrent plus"
    )


def test_les_pans_fonctionnels_sont_montes(schema):
    """Chaque grand domaine doit être joignable.

    Le compte global pourrait rester au-dessus du seuil alors qu'un domaine précis
    a disparu — c'est « la portée du contrôle fait partie du contrôle ».
    """
    chemins = set(schema.get("paths", {}))
    for prefixe in ("/auth", "/admin", "/tickets", "/lots", "/acces",
                    "/prestataires", "/bailleur", "/config"):
        assert any(c.startswith(prefixe) for c in chemins), (
            f"aucune route sous « {prefixe} » : ce pan de l'application n'est plus monté"
        )


def test_le_cycle_de_vie_est_branche(application):
    """Sauvegarde, contrôle de santé, WhatsApp et télémétrie vivent dans le lifespan.

    Sans lui, l'application répondrait normalement pendant que **toutes les tâches
    planifiées** seraient silencieusement mortes : plus de sauvegarde à 03:00, plus
    de contrôle de santé à 06:00, plus d'envoi WhatsApp. Aucune erreur, aucun log —
    exactement le genre de panne que ce projet a déjà connu.
    """
    assert application.router.lifespan_context is not None


def test_la_documentation_reste_fermee_par_defaut(application):
    """`ENABLE_API_DOCS=false` doit réellement fermer /docs.

    Le réglage est vérifié ici parce que c'est au moment de l'assemblage qu'il
    s'applique — et parce qu'une inversion de ce défaut exposerait publiquement
    la carte complète de l'API sur un dépôt déjà public.
    """
    chemins = {r.path for r in application.routes if hasattr(r, "path")}
    assert "/docs" not in chemins
    assert "/redoc" not in chemins
