"""Modèles d'e-mail du circuit des tickets, du signalement à la relance.

C'est le seul circuit qui sort de la copropriété : `ticket_syndic`, `ticket_externe` et `relance_syndic` s'adressent au syndic ou à un tiers, et leur ton engage le conseil syndical. Ils changent quand ce circuit change.

Le gabarit commun (`email._wrap_email`) enveloppe ces contenus : pas de
`<html>` ni de `<body>` ici, seulement le corps riche.
"""

MODELES = [
    ("ticket_bug_admin", "Ticket bug — notification admin site",
     "Bug signalé via Tickets — {{ ticket.titre }} — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#c0392b">⚠ Bug signalé</h2>'
     '<p style="margin:0 0 12px">Un ticket de type <strong style="color:#c0392b">Bug</strong> a été soumis par <strong>{{ auteur.prenom }} {{ auteur.nom }}</strong>{% if auteur.email %} (<a href="mailto:{{ auteur.email }}" style="color:#1E3A5F">{{ auteur.email }}</a>){% endif %}.</p>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#FDF0F0;padding:16px;border-left:4px solid #c0392b">'
     '<p style="margin:0 0 4px;font-weight:700;font-size:16px;color:#1A1A2E">{{ ticket.titre }}</p>'
     '<p style="margin:0;font-size:14px;color:#5A6070">{{ ticket.description }}</p>'
     '</td></tr></table>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}/tickets/{{ ticket.id }}" style="display:inline-block;background:#c0392b;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Traiter le bug</a></p>',
     True),
    ("ticket_syndic", "Ticket transmis au syndic",
     #  `{{ prefixe_copro }}` ouvre les DEUX branches — il ne manquait qu'à celle
     #  du commentaire, donc un échange sur un ticket déjà transmis arrivait sans
     #  référence. La règle et sa forme unique : `seed/emails/__init__.py`.
     #
     #  Le **titre** passe avant le nom de la résidence : un client de messagerie
     #  n'affiche qu'une soixantaine de caractères, et sur ces quatre
     #  informations, celle que le destinataire ne connaît pas encore est le
     #  titre. La résidence est ce qu'on accepte de perdre.
     '{% if is_commentaire %}{{ prefixe_copro }}\U0001f4ac Commentaire — Ticket #{{ ticket.numero }} — {{ ticket.titre }} — {{ residence.nom }}{% else %}{{ prefixe_copro }}Ticket #{{ ticket.numero }} — {{ ticket.titre }} — {{ residence.nom }}{% endif %}',
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
     '{% if is_commentaire %}\U0001f4ac Nouveau commentaire{% else %}\U0001f4cb Ticket transmis par le conseil syndical{% endif %}'
     '</h2>'
     '<p style="margin:0 0 16px">'
     '{% if is_commentaire %}'
     'Un nouveau commentaire a été ajouté sur le ticket <strong>#{{ ticket.numero }} — {{ ticket.titre }}</strong> par {{ auteur.prenom }} {{ auteur.nom }}{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.'
     '{% else %}'
     'Un ticket a été transmis à votre attention par le conseil syndical de <strong>{{ residence.nom }}</strong>{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.'
     '{% endif %}'
     '</p>'
     '{% if is_commentaire %}'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:2px solid #1E3A5F;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#EEF2F7;padding:16px">'
     '<p style="margin:0 0 6px;font-size:13px;color:#5A6070;font-weight:600">{{ auteur.prenom }} {{ auteur.nom }} — {{ date_commentaire }}{% if commentaire_perimetre %} — \U0001f539 {{ commentaire_perimetre }}{% endif %}</p>'
     '<div style="font-size:14px;color:#1A1A2E">{{ commentaire | safe }}</div>'
     '{% if fichiers %}<p style="margin:8px 0 0;font-size:13px;color:#5A6070">\U0001f4ce Pièces jointes disponibles ci-dessous.</p>{% endif %}'
     '</td></tr></table>'
     '<h3 style="margin:0 0 12px;font-size:13px;font-weight:600;color:#8A8FA0;text-transform:uppercase;letter-spacing:.5px">Historique</h3>'
     '{% endif %}'
     '<table role="presentation" style="width:100%;margin:0 0 {% if is_commentaire %}8{% else %}20{% endif %}px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Ticket #{{ ticket.numero }}{% if ticket.categorie %} · {{ ticket.categorie }}{% endif %}{% if ticket.perimetre %} · \U0001f539 {{ ticket.perimetre }}{% endif %}{% if is_commentaire %} — Soumis le {{ date_creation }}{% endif %}</p>'
     '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ ticket.titre }}</p>'
     '{% if ticket.description %}<div style="font-size:14px;color:#1A1A2E">{{ ticket.description | safe }}</div>{% endif %}'
     '{% if not is_commentaire %}<p style="margin:8px 0 0;font-size:14px;color:#5A6070">Soumis par {{ auteur.prenom }} {{ auteur.nom }}</p>{% endif %}'
     '</td></tr></table>'
     '{% if is_commentaire and messages %}'
     '{% for m in messages %}'
     '<table role="presentation" style="width:100%;margin:0 0 8px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#FFFFFF;padding:12px 16px">'
     '<p style="margin:0 0 4px;font-size:12px;color:#8A8FA0">{{ m.auteur_nom }} — {{ m.date }}{% if m.perimetre %} — \U0001f539 {{ m.perimetre }}{% endif %}</p>'
     '<div style="font-size:14px;color:#1A1A2E">{{ m.contenu | safe }}</div>'
     '</td></tr></table>'
     '{% endfor %}'
     '{% endif %}'
     '{% if not is_commentaire and historique and historique|length > 1 %}'
     '<h3 style="margin:0 0 8px;font-size:15px;color:#1E3A5F">Historique</h3>'
     '<table role="presentation" style="border-collapse:collapse;width:100%;font-size:.88rem;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden">'
     '{% for h in historique %}'
     '<tr style="background:{% if loop.index is odd %}#F2EFE9{% else %}#FFFFFF{% endif %}">'
     '<td style="padding:.35rem .75rem;border-bottom:1px solid #D0D8E4;white-space:nowrap;color:#5A6070;font-size:.82rem">{{ h.date }}</td>'
     '<td style="padding:.35rem .75rem;border-bottom:1px solid #D0D8E4;color:#1A1A2E">{{ h.label }}</td>'
     '</tr>{% endfor %}'
     '</table>'
     '{% endif %}'
     '<p style="text-align:center;margin:{% if is_commentaire %}16{% else %}0{% endif %}px 0 0">'
     '<a href="{{ app.url }}/tickets/{{ ticket.id }}" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Consulter le ticket</a></p>',
     True),
    ("ticket_statut_change", "Statut ticket modifié",
     "Ticket #{{ ticket.numero }} mis à jour — {{ ticket.titre }} — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Mise à jour de votre ticket</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0 0 16px">Le statut de votre ticket a été mis à jour\u202f:</p>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Ticket #{{ ticket.numero }}</p>'
     '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ ticket.titre }}</p>'
     '<p style="margin:0"><span style="display:inline-block;background:#3D6B4F;color:#fff;padding:4px 12px;border-radius:4px;font-size:13px;font-weight:600">{{ ticket.statut }}</span></p>'
     '</td></tr></table>',
     True),
    ("ticket_nouveau_message", "Nouveau message sur un ticket",
     "Nouveau message — Ticket #{{ ticket.numero }} — {{ ticket.titre }} — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">💬 Nouveau message sur votre ticket</h2>'
     '<p style="margin:0 0 16px">Un nouveau message a été ajouté sur le ticket <strong>#{{ ticket.numero }} — {{ ticket.titre }}</strong> par {{ auteur_action.prenom }} {{ auteur_action.nom }}\u202f:</p>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0;font-size:14px;color:#1A1A2E">{{ message.contenu }}</p>'
     '</td></tr></table>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}/tickets/{{ ticket.id }}" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Voir le ticket</a></p>',
     True),
    ("relance_syndic", "Relance tickets syndic non résolus",
     "{{ prefixe_copro }}Relance ticket(s) sans avancée depuis {{ anciennete }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
     '\U0001f514 Relance ticket(s) sans avancée depuis {{ anciennete }}</h2>'
     '<p style="margin:0 0 20px">{{ interlocuteurs }},</p>'
     # Préambule partenarial (choisi le 01/08/2026) : poser l’ancienneté réelle
     # et le mécontentement qu’elle nourrit, sans mettre le gestionnaire en
     # accusation — la relance reste un outil de travail, pas un grief.
     '<p style="margin:0 0 16px">Le Conseil Syndical de la copropriété <strong>{{ residence.nom }}</strong> '
     'se permet de revenir vers vous concernant les tickets ci-dessous, transmis au syndic '
     'et toujours <strong>sans avancée après {{ anciennete }}</strong>.</p>'
     '<p style="margin:0 0 16px">Nous mesurons la charge qui pèse sur la gestion d’un '
     'portefeuille de copropriétés. C’est précisément pour vous éviter des '
     'sollicitations répétées que nous regroupons ici l’ensemble des dossiers '
     'en attente. Leur ancienneté commence toutefois à nourrir un mécontentement '
     'que nous préférerions désamorcer ensemble.</p>'
     '<p style="margin:0 0 20px">Un simple point d’étape, même succinct, sur chacun '
     'd’eux nous permettrait de rassurer les résidents.</p>'
     '{% for item in tickets %}'
     '<table role="presentation" style="width:100%;margin:0 0 24px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden">'
     '<tr><td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0 0 8px;font-weight:700;font-size:15px;color:#1E3A5F">'
     '{{ item.numero }} — {{ item.titre }}'
     '{% if item.relance_count > 0 %}'
     ' <span style="background:#DC2626;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px;margin-left:8px">'
     'Relance n°{{ item.relance_count }}</span>'
     '{% else %}'
     ' <span style="background:#F59E0B;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px;margin-left:8px">'
     '1ère relance</span>'
     '{% endif %}'
     '</p>'
     '<p style="margin:0 0 6px;font-size:12px;color:#4B5563">'
     'Catégorie\u202f: {{ item.categorie | capitalize }} · Priorité\u202f: {{ item.priorite | capitalize }}'
     '{% if item.perimetre %} · Périmètre\u202f: {{ item.perimetre }}{% endif %}'
     '</p>'
     '<p style="margin:0 0 10px;font-size:13px;font-weight:600;color:#374151">Description\u202f:</p>'
     '<div style="font-size:13px;color:#1A1A2E;white-space:pre-line">{{ item.description }}</div>'
     '<p style="margin:12px 0 6px;font-size:13px;font-weight:600;color:#374151">Historique\u202f:</p>'
     '<ul style="margin:0;padding-left:1.2em;font-size:12px;color:#374151">'
     '{% for h in item.historique %}'
     '<li style="margin-bottom:3px">{{ h.date }} — {{ h.label }}</li>'
     '{% endfor %}'
     '</ul>'
     '</td></tr></table>'
     '{% endfor %}'
     '<p style="margin:24px 0 0">Nous vous remercions de bien vouloir nous tenir informés '
     'des actions engagées sur ces dossiers.</p>'
     # Signature sans le nom de la résidence : « Le Conseil Syndical de
     # {{ residence.nom }} » rendait « … de Les Hostachy ». L'article du nom
     # propre ne se contracte pas, et le destinataire sait déjà de quelle
     # copropriété il s'agit — le préambule le dit, l'objet aussi.
     '<p style="margin:8px 0 0">Cordialement,<br>'
     '<strong>Le Conseil Syndical</strong></p>',
     False),
    ("ticket_externe", "Notification ticket (email externe)",
     #  Ce canal vise « le syndic ou un tiers » (cf. l'en-tête de ce module) :
     #  l'adresse est saisie à la main et rien ne dit laquelle des deux. Il porte
     #  donc la référence lui aussi — inoffensive pour un prestataire,
     #  indispensable pour le syndic, et c'est la seule façon de tenir « sans
     #  exception » sur un destinataire que le code ne peut pas identifier.
     '{% if is_commentaire %}{{ prefixe_copro }}Relance Ticket #{{ ticket.numero }} — {{ ticket.titre }}{% else %}{{ prefixe_copro }}Ticket #{{ ticket.numero }} — {{ ticket.titre }}{% endif %}',
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
     '{% if is_commentaire %}\U0001f4ac Nouveau commentaire{% else %}\U0001f527 Ticket{% endif %} : {{ ticket.titre }}</h2>'
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
     '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Ticket #{{ ticket.numero }}{% if ticket.categorie %} · {{ ticket.categorie }}{% endif %} — {{ date_creation }}</p>'
     '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ ticket.titre }}</p>'
     '<div style="font-size:14px;color:#1A1A2E">{{ ticket.description | safe }}</div>'
     '</td></tr></table>'
     '{% if is_commentaire and messages %}'
     '{% for m in messages %}'
     '<table role="presentation" style="width:100%;margin:0 0 8px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#FFFFFF;padding:12px 16px">'
     '<p style="margin:0 0 4px;font-size:12px;color:#8A8FA0">{{ m.auteur_nom }} — {{ m.date }}</p>'
     '<div style="font-size:14px;color:#1A1A2E">{{ m.contenu | safe }}</div>'
     '</td></tr></table>'
     '{% endfor %}'
     '{% endif %}'
     '<hr style="border:none;border-top:1px solid #D0D8E4;margin:20px 0 16px">'
     '<p style="margin:0;font-size:13px;color:#5A6070;text-align:center">'
     'Ce message vous a été transmis par le Conseil Syndical de la copropriété <strong>{{ residence.nom }}</strong>.</p>',
     False),
]
