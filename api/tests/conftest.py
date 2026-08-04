"""Configuration pytest — variables d'environnement minimales avant import de l'app.

L'import de `app.config` exige un SECRET_KEY ≥ 32 caractères et `app.database`
instancie un engine depuis `database_url`. On fournit des valeurs neutres pour
que les tests s'exécutent sans .env ni base réelle (aucun test ici ne se
connecte à la base : ils lisent les templates et la chaîne de migrations).
"""
import os
import tempfile

os.environ.setdefault("SECRET_KEY", "x" * 40)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENABLE_API_DOCS", "false")

#  Importer `app.main` monte `/uploads` en statique et crée le répertoire au
#  passage. Sans redirection, ce `mkdir` vise un chemin absolu de conteneur —
#  il échoue sur un poste Windows comme sur un exécuteur d'intégration continue,
#  et rendait l'application entière intestable. Cf. tests/test_demarrage.py.
os.environ.setdefault(
    "UPLOADS_DIR", os.path.join(tempfile.gettempdir(), "hostachy-tests-uploads")
)
