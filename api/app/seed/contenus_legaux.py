"""Mentions légales et politique de confidentialité — GABARIT DU PRODUIT.

Servis tels quels tant que rien n'a été saisi en base ; `routers/config.py` les
lit en repli. Ils énoncent des obligations (RGPD, durées de conservation,
coordonnées de la CNIL) : toute modification est une décision juridique, pas
rédactionnelle — cf. `standards/14-conformite-juridique.md`.

## 🔴 LE SEED PORTE LE PRODUIT, LA BASE PORTE L'INSTANCE (03/09/2026)

5Hostachy est sous licence MIT et peut être déployé ailleurs. Écrire ICI le nom
d'un éditeur ou d'un hébergeur les imposerait à tout autre déploiement, qui
publierait alors des mentions **fausses** — pire que des mentions vagues. Les
mentions de CETTE instance vivent en base (migration 0170).

Ce fichier reste donc générique. Mais il ne prétend plus être des mentions
valides : là où il disait « l'identité de l'éditeur correspond à la copropriété
ou au syndic bénévole qui gère cette instance », il dit **À RENSEIGNER**.

La différence n'est pas rédactionnelle. L'ancienne formulation décrivait ce
qu'il aurait fallu écrire, au lieu de l'écrire — et elle s'affichait sur une
page **publique** comme si elle était complète. Défaut sans symptôme : la page
se rend, elle a l'air finie, et personne ne la lit jusqu'à ce que quelqu'un
cherche qui contacter. La nôtre a vécu ainsi jusqu'à ce qu'un lecteur le voie.
"""

DEFAULT_LEGAL = {
    'mentions_legales': (
        '<h2>Éditeur du service</h2>'
        "<p><strong>À RENSEIGNER</strong> — nom de l'éditeur (personne physique ou "
        "syndicat des copropriétaires), et adresse si l'éditeur est professionnel.<br>"
        "Cette page est PUBLIQUE et la loi impose d'identifier l'éditeur : tant que "
        "cette mention n'est pas remplacée depuis <em>Admin → Légal</em>, le site ne "
        "satisfait pas à cette obligation.</p>"
        '<h2>Directeur de la publication</h2>'
        "<p><strong>À RENSEIGNER</strong> — nom de la personne responsable du contenu publié.</p>"
        '<h2>Hébergeur</h2>'
        "<p><strong>À RENSEIGNER</strong> — nom et coordonnées de l'hébergeur, ou mention "
        "de l'auto-hébergement et des intermédiaires techniques éventuels (DNS, proxy).</p>"
        '<h2>Propriété intellectuelle</h2>'
        '<p>Le code source de 5Hostachy est distribué sous licence <a href="https://spdx.org/licenses/MIT.html" target="_blank" rel="noopener noreferrer">MIT</a> (voir le fichier LICENSE du dépôt). '
        "Les contenus publiés dans l'application restent la propriété de leurs auteurs respectifs.</p>"
        '<h2>Responsabilité</h2>'
        "<p>L'éditeur s'efforce de fournir des informations exactes et à jour. Il ne saurait être tenu responsable "
        'des erreurs ou omissions dans les informations diffusées.</p>'
        '<h2>Contact</h2>'
        "<p>Pour toute question, contactez l'administrateur via la messagerie interne.</p>"
    ),
    'politique_confidentialite': (
        '<h2>1. Responsable du traitement</h2><p>Le responsable du traitement est <strong>À RENSEIGNER</strong>'
        " — nom de l'éditeur et adresse à laquelle exercer ses droits. Cette adresse doit être joignable <em>"
        "sans compte</em> : un droit d'effacement s'exerce souvent après la suppression du compte.</p><h2>"
        "2. Données collectées</h2><ul><li><strong>Données d'identification\xa0:</strong>"
        ' nom, prénom, adresse e-mail, téléphone (facultatif).</li><li><strong>Données de résidence\xa0:</strong>'
        " lot(s) associé(s), bâtiment, tantièmes.</li><li><strong>Données d'usage\xa0:</strong>"
        ' tickets soumis, messages échangés, documents téléchargés.</li><li><strong>Données techniques\xa0:</strong>'
        " tokens d'authentification (cookies HttpOnly), date de connexion.</li></ul><h2>"
        '3. Finalités et bases légales</h2><ul><li><strong>Gestion de la copropriété</strong>'
        ' — base\xa0: intérêt légitime (art.\xa06-1-f).</li><li><strong>Authentification et sécurité</strong>'
        ' — base\xa0: intérêt légitime (art.\xa06-1-f).</li><li><strong>Communication résidents/CS</strong>'
        ' — base\xa0: exécution du contrat (art.\xa06-1-b).</li><li><strong>E-mails transactionnels</strong>'
        ' — base\xa0: intérêt légitime / consentement.</li></ul><h2>4. Destinataires</h2><p>'
        "Les données sont accessibles uniquement aux membres du conseil syndical et à l'administrateur. Elles ne sont n"
        'i cédées à des tiers, ni commercialisées, ni utilisées à des fins publicitaires.</p><p><strong>'
        'Hébergement et acheminement.</strong> <strong>À RENSEIGNER</strong>'
        ' — où les données sont stockées, et par qui. <strong>À RENSEIGNER</strong>'
        " si un intermédiaire technique (CDN, proxy, résolveur DNS) relaie les connexions : nommez-le et dites d'où il "
        'opère. Un relais hors UE traite au minimum les adresses IP des visiteurs, et le taire rendrait ce paragraphe i'
        'nexact.</p><h2>5. Durée de conservation</h2><ul><li>'
        'Données de compte actif\xa0: durée de la relation + 2 ans.</li><li>'
        'Tokens de rafraîchissement\xa0: 7 jours glissants.</li><li>Sauvegardes\xa0: selon la configuration.</li></ul><h2>'
        "6. Vos droits</h2><p>Conformément au RGPD vous disposez des droits d'accès (art.\xa015), rectification (art.\xa016),"
        ' effacement (art.\xa017), portabilité (art.\xa020), opposition (art.\xa021) et retrait du consentement (art.\xa07-3). Pour'
        " les exercer, écrivez à l'adresse indiquée au point 1 — cette voie doit rester ouverte même sans compte, y com"
        "pris après sa suppression. Les titulaires d'un compte peuvent aussi passer par la messagerie de l'application,"
        ' ou exporter et effacer leurs données depuis leur profil. En cas de litige\xa0: <strong>CNIL</strong>'
        " — www.cnil.fr.</p><h2>7. Cookies</h2><p>L'application utilise exclusivement des cookies techniques d'authenti"
        'fication (<code>access_token</code>, <code>refresh_token</code>) définis en <code>'
        'HttpOnly; Secure; SameSite=Strict</code>. Aucun cookie publicitaire ou de traçage.</p>'
    ),
}
