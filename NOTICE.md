# NOTICE — 5Hostachy

**Projet** : 5Hostachy
**Copyright** © 2024-2026 Philippe TRESSARD
**Licence** : Licence 5Hostachy — source-available, fondée sur les principes de
l'AGPLv3, avec clauses commerciales (voir [`LICENSE-5Hostachy.md`](LICENSE-5Hostachy.md))
**Site** : <https://5hostachy.fr>

---

## 1. De quoi il s'agit

5Hostachy est un logiciel de gestion, de documentation et d'organisation pour
les copropriétés et ensembles immobiliers. Son code source est **accessible**,
mais soumis aux obligations détaillées dans la licence du projet.

Ce fichier porte les mentions d'attribution et les obligations minimales à
conserver dans toute redistribution.

## 2. Attribution obligatoire

Toute copie, modification ou redistribution doit inclure :

- la mention **« 5Hostachy — © Philippe TRESSARD »** ;
- un lien vers <https://5hostachy.fr> ;
- la conservation intégrale de **ce fichier** ;
- la conservation intégrale de **`LICENSE-5Hostachy.md`**.

L'attribution doit être visible dans la documentation, dans les pages « À
propos » ou « Crédits », et dans les interfaces d'administration lorsque le
logiciel est utilisé côté serveur.

## 3. Redistribution

Toute redistribution, modifiée ou non, doit :

- inclure ce fichier et le fichier de licence ;
- **indiquer clairement les modifications apportées** ;
- rester conforme à l'obligation de publication du code source.

## 4. Mise à disposition via un réseau

Quiconque met le logiciel à disposition via un service réseau doit en fournir le
**code source complet**, ce qui comprend :

- les fichiers d'origine ;
- les fichiers modifiés ;
- les scripts de déploiement nécessaires à l'exécution du service.

## 5. Usage commercial

L'usage commercial nécessite un **accord préalable avec l'auteur**. Sont
considérés comme commerciaux : l'intégration dans un service payant,
l'utilisation par une organisation à but lucratif, la revente ou la prestation
fondée sur le logiciel, et la création d'un service concurrent ou dérivé destiné
à générer des revenus.

**Les particuliers, associations, copropriétés et syndicats de copropriétaires
peuvent utiliser le logiciel gratuitement**, tant que l'usage n'est pas
commercial.

## 6. Marque et identité visuelle

Le nom **5Hostachy**, son logo et son identité visuelle sont protégés. Ils ne
peuvent servir à promouvoir un service concurrent, à laisser penser à une
affiliation ou une certification, ni à présenter une version « officielle » non
autorisée.

## 7. Contributions

Toute contribution est publiée sous la même licence. En proposant une
modification, son auteur accepte qu'elle soit intégrée au projet sous ces
conditions.

## 8. Absence de garantie

Le logiciel est fourni **« tel quel »**, sans garantie explicite ou implicite.
L'auteur ne peut être tenu responsable des dommages directs ou indirects liés à
son utilisation.

## 9. Composants tiers

5Hostachy s'appuie sur des bibliothèques et des contenus tiers. **Ils restent
sous leur propre licence** : la licence 5Hostachy ne s'applique pas à eux, et
leurs mentions se conservent avec eux.

L'inventaire complet — chaque dépendance de `front/`, `whatsapp-bridge/` et
`api/` avec sa licence — est [`docs/licences-tierces.md`](docs/licences-tierces.md).
Il est **généré** et vérifié par l'intégration continue, qui échoue sur toute
licence ni admise ni déclarée ; la politique et les motifs des exceptions vivent
dans `scripts/ci/licences_politique.py`.

### Contenus repris dans le dépôt

- **Icônes Lucide** (<https://lucide.dev>) — tracés recopiés dans
  `front/src/lib/icones-svg.json`, sa copie `api/app/utils/icones-svg.json`, les
  deux exemplaires du manuel utilisateur et `infra/cloudflare-worker.js`.
  Licence ISC, `Copyright (c) 2026 Lucide Icons and Contributors` ; pour les
  icônes dérivées de Feather, licence MIT, `Copyright (c) 2013-present Cole Bemis`.
  Textes et mentions :
  [`LICENSES/ISC.txt`](LICENSES/ISC.txt) et [`LICENSES/MIT.txt`](LICENSES/MIT.txt).
- **Logo WhatsApp** (tracé de Simple Icons, <https://simpleicons.org>) — versé
  au domaine public sous CC0-1.0 ([`LICENSES/CC0-1.0.txt`](LICENSES/CC0-1.0.txt)).
  CC0 ne cède aucun droit de marque : le logo reste une marque de son titulaire.

L'attribution de ces fichiers est déclarée dans `REUSE.toml`, et contrôlée par
`scripts/ci/contenus_tiers.py`.

### Composants sous licence non permissive

- **`libsignal` (GPL-3.0)**, tiré par `baileys`, est utilisé dans le **service
  de messagerie `whatsapp-bridge/`**. Ce service s'exécute dans un **conteneur
  distinct** de l'API et de l'interface, avec lesquels il communique
  **uniquement par HTTP**. Les binaires de `libvips` (LGPL-3.0-or-later),
  embarqués par `sharp`, vivent dans le même conteneur.
- Côté API : `certifi` (MPL-2.0) et `pyphen` (GPL 2.0+ / LGPL 2.1+ / MPL 1.1,
  selon son propre fichier de licence), tous deux utilisés sans modification.

> ⚠️ **La compatibilité de ces usages avec la licence du projet reste à valider
> par l'auteur.** Ce fichier constate où ces composants sont employés et
> comment ; il n'affirme rien de juridique.
