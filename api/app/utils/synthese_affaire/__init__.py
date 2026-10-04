"""La **synthèse IA d'une affaire close** (#1643).

Quand une affaire qui contribue au carnet d'entretien passe en résolu ou annulé,
une synthèse est produite en différé, déposée dans une nouvelle Suite de
l'affaire, soumise au conseil pour relecture, puis validée — et alors visible
des ayants droit et dans le carnet.

| Module | Ce qu'il porte |
|---|---|
| `format` | le prompt d'origine, le format de réponse et sa relecture — sans base ni `llm` |
| `metriques` | les métriques, calculées par le code (jours ouvrés, étapes, rythme, moyenne) |
| `rassemblement` | ce qu'on lit de l'affaire, et le message envoyé à l'assistant |
| `production` | l'appel, la Suite, le remplacement, l'avis par courriel |
| `file` | l'inscription d'une demande et la tâche permanente |
| `lecture` | qui lit une synthèse (brouillon / validée), et sous quelle forme |
| `agregats` | les moyennes d'un ENSEMBLE d'affaires closes : bilan du carnet (#1645), fiche prestataire (#1646) |

L'éligibilité n'est écrite nulle part ici : c'est celle du carnet,
`carnet_entretien.contribue_au_carnet` (🔒 `test_synthese_eligibilite.py`).
"""
