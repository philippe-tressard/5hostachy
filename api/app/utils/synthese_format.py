"""Le FORMAT d'une synthèse de contrat — ce que le conseil syndical a arrêté.

## Pourquoi ce fichier est séparé de `synthese_contrat.py` (11/09/2026)

La modularité l'a imposé, mais la ligne de coupe n'est pas arbitraire : **ici on
décrit ce qu'on attend du modèle**, là-bas on rassemble la matière et on passe
l'appel. Les deux ne bougent pas pour les mêmes raisons — ce fichier change quand
le conseil syndical veut autre chose dans sa synthèse, l'autre quand un document
se lit différemment.

Il ne connaît ni la base, ni le réseau, ni un contrat : ce sont des chaînes de
caractères. C'est ce qui permet de les vérifier sans rien monter.

## 🔴 Depuis le 17/09/2026, ce fichier porte la valeur d'ORIGINE, pas la servie

L'assistant se règle par usage, et son prompt vit en base
(`llm_synthese_contrat_prompt`, migration 0194) : l'administration le relit et
l'adapte sans toucher au code. `CONSIGNE` ci-dessous **initialise** cette valeur
sur une installation neuve, et sert de repli quand la clé est vidée — c'est ce
que fait « Rétablir le prompt d'origine ».

⚠️ **Modifier ce fichier ne change donc rien à une installation en service**
(`standards/06` §4). Le dire ici plutôt que de le laisser découvrir : un fichier
qui se présente comme la source de vérité alors qu'il n'est plus qu'un défaut
fait annoncer des livraisons sans effet.
"""
from __future__ import annotations

#: 🔴 LE FORMAT, tel que le conseil syndical l'a arrêté (11/09/2026).
#:
#: Il est imposé au modèle, il ne se négocie pas : c'est le format du carnet
#: d'entretien de CETTE copropriété, pas celui qu'un modèle trouverait joli. Les
#: exemples plus bas apprennent le ton ; ce gabarit impose la structure.
#:
#: ⚠️ Les précisions entre parenthèses sont VOLONTAIREMENT génériques. Une
#: version antérieure de ce travail proposait un schéma détaillé par type de
#: contrat (porte de parking, contrôle d'accès) : il aurait été exact une fois et
#: faux au contrat suivant — une assurance n'a ni visites annuelles ni pièces
#: détachées. Ce qu'on impose est ce qui vaut pour TOUT contrat de copropriété ;
#: le détail propre à chacun vient du document, pas du gabarit.
GABARIT = """1. Identification du fournisseur (raison sociale, adresse, SIRET ou RCS, activité)
2. Dates clés / Validité (signature, début, durée initiale, reconduction, préavis de résiliation)
3. Objet du contrat (ce qui est couvert, et ce qui relève d'une option)
4. Prestations incluses (fréquence des interventions, contenu d'une intervention, plages horaires)
5. Prestations non incluses (exclusions, seuils au-delà desquels un devis est exigé)
6. Conditions financières (montants et leur unité, options chiffrées, indexation, facturation, paiement)
7. Points d'attention pour la copropriété"""

#: 🔴 La règle de CITATION, ajoutée le 11/09/2026 sur proposition de Philippe.
#:
#: C'est ce qui distingue une synthèse vérifiable d'une synthèse crédible. Un
#: montant sans sa phrase d'origine oblige à rouvrir le PDF pour le contrôler —
#: c'est-à-dire à refaire le travail. Avec la citation, la relecture se fait sur
#: la synthèse elle-même, et une erreur du modèle SAUTE AUX YEUX : la citation ne
#: dit pas ce que la puce affirme.
#:
#: ⚠️ Elle ne remplace pas l'interdiction d'inventer, elle la rend CONSTATABLE.
CONSIGNE_CITATIONS = """Chaque fait chiffré ou contraignant — un montant, une durée, un préavis, un
seuil, une fréquence — est suivi de la phrase EXACTE du contrat qui le porte,
entre guillemets français, sur sa propre ligne, sans la reformuler ni la
corriger. Si tu ne peux pas citer, c'est que tu ne l'as pas lu : écris alors
« non précisé dans les éléments fournis »."""

#: 🔴 Les EXTRAITS, demandés par Philippe le 17/09/2026 après les premières
#: synthèses réelles : *« quand il y a une référence à une clause ou article d'un
#: §x, alors en fin de la synthèse tu joins les extraits »*.
#:
#: La citation (ci-dessus) et l'extrait (ici) ne répondent pas à la même
#: question, et c'est pourquoi les deux coexistent : la citation prouve UNE
#: ligne — le montant affirmé est bien celui qu'on lit —, l'extrait donne la
#: clause ENTIÈRE, pour décider sans rouvrir le PDF.
#:
#: ⚠️ Le plafond de trente lignes n'est pas une coquetterie : une clause recopiée
#: sans borne remplirait la réponse, et la section 8 mangerait le plafond de
#: jetons de la synthèse qu'elle est censée éclairer. La coupure se fait à la fin
#: d'une phrase, jamais au milieu d'un montant — un extrait tronqué à « 390 € »
#: dirait autre chose que « 390 € HT/an ».
#:
#: ⚠️ Et un résumé n'est PAS un extrait : mis sous un titre de clause, il se lit
#: comme le texte du contrat. Une clause qu'on ne peut pas recopier se déclare
#: non reproduite, comme une section sans information se déclare non précisée.
CONSIGNE_EXTRAITS = """🔴 LES EXTRAITS, en fin de synthèse.

Dès qu'une puce renvoie à une clause, à un article ou à un paragraphe numéroté
du contrat — « article 7.2 », « § 4 », « annexe B » —, ajoute après la section 7
une huitième et dernière section :

8. Extraits des clauses citées

Elle ne remplace aucune des sept autres, et rien ne s'écrit après elle. Elle
porte un extrait par clause ainsi renvoyée, dans l'ordre où les puces les
citent :

- chaque extrait s'ouvre par son TITRE, la clause nommée comme le contrat la
  nomme : « Article 7.2 — Résiliation », « § 4 — Pièces exclues » ;
- vient ensuite le texte du contrat, recopié mot pour mot, sans le reformuler,
  le corriger ni le compléter ;
- TRENTE LIGNES AU PLUS par extrait : au-delà, coupe à la fin d'une phrase et
  termine par « […] » sur sa propre ligne — jamais au milieu d'un mot, jamais au
  milieu d'un montant ;
- une clause citée par deux puces ne donne qu'UN extrait ;
- une clause que tu ne peux pas recopier n'a pas d'extrait : écris sous son titre
  « non reproduit dans les éléments fournis », et ne la résume pas — un résumé
  mis à la place d'un extrait se lit comme le texte du contrat.

⚠️ L'extrait ne remplace pas la citation exigée sous chaque fait chiffré : la
citation prouve la ligne, l'extrait donne la clause entière. Et si aucune puce ne
renvoie à une clause numérotée, la section 8 est ABSENTE — ne l'écris pas vide."""

CONSIGNE = f"""Tu rédiges la synthèse d'un contrat de COPROPRIÉTÉ — entretien, maintenance,
assurance, prestation de services — pour le conseil syndical. Elle sera lue par
des bénévoles, pas par des juristes.

🔴 Tu ne tires tes FAITS que des documents de CE contrat, joints ci-dessous, et
des champs de sa fiche. Rien d'autre : ni ta connaissance générale du
fournisseur, ni ce que contiennent habituellement les contrats de ce type, ni les
exemples de rédaction qui te sont donnés — ceux-là ne montrent que le TON et la
STRUCTURE attendus. Reprendre un montant, une durée ou une clause lus ailleurs
que dans ce contrat serait la pire erreur possible : la synthèse alimente le
carnet d'entretien, qui est un document réglementaire.

Respecte EXACTEMENT ces sept sections, numérotées, dans cet ordre :

{GABARIT}

Règles :
- une section sans information disponible est écrite avec la mention
  « non précisé dans les éléments fournis » — n'invente jamais un montant, une
  date, un numéro RCS ni une clause, et ne comble jamais un manque par ce qui
  est « habituel » ;
- des puces courtes, pas de paragraphes ;
- reprends les termes du contrat, sans les reformuler en langage commercial ;
- les montants gardent leur unité telle qu'elle est écrite (HT ou TTC, par an ou
  par visite) : « 390 € HT/an » ne devient jamais « environ 390 € » ;
- une option chiffrée se distingue de ce qui est inclus — dire qu'une prestation
  est comprise alors qu'elle est en supplément est l'erreur la plus coûteuse ;
- la section 7 est une LECTURE : ce que la copropriété doit surveiller
  (reconduction tacite, préavis, exclusions coûteuses, options facturées) ;
- pas de formule d'introduction ni de conclusion, la synthèse commence par le
  titre de la première section.

{CONSIGNE_CITATIONS}

{CONSIGNE_EXTRAITS}

Rends du HTML SIMPLE, et rien d'autre : un `<h3>` par section (« 1. Identification
du fournisseur »), un `<h4>` par titre d'extrait en section 8, un `<ul><li>` par
liste de puces, un `<p>` pour une phrase isolée, un `<blockquote>` pour une
citation ou un extrait du contrat. Pas de `<html>`, pas de `<body>`, pas de bloc
de code, pas de Markdown — le texte est déposé tel quel dans un champ de notes
enrichi."""
