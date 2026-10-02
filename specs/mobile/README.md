# Spécifications — Application mobile (PWA)

> ⚠️ **Spécification d'origine** — le site a évolué depuis, le [manuel utilisateur](../../docs/manuel-utilisateur.html) fait foi (voir [`specs/README.md`](../README.md)).

## Sommaire

- [Exigences fonctionnelles](exigences-fonctionnelles.md)
- [Exigences non fonctionnelles](exigences-non-fonctionnelles.md)
- [Navigation et arborescence](navigation.md)

## Approche technique

L'application mobile est une **Progressive Web App (PWA)** — pas d'application native séparée.  
Une seule codebase SvelteKit couvre le web et le mobile.

## Plateformes cibles

| Plateforme | Version minimale | Navigateur | Installation |
|------------|-----------------|------------|--------------|
| iOS | 16.4+ | Safari | Ajout à l'écran d'accueil (A2HS) |
| Android | 10+ | Chrome | Ajout à l'écran d'accueil (A2HS) |

> Voir [architecture/stack.md](../architecture/stack.md) pour les détails techniques de la PWA.
