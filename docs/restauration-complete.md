# ðŸ”„ Restauration complÃ¨te â€” Raspberry Pi 5

> **Objectif** : reconstruire l'environnement 5Hostachy depuis zÃ©ro sur un nouveau Raspberry Pi 5 (ou aprÃ¨s un crash complet de la carte SD).
>
> **DurÃ©e estimÃ©e** : ~15 min (hors tÃ©lÃ©chargements rÃ©seau).

---

## PrÃ©requis

| Ã‰lÃ©ment | DÃ©tail |
|---|---|
| **MatÃ©riel** | Raspberry Pi 5 â€” Raspberry Pi OS Lite 64-bit (Debian Bookworm) |
| **RÃ©seau** | IP fixe `<RPi-IP>`, accÃ¨s Internet |
| **GitHub** | Repo `philippe-tressard/5hostachy` (branche `main`) |
| **Backup .env** | Conserver une copie sÃ©curisÃ©e du fichier `/opt/5hostachy/.env` (clÃ©s secrÃ¨tes, tokens, SMTP, etc.) |
| **Backup SQLite** | Dernier fichier `app_*.db.gz` depuis `/data/5hostachy/backups/` |
| **Token Cloudflare** | Token du tunnel Cloudflare (si applicable) |

> âš ï¸ **Sans le `.env` et la base SQLite**, l'application sera fonctionnelle mais vide (aucun utilisateur, aucune donnÃ©e).

---

## Ã‰tape 1 â€” PrÃ©parer le systÃ¨me

Flasher **Raspberry Pi OS Lite 64-bit** sur la carte SD avec **Raspberry Pi Imager**.  
Activer SSH, configurer l'utilisateur `<your-user>` et l'IP statique.

Se connecter :
```bash
ssh <your-user>@<RPi-IP>
```

---

## Ã‰tape 2 â€” Installer Docker & dÃ©pendances

```bash
# Mise Ã  jour
sudo apt-get update -qq && sudo apt-get upgrade -y -qq

# Paquets systÃ¨me
sudo apt-get install -y -qq \
  curl wget git ca-certificates gnupg lsb-release \
  ufw fail2ban unattended-upgrades \
  cron sqlite3 rsync

# Docker Engine (ARM64)
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
sudo usermod -aG docker <your-user>

# Important : se dÃ©connecter/reconnecter pour le groupe docker
exit
```

Se reconnecter :
```bash
ssh <your-user>@<RPi-IP>
docker --version    # VÃ©rifier
```

---

## Ã‰tape 3 â€” Cloner le dÃ©pÃ´t

```bash
# ClÃ© SSH deploy (si perdue, en regÃ©nÃ©rer une â€” voir docs/deploy-rpi5-auto.md)
ssh-keygen -t ed25519 -C "hostachy-rpi5-deploy" -f ~/.ssh/hostachy_deploy -N ""
cat ~/.ssh/hostachy_deploy.pub
# â†’ Ajouter dans GitHub > Settings > Deploy keys

cat >> ~/.ssh/config << 'EOF'
Host github.com
    IdentityFile ~/.ssh/hostachy_deploy
    StrictHostKeyChecking no
EOF

# Cloner
sudo mkdir -p /opt/5hostachy
sudo chown <your-user>:<your-user> /opt/5hostachy
git clone git@github.com:philippe-tressard/5hostachy.git /opt/5hostachy
cd /opt/5hostachy
```

---

## Ã‰tape 4 â€” Restaurer le `.env`

```bash
# Option A : depuis un backup
scp user@backup-machine:/chemin/vers/.env /opt/5hostachy/.env

# Option B : recrÃ©er depuis l'exemple
cp /opt/5hostachy/.env.example /opt/5hostachy/.env
nano /opt/5hostachy/.env
```

**Variables critiques Ã  renseigner** :

| Variable | Description |
|---|---|
| `SECRET_KEY` | ClÃ© JWT â€” **min 32 caractÃ¨res alÃ©atoires** (`openssl rand -hex 32`) |
| `DOMAIN` | Domaine public (`<your-domain>`) |
| `ORIGIN` | URL complÃ¨te (`https://<your-domain>`) |
| `COOKIE_SECURE` | `true` (prod HTTPS) |
| `MAIL_*` | Configuration SMTP |
| `MAINTENANCE_KEY` | ClÃ© partagÃ©e script maintenance â†” API (`openssl rand -hex 24`) |

```bash
chmod 600 /opt/5hostachy/.env
```

---

## Ã‰tape 5 â€” Restaurer la base SQLite

```bash
# CrÃ©er les rÃ©pertoires de volumes Docker
sudo mkdir -p /var/lib/docker/volumes/5hostachy_app_data/_data
sudo mkdir -p /var/lib/docker/volumes/5hostachy_backups/_data

# Restaurer la base de donnÃ©es
gunzip -c /chemin/vers/app_YYYYMMDD_HHMMSS.db.gz \
  > /var/lib/docker/volumes/5hostachy_app_data/_data/app.db
```

> Si aucun backup n'est disponible, l'application crÃ©era une base vide au premier dÃ©marrage (Alembic migrations s'exÃ©cutent automatiquement).

---

## Ã‰tape 6 â€” Lancer Docker Compose

```bash
cd /opt/5hostachy

# Exporter le hash Git pour le build
export GIT_HASH=$(git rev-parse --short HEAD)

# Build + lancement
docker compose up --build -d

# VÃ©rifier les 3 conteneurs
docker compose ps
```

RÃ©sultat attendu :
```
NAME               STATUS
hostachy_caddy     Up
hostachy_front     Up
hostachy_api       Up
```

VÃ©rifier les logs :
```bash
docker compose logs --tail=30 -f
```

Tester l'accÃ¨s : http://<RPi-IP>

---

## Ã‰tape 7 â€” ExÃ©cuter les migrations

Les migrations Alembic s'exÃ©cutent automatiquement au dÃ©marrage du conteneur API via `start.sh`. VÃ©rifier :

```bash
docker exec hostachy_api alembic current
# Doit afficher la derniÃ¨re rÃ©vision (ex: 0043)
```

---

## Ã‰tape 8 â€” Pare-feu UFW

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.1.0/24 to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw --force enable
sudo ufw status
```

---

## Ã‰tape 9 â€” Fail2ban

```bash
sudo tee /etc/fail2ban/jail.d/5hostachy.conf << 'EOF'
[sshd]
enabled  = true
port     = ssh
maxretry = 5
bantime  = 1h
EOF

sudo systemctl enable --now fail2ban
```

---

## Ã‰tape 10 â€” Cloudflare Tunnel (si applicable)

```bash
# Installer cloudflared
sudo bash /opt/5hostachy/install-cloudflared.sh <VOTRE_TOKEN_TUNNEL>

# VÃ©rifier
sudo systemctl status cloudflared
```

Le token est disponible dans **Cloudflare Zero Trust > Networks > Tunnels > Configure**.

---

## Ã‰tape 11 â€” Cron : sauvegardes + maintenance

### Sauvegarde quotidienne (prise en charge par l'API via APScheduler)

DÃ©jÃ  active automatiquement dans le conteneur API â€” rien Ã  configurer.  
Configurable dans **Admin > ParamÃ©trage site > ðŸ–¥ï¸ SystÃ¨me â€” Sauvegardes**.

### Maintenance mensuelle (script cron)

```bash
# Rendre le script exÃ©cutable
chmod +x /opt/5hostachy/maintenance.sh

# Installer le cron (en root)
sudo crontab -e
```

Ajouter la ligne :
```cron
0 3 1 * * /opt/5hostachy/maintenance.sh >> /var/log/hostachy-maintenance.log 2>&1
```

VÃ©rifie que le cron est actif :
```bash
sudo crontab -l | grep maintenance
# 0 3 1 * * /opt/5hostachy/maintenance.sh >> /var/log/hostachy-maintenance.log 2>&1
```

Tester manuellement :
```bash
sudo bash /opt/5hostachy/maintenance.sh
```

---

## Ã‰tape 12 â€” Mises Ã  jour automatiques Debian

```bash
sudo apt-get install -y unattended-upgrades
sudo tee /etc/apt/apt.conf.d/50unattended-upgrades-hostachy << 'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::Automatic-Reboot "false";
EOF
sudo systemctl enable --now unattended-upgrades
```

---

## VÃ©rification finale

| Test | Commande |
|---|---|
| Conteneurs actifs | `docker compose ps` |
| API health | `curl -s http://localhost/api/health` |
| Logs API | `docker compose logs api --tail=20` |
| Alembic version | `docker exec hostachy_api alembic current` |
| UFW actif | `sudo ufw status` |
| Fail2ban actif | `sudo systemctl status fail2ban` |
| Cloudflare tunnel | `sudo systemctl status cloudflared` |
| Cron maintenance | `sudo crontab -l \| grep maintenance` |
| AccÃ¨s web LAN | http://<RPi-IP> |
| AccÃ¨s web public | https://<your-domain> (si Cloudflare) |

---

## Mise Ã  jour courante (post-restauration)

Pour les mises Ã  jour futures, utiliser le script dÃ©diÃ© :

```bash
sudo bash /opt/5hostachy/MaJ-Hostachy.sh
```

Le script applique automatiquement les migrations DB (`alembic upgrade head`) dans le conteneur API aprÃ¨s redÃ©marrage.

---

## Arborescence de rÃ©fÃ©rence

```
/opt/5hostachy/                   â† DÃ©pÃ´t git
â”œâ”€â”€ .env                          â† Secrets (non versionnÃ©)
â”œâ”€â”€ docker-compose.yml
â”œâ”€â”€ Caddyfile
â”œâ”€â”€ maintenance.sh                â† Script maintenance mensuel (cron)
â”œâ”€â”€ MaJ-Hostachy.sh              â† Script mise Ã  jour manuelle
â”œâ”€â”€ install-cloudflared.sh        â† Installation tunnel Cloudflare
â”œâ”€â”€ api/                          â† FastAPI + Alembic
â”‚   â”œâ”€â”€ Dockerfile
â”‚   â”œâ”€â”€ requirements.txt
â”‚   â”œâ”€â”€ alembic/
â”‚   â””â”€â”€ app/
â”œâ”€â”€ front/                        â† SvelteKit
â”‚   â”œâ”€â”€ Dockerfile
â”‚   â”œâ”€â”€ package.json
â”‚   â””â”€â”€ src/
â””â”€â”€ docs/                         â† Documentation

Volumes Docker :
  app_data  â†’ /app/data/app.db    (base SQLite)
  uploads   â†’ /app/uploads/       (fichiers uploadÃ©s)
  backups   â†’ /backups/           (sauvegardes auto)
  caddy_*   â†’ certificats TLS
```

---

## Sauvegardes offsite â€” Ã€ FAIRE

> **âš ï¸ Section Ã  traiter** â€” Les donnÃ©es ci-dessous ne sont **pas** rÃ©cupÃ©rables depuis GitHub en cas de crash SD.

### Fichiers critiques Ã  sauvegarder hors du RPi

| Fichier | Contenu | Impact si perdu |
|---|---|---|
| `/opt/5hostachy/.env` | SECRET_KEY, SMTP, tokens | JWT invalides â†’ tous les utilisateurs dÃ©connectÃ©s |
| `/backups/*.db.gz` | Base SQLite (comptes, lots, tickets, sondagesâ€¦) | **Perte totale des donnÃ©es** |
| Volume `uploads` | Photos et documents uploadÃ©s | Perte des fichiers joints |
| Token Cloudflare | Identifiant du tunnel | Tunnel Ã  reconfigurer dans le dashboard CF |

### Copie manuelle (depuis le PC Windows)

```powershell
# CrÃ©er un dossier de backup local
mkdir ~\backup-hostachy

# 1. Secrets
scp <your-user>@<RPi-IP>:/opt/5hostachy/.env ~\backup-hostachy\.env

# 2. Base de donnÃ©es (dernier backup)
scp "<your-user>@<RPi-IP>:/backups/*.db.gz" ~\backup-hostachy\

# 3. Fichiers uploadÃ©s
scp -r <your-user>@<RPi-IP>:/var/lib/docker/volumes/5hostachy_uploads/_data/ ~\backup-hostachy\uploads\
```

### Automatisation (cron sur le RPi â†’ NAS ou PC)

```bash
# Ajouter dans sudo crontab -e (hebdomadaire, dimanche 04h00)
0 4 * * 0  rsync -az /opt/5hostachy/.env /backups/ <your-user>@<NAS-IP>:/backup-hostachy/ 2>/dev/null
```

### Ã‰lÃ©ments dÃ©jÃ  protÃ©gÃ©s (sur GitHub)

| Ã‰lÃ©ment | Raison |
|---|---|
| Code source, Dockerfiles, migrations | VersionnÃ© dans le dÃ©pÃ´t |
| Scripts (`maintenance.sh`, `MaJ-Hostachy.sh`) | VersionnÃ© |
| Configuration Docker (`docker-compose.yml`, `Caddyfile`) | VersionnÃ© |
| Configuration cron | DocumentÃ©e dans ce guide (Ã©tape 11) |

### Recommandation

Stocker la `SECRET_KEY` et le token Cloudflare dans un **gestionnaire de mots de passe** (Bitwarden, 1Password, KeePassâ€¦).
