# Cloudflare Worker â€” Page de maintenance

## Principe

Un Cloudflare Worker intercepte **toutes les requÃªtes** avant qu'elles atteignent le tunnel.  
Si l'origine (Cloudflare Tunnel â†’ Raspberry Pi) rÃ©pond avec un code d'erreur (502, 503, 530)
ou ne rÃ©pond pas du tout (tunnel coupÃ©, RPi Ã©teint), le Worker renvoie une page de maintenance
aux couleurs du site plutÃ´t que l'Ã©cran d'erreur Cloudflare par dÃ©faut.

```
Visiteur â†’ Cloudflare Edge â†’ Worker â†’ Tunnel â†’ RPi
                                  â†˜ Page maintenance (si RPi KO)
```

## Fichier source

`cloudflare-worker.js` Ã  la racine du projet.

## DÃ©ploiement (une seule fois)

### 1. CrÃ©er le Worker

1. Cloudflare Dashboard â†’ **Workers & Pages** â†’ **Create application** â†’ **Create Worker**
2. Donner un nom : `hostachy-maintenance`
3. Cliquer **Deploy** (page vide par dÃ©faut)
4. Cliquer **Edit code** â†’ **remplacer tout** par le contenu de `cloudflare-worker.js` â†’ **Save and deploy**

### 2. Assigner une Route

1. Cloudflare Dashboard â†’ ton domaine â†’ **Workers Routes** â†’ **Add route**
2. Route : `<your-domain>/*`
3. Worker : `hostachy-maintenance`
4. Sauvegarder

> La route `/*` couvre toutes les pages du site, y compris l'API (`/api/*`).

## Mise Ã  jour du Worker

1. Cloudflare Dashboard â†’ **Workers & Pages** â†’ `hostachy-maintenance` â†’ **Edit code**
2. Modifier le HTML dans la fonction `maintenancePage()`
3. **Save and deploy**

## Comportement

| Situation | RÃ©sultat |
|---|---|
| RPi UP, rÃ©ponse 200 | RequÃªte passÃ©e telle quelle â€” aucun impact |
| RPi rÃ©pond 502 / 503 / 530 | Page de maintenance HTML (503 + `Retry-After: 300`) |
| Tunnel coupÃ© (erreur rÃ©seau) | Page de maintenance HTML (503 + `Retry-After: 300`) |

## Limites plan Free

| | Free | Workers Paid ($5/mois) |
|---|---|---|
| RequÃªtes incluses | 100 000 / jour | 10 millions / mois |
| Au-delÃ  | Worker dÃ©sactivÃ© | $0,30 / million |
| Cold start | < 5 ms | < 5 ms |

Pour un usage rÃ©sidence (< 500 utilisateurs), le plan Free est largement suffisant.

## Design

La page de maintenance respecte la charte graphique Hostachy :
- Police titres : Georgia (serif systÃ¨me)
- Police UI : Segoe UI / system-ui
- Couleurs : Bleu Seine `#1E3A5F`, Or Croissy `#C9983A`, Pierre de taille `#F2EFE9`
- Composants : header + card + badge statut animÃ© + note informative
- Responsive mobile / desktop
