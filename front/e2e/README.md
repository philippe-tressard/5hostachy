# Tests de navigateur (Playwright)

Ce dossier porte les tests qui vérifient **ce qui se voit** — le comportement au
clavier, la responsivité, le rendu réel d'un écran. Le reste du projet vérifie
autre chose : `api/tests/` le serveur, les `lint:*` la **source**, `svelte-check`
les types. Aucun d'eux ne peut dire quel élément prend le focus au premier Tab,
ni si une page déborde horizontalement sur un téléphone.

```bash
cd front
npm run e2e            # tous les tests, profils bureau ET mobile
npm run e2e:ui         # le mode interactif, pour écrire un test
npx playwright test --project=bureau e2e/squelette.spec.ts
```

Le serveur de développement démarre tout seul (`webServer` dans
`playwright.config.ts`) et est réutilisé s'il tourne déjà.

## 🔴 Ce que ces tests ne couvrent PAS, et pourquoi

**Tout le site applicatif est derrière une connexion.** Sans session, seuls
`/auth/*`, les mentions légales et la politique de confidentialité sont
atteignables — c'est le périmètre actuel.

⚠️ **Le lien d'évitement « Aller au contenu » n'en fait donc pas partie** : il
vit dans le squelette `(app)` et son ancre `#contenu` n'existe pas sur les écrans
publics (voir `routes/+layout.svelte`). Ce qui est couvert ici est la moitié qui
avait réellement cassé — les bandeaux flottants qui volaient le premier Tab
(#802), défaut visible sur n'importe quelle page.

Couvrir les écrans applicatifs demande trois décisions, aucune prise :

1. un **compte de test** dédié dans la base de développement — jamais un compte
   réel, jamais un compte de production ;
2. un endroit pour ses identifiants qui ne soit **pas le dépôt** (`standards/03`
   §2 — un historique git conserve ce qu'on y a mis) : des variables
   d'environnement, et un test qui se **saute explicitement** quand elles
   manquent, plutôt qu'un échec laissant croire que l'écran est cassé ;
3. l'**API lancée** sur `localhost:8000` — `vite dev` ne fait qu'y proxifier les
   appels, il ne la démarre pas.

## ⚠️ Ces tests ne sont pas encore dans la CI

Les navigateurs pèsent une centaine de mégaoctets à installer sur un exécuteur.
Le job s'ajoutera quand le périmètre couvert le justifiera ; d'ici là ils se
lancent à la main, et `.gitignore` tient leurs sorties à l'écart
(`e2e-rapport/`, `test-results/`).

🔴 **Un test d'interface qui échoue pour une raison étrangère à l'interface finit
désarmé.** C'est pourquoi le contrôle des erreurs de console écarte explicitement
les échecs de chargement de ressource : sans API lancée, `/api/*` répond 500, et
cela ne dit rien de la page. Ce qui reste couvert est ce qui compte — une
exception JavaScript ou un `console.error` de l'application.
