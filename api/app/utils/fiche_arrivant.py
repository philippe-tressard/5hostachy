"""Génération dynamique de la fiche d'accueil (fiche arrivant) en HTML."""
from __future__ import annotations

import base64
import io
from collections import defaultdict
from html import escape
from pathlib import Path


# ── Helpers ──────────────────────────────────────────────────────────────────

def _qr_data_uri(url: str) -> str:
    """QR code → data:image/png;base64,..."""
    try:
        import qrcode

        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception:
        return ""


def _photo_data_uri(photo_url: str | None) -> str | None:
    if not photo_url:
        return None
    path = Path("/app") / photo_url.lstrip("/")
    if not path.is_file():
        return None
    try:
        return f"data:image/jpeg;base64,{base64.b64encode(path.read_bytes()).decode()}"
    except Exception:
        return None


def _initials(prenom: str, nom: str) -> str:
    p = prenom.strip()[0].upper() if prenom and prenom.strip() else "?"
    n = nom.strip()[0].upper() if nom and nom.strip() else "?"
    return p + n


# ── SVG icons (inlined) ─────────────────────────────────────────────────────

_LOGO_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="36" height="36">
  <rect width="64" height="64" rx="14" fill="#1E3A5F"/>
  <g fill="none" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <path d="M18 54V18a4 4 0 0 1 4-4h20a4 4 0 0 1 4 4v36Z"/>
    <path d="M18 34h-6a4 4 0 0 0-4 4v16h10"/>
    <path d="M46 30h6a4 4 0 0 1 4 4v20H46"/>
    <path d="M25 22h14"/><path d="M25 30h14"/><path d="M25 38h14"/><path d="M25 46h14"/>
  </g>
  <path d="M48 50c0 4.4-3.6 8-8 8h14a8 8 0 0 0-6-8Z" fill="#C9983A" opacity=".95"/>
</svg>'''

_GLOBE_SVG = '<svg style="width:14px;height:14px;vertical-align:-2px;margin-right:2px" viewBox="0 0 24 24" fill="none" stroke="#1E3A5F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg>'

_WA_SVG = '<svg style="width:14px;height:14px;vertical-align:-2px;margin-right:2px" viewBox="0 0 24 24" fill="#25D366"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.019-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51l-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413z"/></svg>'


# ── CSS ──────────────────────────────────────────────────────────────────────

_CSS = """\
@page { size: A4; margin: 6mm 8mm; }
@media print {
  body { background: none !important; }
  .page { box-shadow: none !important; border: none !important; }
}
:root {
  --navy: #1E3A5F; --navy-dark: #16304F; --gold: #C9983A; --green: #3D6B4F;
  --bg: #F2EFE9; --card: #FFFFFF; --ink: #1A1A2E; --muted: #5A6070;
  --light-muted: #8A8FA0; --footer-bg: #FAFAF7; --border: #E5E2DC;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, 'Helvetica Neue', Arial, sans-serif;
  color: var(--ink); background: var(--bg); line-height: 1.4; font-size: 12.5px;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.page {
  max-width: 210mm; height: 281mm; margin: 0 auto; background: var(--card);
  border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(30,58,95,.12);
  display: flex; flex-direction: column;
}
.header {
  background: linear-gradient(135deg, var(--navy) 0%, var(--navy-dark) 100%);
  padding: 12px 20px; display: flex; align-items: center; gap: 10px;
}
.header svg { flex-shrink: 0; }
.header-text { flex: 1; }
.header-title {
  font-family: Georgia, 'Palatino Linotype', 'Book Antiqua', Palatino, serif;
  font-size: 18px; font-weight: 700; color: #fff; letter-spacing: .3px;
}
.header-sub {
  font-size: 10px; color: var(--gold); letter-spacing: 1.5px;
  text-transform: uppercase; margin-top: 1px; font-weight: 600;
}
.accent-bar {
  height: 3px;
  background: linear-gradient(90deg, var(--gold) 0%, var(--navy) 50%, var(--green) 100%);
}
.content { padding: 10px 20px; flex: 1; }
.content h2 {
  font-family: Georgia, 'Palatino Linotype', serif;
  font-size: 16px; font-weight: 700; color: var(--navy); margin-bottom: 3px;
}
.content h3 {
  font-size: 12.5px; font-weight: 700; color: var(--navy);
  margin: 8px 0 4px; padding-bottom: 2px;
  border-bottom: 2px solid var(--gold); display: inline-block;
}
.content p { margin-bottom: 4px; font-size: 12px; }
.content .muted { color: var(--muted); font-size: 10.5px; }
.dual-cta { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 6px 0; }
.cta-banner {
  display: flex; align-items: center; gap: 8px;
  background: linear-gradient(135deg, #F7F5F0, #F0EDE6);
  border-radius: 6px; padding: 7px 10px; border-left: 4px solid var(--gold);
}
.cta-banner-text { flex: 1; }
.cta-banner-text .label { font-size: 9px; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: .5px; }
.cta-banner-text .url { font-size: 13px; font-weight: 700; color: var(--navy); letter-spacing: .3px; }
.cta-banner-text .hint { font-size: 9px; color: var(--light-muted); margin-top: 1px; }
.bat-section { margin-bottom: 4px; }
.bat-label {
  font-size: 10px; font-weight: 700; color: var(--navy);
  text-transform: uppercase; letter-spacing: .5px;
  padding: 2px 6px; border-left: 3px solid var(--gold);
  margin-bottom: 3px; background: #FAFAF7;
}
.bat-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 3px; }
.annuaire-section { margin-top: 6px; }
.annuaire-section h3 { margin-top: 6px; }
.contact-card {
  background: #F7F5F0; border-radius: 5px; padding: 4px 8px;
  border-left: 3px solid var(--navy); display: flex; align-items: center; gap: 6px;
}
.contact-card.president { border-left-color: var(--green); background: #F2F7F4; }
.contact-card.syndic { border-left-color: #7C3AED; }
.contact-card.principal { border-left-color: var(--gold); background: #FDFAF3; }
.contact-avatar {
  width: 24px; height: 24px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 9px; font-weight: 700; color: #fff; flex-shrink: 0;
}
.contact-avatar.navy { background: var(--navy); }
.contact-avatar.green { background: var(--green); }
.contact-avatar.gold { background: var(--gold); }
.contact-avatar.purple { background: #7C3AED; }
.contact-body { flex: 1; min-width: 0; }
.contact-name { font-size: 11px; font-weight: 600; color: var(--ink); }
.contact-role { font-size: 8.5px; color: var(--gold); font-weight: 600; text-transform: uppercase; letter-spacing: .5px; }
.contact-info { font-size: 9.5px; color: var(--muted); line-height: 1.3; }
.syndic-header {
  background: linear-gradient(135deg, #F7F5F0, #F0EDE6); border-radius: 6px;
  padding: 7px 10px; margin-top: 4px; margin-bottom: 3px; overflow: visible;
}
.syndic-name { font-size: 12px; font-weight: 700; color: var(--navy); }
.syndic-detail { font-size: 10px; color: var(--muted); }
.syndic-contacts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; }
.contact-photo {
  width: 24px; height: 24px; border-radius: 50%;
  object-fit: cover; flex-shrink: 0;
}
.qr-code { width: 52px; min-width: 52px; height: 52px; flex-shrink: 0; display: block; }
.sep { border: none; height: 1px; background: var(--border); margin: 6px 0; }
.footer {
  background: var(--footer-bg); padding: 6px 20px; text-align: center;
  border-top: 1px solid var(--border);
}
.footer p { font-size: 10px; color: var(--light-muted); }
.consignes-intro {
  background: linear-gradient(135deg, #F7F5F0, #F0EDE6);
  border-radius: 6px; padding: 8px 12px; margin-bottom: 6px;
  border-left: 4px solid var(--gold);
}
.consignes-intro p { margin: 0; font-size: 10.5px; color: var(--muted); line-height: 1.35; }
.consignes-intro strong { color: var(--navy); }
.regle {
  margin-bottom: 5px; padding: 6px 10px;
  background: #FAFAF7; border-radius: 5px;
  border-left: 3px solid var(--green); page-break-inside: avoid;
}
.regle-titre { font-size: 12px; font-weight: 700; color: var(--navy); margin-bottom: 2px; }
.regle-contenu { font-size: 10.5px; color: var(--muted); line-height: 1.35; white-space: pre-wrap; }
.regle-contenu strong { color: var(--ink); }
.consigne-footer-note {
  text-align: center; margin-top: 6px;
  font-size: 10px; color: var(--light-muted); font-style: italic;
}
.whatsapp-cta {
  display: flex; align-items: center; gap: 8px; padding: 7px 10px;
  background: linear-gradient(135deg, #E8F5E9, #F1F8E9);
  border-radius: 6px; border-left: 4px solid #25D366;
}
.whatsapp-cta .wa-text { flex: 1; }
.whatsapp-cta .wa-title { font-size: 11px; font-weight: 700; color: var(--navy); margin-bottom: 1px; }
.whatsapp-cta .wa-desc { font-size: 9px; color: var(--muted); line-height: 1.3; }
.whatsapp-cta .wa-desc strong { color: var(--ink); }
"""


# ── Consignes (contenu statique) ─────────────────────────────────────────────

_CONSIGNES = [
    (
        "📦 1. Emménagement / déménagement",
        "Prévenez le conseil syndical du bâtiment concerné, <strong>1 semaine à l'avance</strong>, "
        "pour toute arrivée ou départ afin de permettre à ce dernier d'effectuer un état des lieux "
        "des parties communes avant et après.\n"
        "Pensez à demander l'autorisation à la mairie pour le stationnement des camions devant la copropriété.\n"
        "Protégez au mieux les parties communes lors des déménagements (ascenseur, escaliers, halls) "
        "et évacuez les cartons et encombrants rapidement, sans les laisser dans les couloirs ou les locaux à poubelles.\n"
        "Demander au syndic IFF Gestion de changer les noms sur la boîte aux lettres et l'interphone.",
    ),
    (
        "🗑 2. Sortie des poubelles et tri",
        "Déchets encombrants : <strong>ne pas les laisser dans les parties communes</strong>. "
        "Apportez-les à la déchèterie ou en collecte sur le trottoir :\n"
        "<strong>Boulevard Hostachy</strong> : Collecte des encombrants à partir de 6h, "
        "le 3ème samedi de chaque mois. Sortir la veille après 19h.\n"
        "<strong>Rue Maurice Berteaux</strong> : Collecte des encombrants à partir de 6h, "
        "le 4ème samedi de chaque mois. Sortir la veille après 19h.",
    ),
    (
        "🏢 3. Parties communes",
        "Gardez les couloirs, escaliers et halls propres. "
        "Ne laissez rien traîner : poubelles, poussettes, vélos, cartons, etc.\n"
        "Respectez la tranquillité des lieux : évitez de faire du bruit, surtout entre 22h et 7h.\n"
        "Ne donnez pas de code ou de clé aux personnes non autorisées.",
    ),
]


# ── Builders ─────────────────────────────────────────────────────────────────

def _build_cs_card(m: dict) -> str:
    """Carte d'un membre CS."""
    is_president = m.get("est_president", False)
    is_gestionnaire = m.get("est_gestionnaire_site", False)
    photo_uri = _photo_data_uri(m.get("photo_url"))

    card_class = "contact-card"
    if is_president:
        card_class += " president"
    elif is_gestionnaire:
        card_class += '" style="border-left-color:var(--navy);background:#F5F7FA;'

    initials = _initials(m.get("prenom", ""), m.get("nom", ""))
    avatar_color = "green" if is_president else ("gold" if is_gestionnaire else "navy")

    if photo_uri and is_gestionnaire:
        avatar_html = f'<img class="contact-photo" src="{photo_uri}" alt="{initials}">'
    else:
        avatar_html = f'<div class="contact-avatar {avatar_color}">{initials}</div>'

    role_html = ""
    if is_gestionnaire:
        role_html = '<div class="contact-role">🏢 Gestionnaire du site</div>'
    elif is_president:
        role_html = '<div class="contact-role">Président</div>'

    etage_html = f"Étage {m['etage']}" if m.get("etage") else ""

    return (
        f'<div class="{card_class}">'
        f"  {avatar_html}"
        f'  <div class="contact-body">'
        f"    {role_html}"
        f'    <div class="contact-name">{escape(m["genre"])} {escape(m["prenom"])} {escape(m["nom"].upper())}</div>'
        f'    <div class="contact-info">{escape(etage_html)}</div>'
        f"  </div>"
        f"</div>"
    )


def _build_cs_section(cs_data: dict) -> str:
    """Section Conseil Syndical groupée par bâtiment."""
    membres = cs_data.get("membres", [])
    if not membres:
        return ""

    ag_annee = cs_data.get("ag_annee")
    ag_date = cs_data.get("ag_date", "")

    by_bat: dict[str, list] = defaultdict(list)
    for m in membres:
        bat = m.get("batiment_nom") or "?"
        by_bat[bat].append(m)

    html = '<div class="annuaire-section">\n'
    html += '  <h3>📇 Conseil Syndical</h3>\n'
    if ag_annee:
        html += f'  <p class="muted" style="margin-bottom:8px;font-size:11.5px">Voté en AG {ag_annee}'
        if ag_date:
            from datetime import date as dt_date

            try:
                d = dt_date.fromisoformat(ag_date)
                html += f" — {d.strftime('%d %B %Y').lstrip('0')}"
            except Exception:
                html += f" — {ag_date}"
        html += "</p>\n"

    for bat_nom, bat_membres in sorted(by_bat.items()):
        html += '  <div class="bat-section">\n'
        html += f'    <div class="bat-label">Bât. {escape(bat_nom)}</div>\n'
        html += '    <div class="bat-grid">\n'
        for m in bat_membres:
            html += f"      {_build_cs_card(m)}\n"
        html += "    </div>\n"
        html += "  </div>\n"

    html += "</div>\n"
    return html


def _build_syndic_section(syndic_data: dict) -> str:
    """Section Syndic."""
    nom = syndic_data.get("nom_syndic", "")
    adresse = syndic_data.get("adresse", "")
    site_web = syndic_data.get("site_web")
    membres = syndic_data.get("membres", [])

    qr_html = ""
    if site_web:
        qr_src = _qr_data_uri(site_web)
        if qr_src:
            qr_html = f'<img class="qr-code" src="{qr_src}" alt="QR Extranet">'

    html = f'<h3>🏛 Syndic — {escape(nom)}</h3>\n'
    html += '<div class="syndic-header" style="display:flex;align-items:center;gap:10px;">\n'
    html += '  <div style="flex:1;">\n'
    html += '    <div style="display:flex;align-items:baseline;gap:6px;flex-wrap:wrap;">\n'
    html += f'      <span class="syndic-name">{escape(nom)}</span>\n'
    html += f'      <span class="syndic-detail">📍 {escape(adresse)}</span>\n'
    html += "    </div>\n"
    html += "  </div>\n"
    html += f"  {qr_html}\n"
    html += "</div>\n"

    if membres:
        html += '<div class="syndic-contacts">\n'
        for m in membres:
            is_principal = m.get("est_principal", False)
            card_class = "contact-card principal" if is_principal else "contact-card syndic"
            avatar_color = "gold" if is_principal else "purple"
            initials = _initials(m.get("prenom", ""), m.get("nom", ""))

            role_label = "★ " + (m.get("fonction") or "Gestionnaire") if is_principal else (m.get("fonction") or "")

            info_parts = []
            if m.get("email"):
                info_parts.append(f"✉ {escape(m['email'])}")
            if m.get("telephone"):
                for tel in m["telephone"].split(","):
                    tel = tel.strip()
                    if tel:
                        info_parts.append(f"☎ {escape(tel)}")
            info_html = "<br>".join(info_parts)

            html += f'  <div class="{card_class}">\n'
            html += f'    <div class="contact-avatar {avatar_color}">{initials}</div>\n'
            html += f'    <div class="contact-body">\n'
            if role_label:
                html += f'      <div class="contact-role">{escape(role_label)}</div>\n'
            html += f'      <div class="contact-name">{escape(m.get("genre", ""))} {escape(m.get("prenom", ""))} {escape(m.get("nom", "").upper())}</div>\n'
            html += f'      <div class="contact-info">{info_html}</div>\n'
            html += f"    </div>\n"
            html += f"  </div>\n"
        html += "</div>\n"

    return html


def _build_consignes_section(site_url: str) -> str:
    html = '<h3>📋 Consignes de la copropriété</h3>\n'
    html += '<div class="consignes-intro">\n'
    html += (
        "  <p>À la demande du Conseil syndical, il est rappelé à Mesdames et Messieurs "
        "les résidents que les dispositions du règlement de copropriété relatives aux "
        "parties communes et à la vie collective doivent être respectées par tous et "
        "notamment ce qui suit.</p>\n"
    )
    html += "</div>\n"

    for titre, contenu in _CONSIGNES:
        html += '<div class="regle">\n'
        html += f'  <div class="regle-titre">{titre}</div>\n'
        html += f'  <div class="regle-contenu">{contenu}</div>\n'
        html += "</div>\n"

    html += f'<p class="consigne-footer-note">Ce document est un résumé. Le règlement complet est disponible sur <strong>{escape(site_url)}</strong> → Résidence.</p>\n'
    return html


# ── Public API ───────────────────────────────────────────────────────────────

def generer_fiche_arrivant(
    *,
    cs_data: dict,
    syndic_data: dict,
    site_url: str = "5hostachy.fr",
    whatsapp_url: str | None = None,
    annee: int = 2026,
) -> str:
    """Génère le HTML complet de la fiche arrivant à partir des données annuaire."""
    site_qr = _qr_data_uri(f"https://{site_url}")
    wa_qr = _qr_data_uri(whatsapp_url) if whatsapp_url else ""

    # ── Dual CTA ──
    wa_cta = ""
    if whatsapp_url and wa_qr:
        wa_cta = (
            '<div class="whatsapp-cta">\n'
            '  <div class="wa-text">\n'
            f'    <div class="wa-title">{_WA_SVG}WhatsApp de la Copro</div>\n'
            '    <div class="wa-desc">Infos résidence en temps réel.<br>Demandez le lien au CS de votre bâtiment.</div>\n'
            "  </div>\n"
            f'  <img class="qr-code" src="{wa_qr}" alt="QR WhatsApp">\n'
            "</div>\n"
        )
    else:
        wa_cta = (
            '<div class="whatsapp-cta">\n'
            '  <div class="wa-text">\n'
            f'    <div class="wa-title">{_WA_SVG}WhatsApp de la Copro</div>\n'
            '    <div class="wa-desc">Infos résidence en temps réel.<br>Demandez le lien au CS de votre bâtiment.</div>\n'
            "  </div>\n"
            "</div>\n"
        )

    return f"""\
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bienvenue — 5Hostachy</title>
<style>
{_CSS}
</style>
</head>
<body>
<div class="page">
  <div class="header">
    {_LOGO_SVG}
    <div class="header-text">
      <div class="header-title">Bienvenue dans votre résidence !</div>
      <div class="header-sub">Consignes de la copropriété</div>
    </div>
  </div>
  <div class="accent-bar"></div>
  <div class="content">
    <h2>Bonjour et bienvenue&nbsp;!</h2>
    <p>Vous venez d'emménager à la <strong>Résidence 5 Hostachy</strong>. Créez votre compte sur le portail pour accéder aux documents, calendrier, tickets et toutes les infos de la résidence.</p>
    <div class="dual-cta">
      <div class="cta-banner">
        <div class="cta-banner-text">
          <div class="label">Votre espace en ligne</div>
          <div class="url">{_GLOBE_SVG}{escape(site_url)}</div>
          <div class="hint">Inscription → Validation par le CS → C'est prêt !</div>
        </div>
        <img class="qr-code" src="{site_qr}" alt="QR {escape(site_url)}">
      </div>
      {wa_cta}
    </div>
    <hr class="sep">
    {_build_cs_section(cs_data)}
    <hr class="sep">
    {_build_syndic_section(syndic_data)}
    <hr class="sep">
    {_build_consignes_section(site_url)}
  </div>
  <div class="footer">
    <p>© {annee} • 5Hostachy • <strong>{escape(site_url)}</strong> • Résidence 5 Hostachy</p>
  </div>
</div>
</body>
</html>"""
