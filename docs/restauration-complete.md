# Restauration complète — Raspberry Pi 5

> **Objectif** : reconstruire l'environnement 5Hostachy depuis zéro sur un nouveau Raspberry Pi 5 (ou après un crash complet de la carte SD).
>
> **Durée estimée** : ~15 min (hors téléchargements réseau).

---

## Prérequis

| Élément | Détail |
|---|---|
| **Matériel** | Raspberry Pi 5 — Raspberry Pi OS Lite 64-bit (Debian Bookworm) |
| **Réseau** | IP fixe `192.168.1.222` (rpi1) ou `192.168.1.223` (rpi2), accès Internet |
| **GitHub** | Repo `philippe-tressard/5hostachy` (branche `main`) |
| **Backup .env** | Conserver une copie sécurisée du fichier `/opt/5hostachy/.env` (clés secrètes, tokens, SMTP, etc.) |
| **Backup SQLite** | Dernier fichier `app_*.db.gz` depuis `/data/5hostachy/backups/` |
| **Token Cloudflare** | Token du tunnel Cloudflare |

> ⚠️ **Sans le `.env` et la base SQLite**, l'application sera fonctionnelle mais vide (aucun utilisateur, aucune donnée).

---

## Étape 1 — Préparer le système

Flasher **Raspberry Pi OS Lite 64-bit** sur la carte SD avec **Raspberry Pi Imager**.
Activer SSH, configurer l'utilisateur `ptressard` et l'IP statique.

Se connecter :
```bash
ssh ptressard@192.168.1.222   # ou .223
```

---

## Étape 2 — Installer Docker & dépendances

```bash
# Mise à jour
sudo apt-get update -qq && sudo apt-get upgrade -y -qq

# Paquets système
sudo apt-get install -y -qq \
  curl wget git ca-certificates gnupg lsb-release \
  ufw fail2ban unattended-upgrades \
  cron sqlite3 rsync python3

# Docker Engine (ARM64)
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
sudo usermod -aG docker ptressard

# Important : se déconnecter/reconnecter pour le groupe docker
exit
```

Se reconnecter :
```bash
ssh ptressard@192.168.1.222
docker --version    # Vérifier
```

---

## Étape 3 — Cloner le dépôt

```bash
# Clé SSH deploy
ssh-keygen -t ed25519 -C "hostachy-rpi5-deploy" -f ~/.ssh/hostachy_deploy -N ""
cat ~/.ssh/hostachy_deploy.pub
# → Ajouter dans GitHub > Settings > Deploy keys

cat >> ~/.ssh/config << 'EOF'
Host github.com
    IdentityFile ~/.ssh/hostachy_deploy
    StrictHostKeyChecking no
EOF

# Cloner
sudo mkdir -p /opt/5hostachy
sudo chown ptressard:ptressard /opt/5hostachy
git clone git@github.com:philippe-tressard/5hostachy.git /opt/5hostachy
cd /opt/5hostachy
```

---

## Étape 4 — Restaurer le `.env`

```bash
# Option A : depuis un backup
scp user@backup-machine:/chemin/vers/.env /opt/5hostachy/.env

# Option B : recréer depuis l'exemple
cp /opt/5hostachy/.env.example /opt/5hostachy/.env
nano /opt/5hostachy/.env
```

**Variables critiques à renseigner** :

| Variable | Description |
|---|---|
| `SECRET_KEY` | Clé JWT — **min 32 caractères aléatoires** (`openssl rand -hex 32`) |
| `DOMAIN` | Domaine public (`5hostachy.fr`) |
| `ORIGIN` | URL complète (`https://5hostachy.fr`) — ou IP LAN si standby |
| `COOKIE_SECURE` | `true` (prod HTTPS) |
| `MAIL_*` | Configuration SMTP |
| `MAINTENANCE_KEY` | Clé partagée script maintenance ↔ API (`openssl rand -hex 24`) |

```bash
chmod 600 /opt/5hostachy/.env
```

---

## Étape 5 — Restaurer la base SQLite

```bash
# Créer les répertoires de volumes Docker
sudo mkdir -p /var/lib/docker/volumes/5hostachy_app_data/_data
sudo mkdir -p /var/lib/docker/volumes/5hostachy_backups/_data

# Restaurer la base de données
gunzip -c /chemin/vers/app_YYYYMMDD_HHMMSS.db.gz \
  > /var/lib/docker/volumes/5hostachy_app_data/_data/app.db
```

> Si aucun backup n'est disponible, l'application créera une base vide au premier démarrage (Alembic migrations s'exécutent automatiquement).

---

## Étape 6 — Lancer Docker Compose

```bash
cd /opt/5hostachy

# Exporter le hash Git pour le build
export GIT_HASH=$(git rev-parse --short HEAD)

# Build + lancement
docker compose up --build -d

# Vérifier les 4 conteneurs
docker compose ps
```

Résultat attendu :
```
NAME                STATUS
hostachy_caddy      Up
hostachy_front      Up
hostachy_api        Up
hostachy_whatsapp   Up
```

Vérifier les logs :
```bash
docker compose logs --tail=30 -f
```

Tester l'accès : `http://<RPi-IP>`

---

## Étape 7 — Exécuter les migrations

Les migrations Alembic s'exécutent automatiquement au démarrage du conteneur API via `start.sh`. Vérifier :

```bash
docker exec hostachy_api alembic current
# Doit afficher la dernière révision (ex: 0093)
```

---

## Étape 8 — Pare-feu UFW

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

## Étape 9 — Fail2ban

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

## Étape 10 — Cloudflare Tunnel

```bash
# Installer cloudflared
sudo bash /opt/5hostachy/scripts/installation/install-cloudflared.sh <VOTRE_TOKEN_TUNNEL>

# Vérifier
sudo systemctl status cloudflared
```

Le token est disponible dans **Cloudflare Zero Trust > Networks > Tunnels > Configure**.

> ⚠️ Ne démarrer cloudflared que sur le RPi **actif** (voir `.active`). Le standby laisse cloudflared arrêté.

---

## Étape 11 — Crons (sudo crontab -e)

```bash
sudo crontab -e
```

Ajouter les trois lignes suivantes :

```cron
# Bascule quotidienne rpi1 ↔ rpi2 (02h00)
0 2 * * * /opt/5hostachy/scripts/exploitation/bascule.sh >> /var/log/hostachy-bascule.log 2>&1

# Surveillance site + failover automatique (toutes les 5 min)
*/5 * * * * /opt/5hostachy/scripts/exploitation/health-watch.sh >> /var/log/hostachy-health-watch.log 2>&1

# Maintenance hebdomadaire (dimanche 03h00)
0 3 * * 0 /opt/5hostachy/scripts/exploitation/maintenance.sh >> /var/log/hostachy-maintenance.log 2>&1
```

Rendre les scripts exécutables :
```bash
chmod +x /opt/5hostachy/scripts/exploitation/bascule.sh
chmod +x /opt/5hostachy/scripts/exploitation/health-watch.sh
chmod +x /opt/5hostachy/scripts/exploitation/maintenance.sh
```

Vérifier :
```bash
sudo crontab -l
```

---

## Étape 12 — Clé SSH bascule (entre les deux RPi)

La bascule automatique nécessite une clé SSH sans passphrase entre les deux machines.

```bash
# Générer sur chaque RPi (en root)
sudo ssh-keygen -t ed25519 -C "hostachy-bascule" -f /root/.ssh/id_ed25519_bascule -N ""

# Copier la clé publique du rpi1 vers rpi2 et vice-versa
sudo ssh-copy-id -i /root/.ssh/id_ed25519_bascule.pub ptressard@192.168.1.223  # depuis rpi1
sudo ssh-copy-id -i /root/.ssh/id_ed25519_bascule.pub ptressard@192.168.1.222  # depuis rpi2

# Tester
sudo ssh -i /root/.ssh/id_ed25519_bascule ptressard@192.168.1.223 "echo ok"
```

---

## Étape 13 — Flag .active

```bash
# Sur le RPi actif (celui qui a cloudflared démarré)
echo "rpi1" > /opt/5hostachy/.active   # ou "rpi2"

# Sur le RPi standby
echo "rpi2" > /opt/5hostachy/.active   # doit contenir le nom du RPi ACTIF
```

---

## Étape 14 — Mises à jour automatiques Debian

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

## Vérification finale

| Test | Commande |
|---|---|
| Conteneurs actifs | `docker compose ps` |
| API health | `curl -s http://localhost/api/health` |
| URL publique | `curl -s https://5hostachy.fr/api/health` |
| Logs API | `docker compose logs api --tail=20` |
| Alembic version | `docker exec hostachy_api alembic current` |
| Heure conteneurs | `docker exec hostachy_api date` (doit afficher CEST) |
| UFW actif | `sudo ufw status` |
| Fail2ban actif | `sudo systemctl status fail2ban` |
| Cloudflare tunnel | `sudo systemctl status cloudflared` |
| Crons actifs | `sudo crontab -l` |
| Flag .active | `cat /opt/5hostachy/.active` |
| Accès web LAN | `http://192.168.1.222` |
| Accès web public | `https://5hostachy.fr` |

---

## Mise à jour courante (post-restauration)

```bash
sudo bash /opt/5hostachy/scripts/exploitation/MaJ-Hostachy.sh
```

---

## Arborescence de référence

```
/opt/5hostachy/                   ← Dépôt git
├── .env                          ← Secrets (non versionné)
├── .active                       ← "rpi1" ou "rpi2" (non versionné)
├── docker-compose.yml
├── Caddyfile
├── Dockerfile.caddy              ← Image Caddy custom (tzdata)
├── bascule.sh                    ← Bascule quotidienne rpi1 ↔ rpi2
├── health-watch.sh               ← Surveillance + failover automatique
├── maintenance.sh                ← Maintenance hebdomadaire (cron)
├── MaJ-Hostachy.sh               ← Mise à jour manuelle
├── install-cloudflared.sh        ← Installation tunnel Cloudflare
├── api/                          ← FastAPI + Alembic
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/
│   └── app/
├── front/                        ← SvelteKit
│   ├── Dockerfile                ← tzdata inclus (runner stage)
│   ├── package.json
│   └── src/
├── whatsapp-bridge/              ← Passerelle WhatsApp
│   ├── Dockerfile                ← tzdata inclus
│   └── index.js
└── docs/                         ← Documentation

Volumes Docker :
  app_data  → /app/data/app.db    (base SQLite)
  uploads   → /app/uploads/       (fichiers uploadés)
  backups   → /backups/           (sauvegardes auto)
  caddy_*   → config Caddy
```

---

## Sauvegardes offsite

### Fichiers critiques à sauvegarder hors du RPi

| Fichier | Contenu | Impact si perdu |
|---|---|---|
| `/opt/5hostachy/.env` | SECRET_KEY, SMTP, tokens | JWT invalides → tous les utilisateurs déconnectés |
| `/backups/*.db.gz` | Base SQLite (comptes, lots, tickets, sondages…) | **Perte totale des données** |
| Volume `uploads` | Photos et documents uploadés | Perte des fichiers joints |
| Token Cloudflare | Identifiant du tunnel | Tunnel à reconfigurer dans le dashboard CF |

### Copie manuelle (depuis le PC Windows)

```powershell
mkdir ~\backup-hostachy

# 1. Secrets
scp ptressard@192.168.1.222:/opt/5hostachy/.env ~\backup-hostachy\.env

# 2. Base de données (dernier backup)
scp "ptressard@192.168.1.222:/backups/*.db.gz" ~\backup-hostachy\

# 3. Fichiers uploadés
scp -r ptressard@192.168.1.222:/var/lib/docker/volumes/5hostachy_uploads/_data/ ~\backup-hostachy\uploads\
```

### Éléments déjà protégés (sur GitHub)

| Élément | Raison |
|---|---|
| Code source, Dockerfiles, migrations | Versionné dans le dépôt |
| Scripts (`bascule.sh`, `health-watch.sh`, `maintenance.sh`, `MaJ-Hostachy.sh`) | Versionné |
| Configuration Docker (`docker-compose.yml`, `Caddyfile`, `Dockerfile.caddy`) | Versionné |
| Configuration cron | Documentée dans ce guide (étape 11) |

### Recommandation

Stocker la `SECRET_KEY` et le token Cloudflare dans un **gestionnaire de mots de passe** (Bitwarden, 1Password, KeePass…).
