"""Mentions légales et politique de confidentialité — GABARIT DU PRODUIT.

Servis tels quels tant que rien n'a été saisi en base ; `routers/config.py` les
lit en repli. Ils énoncent des obligations (RGPD, durées de conservation,
coordonnées de la CNIL) : toute modification est une décision juridique, pas
rédactionnelle — cf. `standards/14-conformite-juridique.md`.

## 🔴 LE SEED PORTE LE PRODUIT, LA BASE PORTE L'INSTANCE (03/09/2026)

5Hostachy est sous Licence 5Hostachy et peut être déployé ailleurs. Écrire ICI le nom
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
        '<p>Le code source de 5Hostachy est <strong>accessible</strong> et distribué sous la '
        '<a href="https://github.com/philippe-tressard/5hostachy/blob/main/LICENSE-5Hostachy.md" target="_blank" rel="noopener noreferrer">Licence 5Hostachy</a> '
        "— source-available, fondée sur les principes de l'AGPLv3, avec clauses commerciales. "
        "Les particuliers, associations et copropriétés peuvent l'utiliser gratuitement ; tout usage "
        "commercial requiert un accord préalable de l'auteur.</p>"
        "<p>⚠️ Ce n'est <em>pas</em> une licence libre au sens de l'OSI : la clause commerciale ajoute "
        "une restriction que l'AGPLv3 n'admet pas.</p>"
        "<p>Les contenus publiés dans l'application restent la propriété de leurs auteurs respectifs.</p>"
        '<h2>Responsabilité</h2>'
        "<p>L'éditeur s'efforce de fournir des informations exactes et à jour. Il ne saurait être tenu responsable "
        'des erreurs ou omissions dans les informations diffusées.</p>'
        '<h2>Contact</h2>'
        "<p>Pour toute question, contactez l'administrateur via la messagerie interne.</p>"
    ),
    'politique_confidentialite': (
        '<h2>1. Responsable du traitement</h2><p>Le responsable du traitement est <strong>À '
        "RENSEIGNER</strong> — nom de l'éditeur et adresse à laquelle exercer ses droits. Cette "
        "adresse doit être joignable <em>sans compte</em> : un droit d'effacement s'exerce souvent "
        'après la suppression du compte.</p><h2>2. Données collectées</h2><ul><li><strong>Données '
        "d'identification\xa0:</strong> nom, prénom, adresse e-mail, téléphone "
        '(facultatif).</li><li><strong>Données de résidence\xa0:</strong> lot(s) associé(s), bâtiment, '
        "tantièmes.</li><li><strong>Données d'usage\xa0:</strong> tickets soumis, messages échangés, "
        'documents téléchargés.</li><li><strong>Données techniques\xa0:</strong> tokens '
        "d'authentification (cookies HttpOnly), date de connexion.</li></ul><li><strong>Photos et "
        'pièces jointes\xa0:</strong> images et documents que vous déposez sur un ticket, une actualité,'
        ' une annonce ou un contrat. Les métadonnées de prise de vue (EXIF, dont la géolocalisation) '
        "sont <strong>retirées</strong> au téléversement.</li><li><strong>Objets d'accès\xa0:</strong> "
        'badges Vigik et télécommandes de parking, avec leur porteur et le lot auquel ils sont '
        "rattachés.</li><li><strong>Mesure d'audience interne (télémétrie)\xa0:</strong> pages "
        'consultées et actions effectuées, rattachées à votre compte. Elle sert à savoir quels écrans'
        " servent, et à rien d'autre\xa0: elle n'alimente aucune publicité et ne quitte pas "
        "l'application. Vous pouvez la <strong>refuser</strong> et <strong>effacer</strong> votre "
        'historique depuis <em>Mon profil</em>, rubrique <em>Vos droits (RGPD)</em>.</li><h2>3. '
        'Finalités et bases légales</h2><ul><li><strong>Gestion de la copropriété</strong> — base\xa0: '
        'intérêt légitime (art.\xa06-1-f).</li><li><strong>Authentification et sécurité</strong> — '
        'base\xa0: intérêt légitime (art.\xa06-1-f).</li><li><strong>Communication résidents/CS</strong> — '
        'base\xa0: exécution du contrat (art.\xa06-1-b).</li><li><strong>E-mails transactionnels</strong> —'
        ' base\xa0: intérêt légitime / consentement.</li></ul><h2>4. Destinataires</h2><p>Les données '
        "sont accessibles uniquement aux membres du conseil syndical et à l'administrateur. Elles ne "
        'sont ni cédées à des tiers, ni commercialisées, ni utilisées à des fins '
        'publicitaires.</p><p>Cette phrase vise la <strong>cession</strong> et la '
        "<strong>commercialisation</strong>\xa0: il n'y en a aucune. Elle ne signifie pas qu'aucune "
        "donnée ne quitte l'application — les <strong>sous-traitants techniques</strong> nommés "
        'ci-dessous en reçoivent, pour la seule exécution du service.</p><p><strong>Hébergement et '
        'acheminement.</strong> <strong>À RENSEIGNER</strong> — où les données sont stockées, et par '
        'qui. <strong>À RENSEIGNER</strong> si un intermédiaire technique (CDN, proxy, résolveur DNS)'
        " relaie les connexions : nommez-le et dites d'où il opère. Un relais hors UE traite au "
        'minimum les adresses IP des visiteurs, et le taire rendrait ce paragraphe '
        'inexact.</p><p><strong>Services tiers qui reçoivent des données.</strong> Trois fonctions '
        "transmettent des informations hors de l'application lorsqu'elles sont activées — elles le "
        "sont au cas par cas, par l'administrateur\xa0:</p><ul><li><strong>Diffusion sur une messagerie "
        "instantanée</strong> — lorsqu'une publication est diffusée au groupe de la résidence, son "
        'titre, son texte et, le cas échéant, <strong>une photo</strong> sont transmis au service qui'
        " héberge ce groupe (WhatsApp, service de Meta). Les conditions de ce service s'appliquent "
        'alors à ce message. <strong>À RENSEIGNER</strong> si cette diffusion est active sur cette '
        'instance, et vers quel groupe.</li><li><strong>Assistant de rédaction (modèle de '
        "langage)</strong> — lorsqu'un membre du conseil syndical demande une reformulation ou la "
        "synthèse d'un contrat, le texte concerné — et, pour un contrat, le <strong>contenu des "
        'documents joints</strong> — est transmis au service de modèle de langage configuré. '
        "<strong>À RENSEIGNER</strong>\xa0: lequel, et depuis quel pays il opère. Rien n'est transmis si"
        " l'assistant est désactivé, et rien ne l'est automatiquement\xa0: la demande est toujours un "
        'geste explicite.</li><li><strong>Acheminement des courriels</strong> — les notifications '
        "partent par un service d'envoi de courriels, qui traite donc l'adresse du destinataire et le"
        ' contenu du message. <strong>À RENSEIGNER</strong>\xa0: lequel.</li></ul><h2>5. Durée de '
        'conservation</h2><ul><li>Données de compte actif\xa0: durée de la relation + 2 '
        'ans.</li><li>Tokens de rafraîchissement\xa0: 7 jours glissants.</li><li>Sauvegardes\xa0: selon la '
        "configuration.</li></ul><ul><li>Mesure d'audience\xa0: événements détaillés "
        '<strong>30\xa0jours</strong>, puis agrégats sans détail — par jour pendant 12\xa0mois, par mois '
        "pendant 10\xa0ans. L'effacement demandé depuis votre profil est immédiat.</li><li>Historique "
        'des envois de courriels\xa0: conservé pour le suivi des notifications. <strong>Aucune purge '
        "automatique n'est en place à ce jour</strong>\xa0; l'effacement s'obtient sur demande à "
        "l'adresse du point\xa01.</li></ul><h2>6. Vos droits</h2><p>Conformément au RGPD vous disposez "
        "des droits d'accès (art.\xa015), rectification (art.\xa016), effacement (art.\xa017), portabilité "
        '(art.\xa020), opposition (art.\xa021) et retrait du consentement (art.\xa07-3). Pour les exercer, '
        "écrivez à l'adresse indiquée au point 1 — cette voie doit rester ouverte même sans compte, y"
        " compris après sa suppression. Les titulaires d'un compte peuvent aussi passer par la "
        "messagerie de l'application, ou exporter et effacer leurs données depuis leur profil. En cas"
        " de litige\xa0: <strong>CNIL</strong> — www.cnil.fr.</p><h2>7. Cookies</h2><p>L'application "
        "utilise exclusivement des cookies techniques d'authentification (<code>access_token</code>, "
        '<code>refresh_token</code>) définis en <code>HttpOnly; Secure; SameSite=Strict</code>. Aucun'
        ' cookie publicitaire ou de traçage.</p>'
    ),
}

#: Les paragraphes ajoutés le 20/09/2026 (#1034) : ce que le code collecte et
#: transmet, que ce texte passait entièrement sous silence.
#:
#: 🔴 **Ils sont ici, et la migration 0199 les LIT.** Une migration qui les
#: aurait recopiés aurait créé deux rédactions parallèles d'un texte juridique —
#: et c'est alors le texte SERVI qui aurait divergé du gabarit, sans que rien ne
#: le signale. Le seed porte le produit ; la migration porte l'instance.
#:
#: Chaque entrée est `(ancre, paragraphe inséré AVANT l'ancre)`. Les ancres sont
#: les titres de section numérotés, les plus stables du document : une
#: reformulation du corps ne les déplace pas.
#:
#: ⚠️ Ce qui dépend du DÉPLOIEMENT reste « À RENSEIGNER » — quel groupe de
#: messagerie, quel fournisseur de modèle et depuis quel pays, quel service
#: d'acheminement. Nommer un prestataire ici l'imposerait à tout autre
#: déploiement, qui publierait alors des mentions fausses (décision du
#: 03/09/2026, en tête de ce fichier).
#:
#: 🔒 `api/tests/test_politique_confidentialite_couvre_le_code.py` confronte le
#: CODE à ce texte : toute capacité qui exporte une donnée doit y être nommée, et
#: la CI échoue tant qu'elle ne l'est pas. C'est le seul moment où quelqu'un y
#: pensera — celui où on l'écrit.
AJOUTS_1034 = [
    (
        '<h2>3. Finalités et bases légales</h2>',
        '<li><strong>Photos et pièces jointes\xa0:</strong> images et documents que vous déposez sur'
        ' un ticket, une actualité, une annonce ou un contrat. Les métadonnées de prise de vue '
        '(EXIF, dont la géolocalisation) sont <strong>retirées</strong> au '
        "téléversement.</li><li><strong>Objets d'accès\xa0:</strong> badges Vigik et télécommandes "
        'de parking, avec leur porteur et le lot auquel ils sont '
        "rattachés.</li><li><strong>Mesure d'audience interne (télémétrie)\xa0:</strong> pages "
        'consultées et actions effectuées, rattachées à votre compte. Elle sert à savoir quels '
        "écrans servent, et à rien d'autre\xa0: elle n'alimente aucune publicité et ne quitte pas "
        "l'application. Vous pouvez la <strong>refuser</strong> et <strong>effacer</strong> votre"
        ' historique depuis <em>Mon profil</em>, rubrique <em>Vos droits (RGPD)</em>.</li>'
    ),
    (
        '<h2>5. Durée de conservation</h2>',
        '<p><strong>Services tiers qui reçoivent des données.</strong> Trois fonctions '
        "transmettent des informations hors de l'application lorsqu'elles sont activées — elles "
        "le sont au cas par cas, par l'administrateur\xa0:</p><ul><li><strong>Diffusion sur une "
        "messagerie instantanée</strong> — lorsqu'une publication est diffusée au groupe de la "
        'résidence, son titre, son texte et, le cas échéant, <strong>une photo</strong> sont '
        'transmis au service qui héberge ce groupe (WhatsApp, service de Meta). Les conditions de'
        " ce service s'appliquent alors à ce message. <strong>À RENSEIGNER</strong> si cette "
        'diffusion est active sur cette instance, et vers quel groupe.</li><li><strong>Assistant '
        "de rédaction (modèle de langage)</strong> — lorsqu'un membre du conseil syndical demande"
        " une reformulation ou la synthèse d'un contrat, le texte concerné — et, pour un contrat,"
        ' le <strong>contenu des documents joints</strong> — est transmis au service de modèle de'
        ' langage configuré. <strong>À RENSEIGNER</strong>\xa0: lequel, et depuis quel pays il '
        "opère. Rien n'est transmis si l'assistant est désactivé, et rien ne l'est "
        'automatiquement\xa0: la demande est toujours un geste '
        'explicite.</li><li><strong>Acheminement des courriels</strong> — les notifications '
        "partent par un service d'envoi de courriels, qui traite donc l'adresse du destinataire "
        'et le contenu du message. <strong>À RENSEIGNER</strong>\xa0: lequel.</li></ul>'
    ),
    (
        '<h2>6. Vos droits</h2>',
        "<ul><li>Mesure d'audience\xa0: événements détaillés <strong>30\xa0jours</strong>, puis "
        "agrégats sans détail — par jour pendant 12\xa0mois, par mois pendant 10\xa0ans. L'effacement "
        'demandé depuis votre profil est immédiat.</li><li>Historique des envois de courriels\xa0: '
        "conservé pour le suivi des notifications. <strong>Aucune purge automatique n'est en "
        "place à ce jour</strong>\xa0; l'effacement s'obtient sur demande à l'adresse du "
        'point\xa01.</li></ul>'
    ),
    (
        '<p><strong>Hébergement et acheminement.</strong>',
        '<p>Cette phrase vise la <strong>cession</strong> et la '
        "<strong>commercialisation</strong>\xa0: il n'y en a aucune. Elle ne signifie pas qu'aucune "
        "donnée ne quitte l'application — les <strong>sous-traitants techniques</strong> nommés "
        'ci-dessous en reçoivent, pour la seule exécution du service.</p>'
    ),
]
