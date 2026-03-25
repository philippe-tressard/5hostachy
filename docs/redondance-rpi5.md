# ðŸ” Redondance RPi5 â€” Option A : Failover passif

> **Statut** : Ã€ implÃ©menter ultÃ©rieurement
>
> **Objectif** : avoir un second RPi5 en veille chaude, capable de prendre le relais en ~5 min en cas de panne matÃ©rielle du principal.

---

## Architecture cible

```
RPi5 #1 (ACTIF)          RPi5 #2 (VEILLE)
â”œâ”€â”€ Docker Compose        â”œâ”€â”€ Docker Compose (arrÃªtÃ©)
â”œâ”€â”€ SQLite app.db    â”€â”€â”€â”€ â”œâ”€â”€ SQLite app.db   (Litestream, < 1s dÃ©lai)
â”œâ”€â”€ uploads/         â”€â”€â”€â”€ â”œâ”€â”€ uploads/        (rsync toutes les 5 min)
â”œâ”€â”€ .env             â”€â”€â”€â”€ â”œâ”€â”€ .env            (rsync toutes les 5 min)
â””â”€â”€ Cloudflare Tunnel     â””â”€â”€ Cloudflare Tunnel (second tunnel, en pause)
       â†“
   DNS public (<your-domain>)
       â†“
   En cas de bascule : activer le tunnel du RPi5 #2
```

---

## Composants

### 1. Litestream â€” rÃ©plication SQLite en temps rÃ©el

[Litestream](https://litestream.io) Ã©coute le WAL de SQLite et rÃ©plique chaque transaction vers le RPi5 #2 (ou un bucket S3). DÃ©lai < 1 seconde. Restauration < 1 minute.

**Sidecar Docker** Ã  ajouter dans `docker-compose.yml` :

```yaml
  litestream:
    image: litestream/litestream:latest
    container_name: hostachy_litestream
    restart: unless-stopped
    volumes:
      - app_data:/app/data
      - ./litestream.yml:/etc/litestream.yml:ro
    command: replicate
    networks:
      - hostachy
```

**`litestream.yml`** (Ã  crÃ©er Ã  la racine du repo) :

```yaml
dbs:
  - path: /app/data/app.db
    replicas:
      # Option 1 : rÃ©plication vers le second RPi via SFTP
      - type: sftp
        host: <RPi2-IP>:22
        user: <your-user>
        key-path: /app/data/litestream_id_ed25519
        path: /opt/5hostachy-replica/app.db

      # Option 2 : rÃ©plication vers un bucket S3-compatible (Backblaze B2, Cloudflare R2â€¦)
      # - type: s3
      #   bucket: hostachy-replica
      #   path: app.db
      #   access-key-id: ${LITESTREAM_ACCESS_KEY_ID}
      #   secret-access-key: ${LITESTREAM_SECRET_ACCESS_KEY}
      #   endpoint: https://s3.eu-central-003.backblazeb2.com
```

ClÃ© SSH dÃ©diÃ©e pour Litestream (sans passphrase) :

```bash
ssh-keygen -t ed25519 -C "litestream-replica" -f /opt/5hostachy/litestream_id_ed25519 -N ""
ssh-copy-id -i /opt/5hostachy/litestream_id_ed25519.pub <your-user>@<RPi2-IP>
```

### 2. rsync â€” synchronisation uploads + .env

ClÃ© SSH dÃ©diÃ©e entre les deux RPi :

```bash
ssh-keygen -t ed25519 -C "hostachy-replica" -f ~/.ssh/hostachy_replica -N ""
ssh-copy-id -i ~/.ssh/hostachy_replica.pub <your-user>@<RPi2-IP>
```

Crons Ã  ajouter dans `sudo crontab -e` sur le RPi5 #1 :

```cron
# Sync uploads (toutes les 5 min)
*/5 * * * *  rsync -az --delete -e "ssh -i /home/<your-user>/.ssh/hostachy_replica" \
  /var/lib/docker/volumes/5hostachy_uploads/_data/ \
  <your-user>@<RPi2-IP>:/var/lib/docker/volumes/5hostachy_uploads/_data/ 2>/dev/null

# Sync .env (toutes les 5 min)
*/5 * * * *  rsync -az -e "ssh -i /home/<your-user>/.ssh/hostachy_replica" \
  /opt/5hostachy/.env \
  <your-user>@<RPi2-IP>:/opt/5hostachy/.env 2>/dev/null
```

---

## ProcÃ©dure de bascule (RPi5 #1 en panne)

### Ã‰tape 1 â€” ArrÃªter Litestream sur RPi5 #1 (si encore accessible)

```bash
docker stop hostachy_litestream
```

### Ã‰tape 2 â€” Restaurer la base depuis la rÃ©plique Litestream

```bash
# Sur le RPi5 #2
litestream restore -o /var/lib/docker/volumes/5hostachy_app_data/_data/app.db \
  sftp://<your-user>@<RPi1-IP>/opt/5hostachy-replica/app.db
# (ou depuis S3 si rÃ©plique distante configurÃ©e)
```

### Ã‰tape 3 â€” DÃ©marrer Docker sur le RPi5 #2

```bash
cd /opt/5hostachy
git pull
export GIT_HASH=$(git rev-parse --short HEAD)
docker compose up --build -d
docker compose ps
curl -s http://localhost/api/health
```

### Ã‰tape 4 â€” Rediriger le trafic

**Via Cloudflare** (recommandÃ©) :
1. Aller dans **Cloudflare Zero Trust > Networks > Tunnels**
2. DÃ©sactiver le tunnel du RPi5 #1
3. Activer le tunnel du RPi5 #2 (prÃ©-configurÃ© en pause)

â†’ Propagation DNS : ~30 secondes, aucune intervention utilisateur requise.

**Via DNS local uniquement** :
Sur le routeur, changer l'IP associÃ©e au nom d'hÃ´te hostachy de `<RPi1-IP>` â†’ `<RPi2-IP>`.

---

## RÃ©sumÃ© des dÃ©lais

| Ã‰vÃ©nement | DÃ©lai |
|---|---|
| Restauration DB Litestream | < 1 min |
| `docker compose up --build` | 2-5 min |
| Bascule DNS Cloudflare | ~30 s |
| **Total bascule manuelle** | **~5 min** |
| Perte de donnÃ©es max | < 1 s (DB) + < 5 min (uploads) |

---

## DÃ©tection automatique de panne (optionnel)

Script Ã  placer sur le RPi5 #2, dÃ©clenchÃ© toutes les 2 minutes :

```bash
#!/bin/bash
# /opt/5hostachy/check-failover.sh
PRIMARY="<RPi1-IP>"
ALERT_EMAIL="admin@<your-domain>"

if ! curl -sf --max-time 5 "http://${PRIMARY}/api/health" > /dev/null 2>&1; then
    echo "[$(date)] ALERTE : RPi5 #1 ne rÃ©pond pas â€” bascule manuelle requise." \
      | mail -s "Hostachy â€” Panne RPi5 #1" "$ALERT_EMAIL" 2>/dev/null || true
fi
```

Cron sur RPi5 #2 (`sudo crontab -e`) :

```cron
*/2 * * * *  bash /opt/5hostachy/check-failover.sh
```

---

## Checklist d'implÃ©mentation

- [ ] RPi5 #2 installÃ© et configurÃ© (voir [restauration-complete.md](restauration-complete.md))
- [ ] ClÃ©s SSH sans passphrase : RPi5 #1 â†’ RPi5 #2 (Litestream + rsync)
- [ ] `litestream.yml` crÃ©Ã© Ã  la racine du repo
- [ ] Service `litestream` ajoutÃ© dans `docker-compose.yml`
- [ ] Variables `LITESTREAM_*` ajoutÃ©es dans `.env` si rÃ©plique S3
- [ ] Crons rsync `uploads/` + `.env` configurÃ©s sur RPi5 #1
- [ ] Second tunnel Cloudflare crÃ©Ã© et maintenu en pause
- [ ] Test de bascule rÃ©alisÃ© Ã  blanc (simuler une panne avant d'en avoir besoin)
