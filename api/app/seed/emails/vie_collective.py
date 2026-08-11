"""Modèles d'e-mail de la vie collective : ce qui est publié et partagé.

Publications, calendrier, documents, boîte à idées, annonces de hall. Tous annoncent quelque chose que le destinataire peut aussi voir dans l'application : l'e-mail est un rappel, pas le canal principal.

Le gabarit commun (`email._wrap_email`) enveloppe ces contenus : pas de
`<html>` ni de `<body>` ici, seulement le corps riche.
"""

MODELES = [
    ("publication_syndic", "Publication transmise au syndic",
     #  Mêmes deux règles que `ticket_syndic`, où elles sont expliquées. Ici la
     #  branche « commentaire » nommait déjà la publication ; c'est celle de la
     #  création qui annonçait « Nouvelle publication » sans dire laquelle.
     '{% if is_commentaire %}{{ prefixe_copro }}\U0001f4ac Commentaire sur « {{ publication.titre }} »{% else %}{{ prefixe_copro }}Nouvelle publication — {{ publication.titre }}{% endif %} — {{ residence.nom }}',
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
     '{% if is_commentaire %}\U0001f4ac Nouveau commentaire{% else %}\U0001f4e2 Publication du conseil syndical{% endif %}'
     '</h2>'
     '<p style="margin:0 0 16px">'
     '{% if is_commentaire %}'
     'Un nouveau commentaire a été ajouté sur la publication <strong>{{ publication.titre }}</strong> par {{ auteur.prenom }} {{ auteur.nom }}{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.'
     '{% else %}'
     'Une publication a été transmise à votre attention par le conseil syndical de <strong>{{ residence.nom }}</strong>{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.'
     '{% endif %}'
     '</p>'
     '{% if is_commentaire %}'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:2px solid #1E3A5F;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#EEF2F7;padding:16px">'
     '<p style="margin:0 0 6px;font-size:13px;color:#5A6070;font-weight:600">{{ auteur.prenom }} {{ auteur.nom }} — {{ date_commentaire }}</p>'
     '<div style="font-size:14px;color:#1A1A2E">{{ commentaire | safe }}</div>'
     '{% if fichiers %}<p style="margin:8px 0 0;font-size:13px;color:#5A6070">\U0001f4ce Pièces jointes disponibles ci-dessous.</p>{% endif %}'
     '</td></tr></table>'
     '<h3 style="margin:0 0 12px;font-size:13px;font-weight:600;color:#8A8FA0;text-transform:uppercase;letter-spacing:.5px">Historique</h3>'
     '{% endif %}'
     '<table role="presentation" style="width:100%;margin:0 0 {% if is_commentaire %}8{% else %}20{% endif %}px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '{% if is_commentaire %}<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Publication initiale — {{ date_publication }}</p>{% endif %}'
     '<p style="margin:0 0 {% if is_commentaire %}8{% else %}12{% endif %}px;font-weight:700;font-size:16px;color:#1E3A5F">{{ publication.titre }}</p>'
     '<div style="font-size:14px;color:#1A1A2E">{{ publication.contenu | safe }}</div>'
     '</td></tr></table>'
     '{% if is_commentaire and evolutions %}'
     '{% for e in evolutions %}'
     '<table role="presentation" style="width:100%;margin:0 0 8px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#FFFFFF;padding:12px 16px">'
     '<p style="margin:0 0 4px;font-size:12px;color:#8A8FA0">{{ e.auteur_nom }} — {{ e.date }}</p>'
     '<div style="font-size:14px;color:#1A1A2E">{{ e.contenu | safe }}</div>'
     '</td></tr></table>'
     '{% endfor %}'
     '{% endif %}'
     '<p style="text-align:center;margin:{% if is_commentaire %}16{% else %}0{% endif %}px 0 0">'
     '<a href="{{ app.url }}/actualites#pub-{{ publication.id }}" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Voir la publication</a></p>',
     True),
    ("publication_externe", "Notification publication (email externe)",
     #  Même raison que `ticket_externe` : l'adresse est saisie à la main et peut
     #  être celle du syndic.
     '{% if is_commentaire %}{{ prefixe_copro }}Relance {{ publication.titre }}{% else %}{{ prefixe_copro }}{{ publication.titre }} — {{ residence.nom }}{% endif %}',
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
     '{% if is_commentaire %}\U0001f4ac Nouveau commentaire{% else %}\U0001f4e2 Publication{% endif %} : {{ publication.titre }}</h2>'
     '{% if is_commentaire %}'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:2px solid #1E3A5F;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#EEF2F7;padding:16px">'
     '<p style="margin:0 0 6px;font-size:13px;color:#5A6070;font-weight:600">{{ auteur.prenom }} {{ auteur.nom }} — {{ date_commentaire }}</p>'
     '<div style="font-size:14px;color:#1A1A2E">{{ commentaire | safe }}</div>'
     '{% if fichiers %}'
     '<p style="margin:8px 0 0;font-size:13px;color:#5A6070">\U0001f4ce Voir les pièces jointes ci-dessous.</p>'
     '{% endif %}'
     '</td></tr></table>'
     '<h3 style="margin:0 0 12px;font-size:14px;font-weight:600;color:#5A6070;text-transform:uppercase;letter-spacing:.5px">Historique</h3>'
     '{% endif %}'
     '<table role="presentation" style="width:100%;margin:0 0 {% if is_commentaire %}8{% else %}20{% endif %}px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Publication initiale — {{ date_publication }}</p>'
     '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ publication.titre }}</p>'
     '<div style="font-size:14px;color:#1A1A2E">{{ publication.contenu | safe }}</div>'
     '</td></tr></table>'
     '{% if is_commentaire and evolutions %}'
     '{% for e in evolutions %}'
     '<table role="presentation" style="width:100%;margin:0 0 8px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#FFFFFF;padding:12px 16px">'
     '<p style="margin:0 0 4px;font-size:12px;color:#8A8FA0">{{ e.auteur_nom }} — {{ e.date }}</p>'
     '<div style="font-size:14px;color:#1A1A2E">{{ e.contenu | safe }}</div>'
     '</td></tr></table>'
     '{% endfor %}'
     '{% endif %}'
     '<hr style="border:none;border-top:1px solid #D0D8E4;margin:20px 0 16px">'
     '<p style="margin:0;font-size:13px;color:#5A6070;text-align:center">'
     'Ce message vous a été transmis par le Conseil Syndical de la copropriété <strong>{{ residence.nom }}</strong>.</p>',
     False),
    ("calendrier_evenement_cree", "Événement calendrier créé", "Nouvel événement : {{ evenement.titre }} — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">\U0001f4c5 Nouvel événement</h2>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0 0 4px;font-size:13px;color:#C9983A;font-weight:600">{{ evenement.date }}</p>'
     '<p style="margin:0;font-weight:700;font-size:16px;color:#1E3A5F">{{ evenement.titre }}</p>'
     '</td></tr></table>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}/calendrier" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Voir le calendrier</a></p>',
     True),
    ("document_publie", "Document publié", "Nouveau document disponible — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">\U0001f4c4 Nouveau document</h2>'
     '<p style="margin:0 0 16px">Un nouveau document a été publié sur l\u2019espace de votre résidence\u202f:</p>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0;font-weight:700;font-size:16px;color:#1E3A5F">{{ document.titre }}</p>'
     '</td></tr></table>'
     # `/documents` n'a jamais existé côté front : chaque document s'affiche là
     # où il est rattaché. Le bouton menait donc à un 404 — le même que celui
     # signalé depuis un PV d'AG le 26/07/2026, resté ici parce que ce modèle
     # n'était envoyé par personne. Le lien vient de `app/utils/liens.py`.
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}{{ document.lien }}" style="display:inline-block;background:#3D6B4F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Consulter le document</a></p>',
     True),
    ("reponse_communaute", "Nouvelle réponse (Communauté)", "💬 Nouvelle réponse sur {{ reponse.rubrique_label }} — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">💬 Nouvelle réponse</h2>'
     '<p style="margin:0 0 16px">{{ reponse.auteur }} a répondu à {{ reponse.rubrique_label }} <strong>« {{ reponse.sujet }} »</strong> :</p>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0;font-size:14px;color:#1A1A2E">{{ reponse.extrait }}</p>'
     '</td></tr></table>'
     '<p style="text-align:center;margin:0"><a href="{{ reponse.lien }}" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Voir et répondre</a></p>',
     True),
    ("idee_statut", "Idée soutenue — changement de statut", "💡 L'idée « {{ idee.titre }} » est {{ idee.statut_label }} — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">💡 Une idée que vous avez soutenue avance</h2>'
     '<p style="margin:0 0 16px">Bonne nouvelle : l\'idée <strong>« {{ idee.titre }} »</strong>, que vous avez soutenue, est désormais <strong>{{ idee.statut_label }}</strong>.</p>'
     '<p style="text-align:center;margin:0"><a href="{{ idee.lien }}" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Voir la boîte à idées</a></p>',
     True),
    ("annonce_hall", "Annonce hall (PDF à afficher)",
     "\U0001f4c4 Annonce à afficher — {{ annonce.titre }} — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">\U0001f4c4 Annonce à afficher dans le hall</h2>'
     '<p style="margin:0 0 16px">{{ auteur.prenom }} {{ auteur.nom }} a préparé une annonce pour <strong>{{ annonce.perimetre }}</strong>. '
     'Le PDF est en pièce jointe, prêt à imprimer au format <strong>{{ annonce.format }}</strong> et à afficher.</p>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px;border-left:4px solid #C9983A">'
     '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">{{ annonce.perimetre }} · Format {{ annonce.format }} · {{ annonce.date }}</p>'
     '<p style="margin:0 0 8px;font-weight:700;font-size:17px;color:#1E3A5F">{{ annonce.titre }}</p>'
     '{% if annonce.apercu %}<p style="margin:0;font-size:14px;color:#5A6070">{{ annonce.apercu }}</p>{% endif %}'
     '</td></tr></table>'
     '<p style="margin:0 0 20px;font-size:13px;color:#5A6070">\U0001f4ce Pièce jointe : <strong>{{ annonce.fichier }}</strong> '
     '— imprimer en couleur, sans mise à l’échelle (100 %).</p>'
     '<p style="text-align:center;margin:0">'
     '<a href="{{ app.url }}/espace-cs?onglet=annonces-hall" '
     'style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">'
     'Voir l’historique des annonces</a></p>',
     True),
]
