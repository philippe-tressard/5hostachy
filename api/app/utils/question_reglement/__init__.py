"""Questions au règlement de copropriété — l'avis d'un juriste, extraits à l'appui.

Le conseil syndical charge le texte de travail du règlement (Markdown) et pose
la question d'un résident ; l'assistant répond par un verdict, une réponse
argumentée, des extraits cités mot pour mot et des réserves. Le CODE vérifie
que chaque extrait figure dans le texte et en déduit la page.

| Module | Ce qu'il porte |
|---|---|
| `format` | le prompt d'origine, la forme de la réponse, sa relecture — pur |
| `extraits` | la recherche des citations et leur repère de page — pur |
| `texte` | charger une version du texte, lire celle en vigueur |
| `production` | l'appel à l'assistant et la trace de la réponse |
"""
