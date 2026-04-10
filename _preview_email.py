"""Génère un aperçu HTML de l'email redesigné — ouvrir le fichier .html dans un navigateur."""
import sys, os, webbrowser

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "5hostachy", "api"))

# ── Import _wrap_email directement (sans dépendance DB) ──

# Logo SVG inline
_LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="48" height="48">'
    '<rect width="64" height="64" rx="14" fill="#1E3A5F"/>'
    '<g fill="none" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M18 54V18a4 4 0 0 1 4-4h20a4 4 0 0 1 4 4v36Z"/>'
    '<path d="M18 34h-6a4 4 0 0 0-4 4v16h10"/>'
    '<path d="M46 30h6a4 4 0 0 1 4 4v20H46"/>'
    '<path d="M25 22h14"/><path d="M25 30h14"/><path d="M25 38h14"/><path d="M25 46h14"/>'
    '</g>'
    '<path d="M48 50c0 4.4-3.6 8-8 8h14a8 8 0 0 0-6-8Z" fill="#C9983A" opacity=".95"/>'
    '</svg>'
)

def _wrap_email(body_html, site_nom, site_url, footer, annee):
    safe_footer = ""
    if footer:
        import re as _re
        linked_footer = _re.sub(
            r'(https?://\S+|(?<!\w)([a-zA-Z0-9-]+\.)+[a-z]{2,}(?:/\S*)?)',
            lambda m: f'<a href="{m.group(0) if m.group(0).startswith("http") else "https://" + m.group(0)}" '
                      f'style="color:#1E3A5F;text-decoration:underline">{m.group(0)}</a>',
            footer,
        )
        safe_footer = (
            f'<tr><td style="background-color:#FAFAF7;padding:20px 32px 24px;text-align:center">'
            f'<p style="margin:0;font-size:13px;color:#5A6070">{linked_footer}</p>'
            f'</td></tr>'
        )
    return f'''<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{site_nom}</title></head>
<body style="margin:0;padding:0;background-color:#F2EFE9;font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,Roboto,'Helvetica Neue',Arial,sans-serif;color:#1A1A2E;-webkit-text-size-adjust:100%">

<!-- Wrapper -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F2EFE9;padding:24px 0">
<tr><td align="center">

<!-- Container -->
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(30,58,95,0.12)">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#1E3A5F 0%,#16304F 100%);padding:28px 32px;text-align:center">
    <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto"><tr>
      <td style="vertical-align:middle;padding-right:14px">{_LOGO_SVG}</td>
      <td style="vertical-align:middle;text-align:left">
        <div style="font-family:Georgia,'Palatino Linotype','Book Antiqua',Palatino,serif;font-size:22px;font-weight:700;color:#FFFFFF;letter-spacing:0.3px">{site_nom}</div>
        <div style="font-size:12px;color:#C9983A;letter-spacing:1.5px;text-transform:uppercase;margin-top:2px;font-weight:600">Espace numérique de résidence</div>
      </td>
    </tr></table>
  </td></tr>

  <!-- Accent bar -->
  <tr><td style="height:4px;background:linear-gradient(90deg,#C9983A 0%,#1E3A5F 50%,#3D6B4F 100%)"></td></tr>

  <!-- Body -->
  <tr><td style="background-color:#FFFFFF;padding:32px 32px 24px;font-size:15px;line-height:1.65;color:#1A1A2E">
    {body_html}
  </td></tr>

  <!-- Notification preferences -->
  <tr><td style="background-color:#FFFFFF;padding:0 32px 20px;text-align:center">
    <p style="margin:0;font-size:12px;color:#8A8FA0">Pour g\u00e9rer vos pr\u00e9f\u00e9rences de notification, rendez-vous dans votre <a href="{site_url.rstrip('/')}/profil" style="color:#1E3A5F;text-decoration:underline">profil</a>.</p>
  </td></tr>

  <!-- Footer -->
  {safe_footer}

</table>
<!-- /Container -->

</td></tr>
</table>
<!-- /Wrapper -->
</body>
</html>'''


# ── 4 templates de démo ──

templates = {
    "invitation": (
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Bienvenue, Philippe\u202f!</h2>'
        '<p style="margin:0 0 12px">Vous avez été invité(e) à rejoindre l\u2019espace numérique de <strong>Résidence Les Music-Halls</strong>.</p>'
        '<p style="margin:0 0 24px;color:#5A6070">Créez votre compte en quelques clics pour accéder aux documents, au calendrier, aux tickets et à toutes les informations de votre résidence.</p>'
        '<p style="text-align:center;margin:0 0 8px"><a href="https://5hostachy.fr/inscription" style="display:inline-block;background:#C9983A;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Créer mon compte</a></p>'
    ),
    "ticket": (
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Nouveau ticket soumis</h2>'
        '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
        '<td style="background:#F2EFE9;padding:16px">'
        '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Ticket #42</p>'
        '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">Fuite d\'eau parking sous-sol B2</p>'
        '<p style="margin:0;font-size:14px;color:#5A6070">par Jean Dupont</p>'
        '</td></tr></table>'
        '<p style="text-align:center;margin:0"><a href="https://5hostachy.fr/tickets/42" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Voir le ticket</a></p>'
    ),
    "compte_active": (
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Votre compte est activé\u202f!</h2>'
        '<p style="margin:0 0 12px">Bonjour Philippe,</p>'
        '<p style="margin:0 0 24px">Votre compte sur <strong>Résidence Les Music-Halls</strong> est maintenant actif. Vous pouvez dès à présent accéder à l\u2019ensemble des services de votre résidence.</p>'
        '<p style="text-align:center;margin:0"><a href="https://5hostachy.fr" style="display:inline-block;background:#3D6B4F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Accéder à l\u2019application</a></p>'
    ),
    "urgence": (
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#c0392b">\U0001f6a8 Ticket URGENT</h2>'
        '<p style="margin:0 0 12px">Bonjour Philippe,</p>'
        '<p style="margin:0 0 16px">Un ticket <strong style="color:#c0392b">URGENT</strong> a été soumis concernant votre lot <strong>B12</strong>\u202f:</p>'
        '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
        '<td style="background:#FDF0F0;padding:16px;border-left:4px solid #c0392b">'
        '<p style="margin:0;font-weight:700;font-size:16px;color:#1A1A2E">Dégât des eaux — infiltration plafond</p>'
        '</td></tr></table>'
    ),
    "syndic": (
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">\U0001f4cb Ticket transmis par le conseil syndical</h2>'
        '<p style="margin:0 0 16px">Un ticket a été transmis à votre attention par le conseil syndical de <strong>5Hostachy</strong> — réf. COPRO-2026-001.</p>'
        '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
        '<td style="background:#F2EFE9;padding:16px">'
        '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Ticket #42 · Maintenance</p>'
        '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">Fuite d\'eau parking sous-sol B2</p>'
        '<p style="margin:0 0 8px;font-size:14px;color:#1A1A2E">Une fuite a été constatée au niveau du joint de dilatation, côté rampe d\'accès. L\'eau s\'accumule sur 2 m² environ.</p>'
        '<p style="margin:0;font-size:14px;color:#5A6070">Soumis par Jean Dupont</p>'
        '</td></tr></table>'
        '<p style="text-align:center;margin:0"><a href="https://5hostachy.fr/tickets/42" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Consulter le ticket</a></p>'
    ),
}


# ── Valeurs réelles : lues depuis la DB locale si elle existe, sinon defaults du seed ──
SITE_NOM = "5Hostachy"
SITE_URL = "https://example.com/"
EMAIL_FOOTER = "— ©2026-5Hostachy - Envoyé depuis 5hostachy.fr —"

try:
    import sqlite3
    for db_path in [
        os.path.join(os.path.dirname(__file__), "5hostachy", "api", "data", "app.db"),
        os.path.join(os.path.dirname(__file__), "5hostachy", "data", "app.db"),
    ]:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            for cle, default, attr in [
                ("site_nom", SITE_NOM, "SITE_NOM"),
                ("site_url", SITE_URL, "SITE_URL"),
                ("email_footer", EMAIL_FOOTER, "EMAIL_FOOTER"),
            ]:
                row = cur.execute("SELECT valeur FROM configsite WHERE cle = ?", (cle,)).fetchone()
                if row and row[0]:
                    globals()[attr] = row[0]
            conn.close()
            print(f"✅ Config lue depuis {db_path}")
            break
except Exception as e:
    print(f"⚠ Pas de DB locale, utilisation des valeurs par défaut du seed ({e})")

print(f"   site_nom     = {SITE_NOM}")
print(f"   site_url     = {SITE_URL}")
print(f"   email_footer = {EMAIL_FOOTER}")

# ── Génération d'un fichier HTML combiné ──

combined = f'''<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>Aperçu emails — {SITE_NOM}</title>
<style>
  body {{ background: #e8e4de; margin: 0; padding: 40px 20px; font-family: 'Segoe UI', sans-serif; }}
  h1 {{ text-align: center; color: #1E3A5F; font-family: Georgia, serif; margin-bottom: 8px; }}
  p.subtitle {{ text-align: center; color: #5A6070; margin-bottom: 40px; }}
  .email-block {{ margin: 0 auto 50px; max-width: 660px; }}
  .email-label {{ background: #1E3A5F; color: #fff; padding: 8px 16px; border-radius: 8px 8px 0 0; font-weight: 600; font-size: 14px; }}
</style></head><body>
<h1>Aperçu des emails — {SITE_NOM}</h1>
<p class="subtitle">5 modèles de démonstration avec le nouveau gabarit · footer : {EMAIL_FOOTER}</p>
'''

labels = {
    "invitation": "📩 Invitation résident",
    "ticket": "🎫 Nouveau ticket (CS)",
    "compte_active": "✅ Compte activé",
    "urgence": "🚨 Ticket urgence (bailleur)",
    "syndic": "📋 Ticket transmis au syndic",
}

for key, body in templates.items():
    # Remplacer les placeholders de démo par le vrai nom de résidence
    body = body.replace("Résidence Les Music-Halls", SITE_NOM)
    body = body.replace("https://5hostachy.fr", SITE_URL.rstrip("/"))

    full_html = _wrap_email(
        body,
        site_nom=SITE_NOM,
        site_url=SITE_URL,
        footer=EMAIL_FOOTER,
        annee=2026,
    )
    # Strip the <!DOCTYPE> / <html> / <body> tags to embed inline
    inner = full_html
    for tag in ["<!DOCTYPE html>", "<html lang=\"fr\">", "</html>"]:
        inner = inner.replace(tag, "")
    inner = inner.replace("<head>", "").replace("</head>", "")
    inner = inner.replace('<meta charset="utf-8">', "")
    inner = inner.replace('<meta name="viewport" content="width=device-width,initial-scale=1">', "")
    inner = inner.replace(f"<title>{SITE_NOM}</title>", "")
    inner = inner.replace("<body", "<div").replace("</body>", "</div>")

    combined += f'<div class="email-block"><div class="email-label">{labels[key]}</div>{inner}</div>\n'

combined += '</body></html>'

out = os.path.join(os.path.dirname(__file__), "_email_preview.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(combined)

print(f"✅ Aperçu généré : {out}")
webbrowser.open(out)
